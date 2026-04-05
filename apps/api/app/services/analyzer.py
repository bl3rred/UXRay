from __future__ import annotations

import re
from collections import defaultdict

from app.schemas import (
    AdapterObservation,
    AdapterRunResult,
    AnalysisArtifact,
    AnalysisIssue,
    AnalysisRecommendation,
    AnalysisResult,
    PersonaRunResult,
)


ISSUE_TEMPLATES = {
    "cta_feedback": {
        "title": "Add explicit CTA feedback",
        "summary": "Show immediate progress or response states when the primary action is triggered.",
        "likely_fix": "Wire the CTA to loading, success, and error states so the user gets visible confirmation after click.",
    },
    "navigation_discoverability": {
        "title": "Increase navigation discoverability",
        "summary": "Raise the prominence of the route or menu entry point that users need next.",
        "likely_fix": "Increase contrast, placement, or labeling for the navigation item so it competes less poorly with adjacent actions.",
    },
    "form_feedback": {
        "title": "Strengthen form feedback",
        "summary": "Make submission outcomes and validation states immediately visible around the form.",
        "likely_fix": "Surface inline validation and request-state messaging near the form controls and submit action.",
    },
    "trust_signal": {
        "title": "Improve trust and polish cues",
        "summary": "Reinforce credibility with clearer visual hierarchy, copy, or supporting trust signals.",
        "likely_fix": "Clarify value, reduce ambiguity, and make trust-supporting content more visible around the action area.",
    },
}

PERSONA_DISPLAY_LABELS = {
    "first_time_visitor": "First-time visitor",
    "intent_driven": "Intent-driven",
    "trust_evaluator": "Trust evaluator",
    "custom_audience": "Custom audience",
}

SECTION_ANCHORS = {
    "faq",
    "accordion",
    "pricing",
    "hero",
    "footer",
    "nav",
    "navigation",
    "header",
    "cta",
    "signup",
    "form",
    "cart",
    "checkout",
    "support",
}

SECTION_ANCHOR_PRIORITY = (
    "faq",
    "accordion",
    "pricing",
    "hero",
    "footer",
    "nav",
    "navigation",
    "header",
    "cta",
    "signup",
    "form",
    "cart",
    "checkout",
    "support",
)

SECTION_ANCHOR_ALIASES = {
    "accordion": "faq",
    "navigation": "nav",
}


def _classify_observation(observation: AdapterObservation) -> str:
    haystack = " ".join([observation.title, *observation.evidence]).lower().strip()
    if not haystack:
        haystack = observation.description.lower()
    if "cta" in haystack or "button" in haystack or "click" in haystack:
        return "cta_feedback"
    if "form" in haystack or "submit" in haystack or "validation" in haystack:
        return "form_feedback"
    if "trust" in haystack or "credib" in haystack or "polish" in haystack:
        return "trust_signal"
    return "navigation_discoverability"


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize_text(value).split()
        if len(token) > 2 and token not in {"page", "screen", "user", "flow"}
    }


def _route_family(route: str) -> str:
    raw_segments = [segment for segment in route.strip().lower().split("/") if segment]
    if not raw_segments:
        return "/"
    normalized_segments: list[str] = []
    for segment in raw_segments[:3]:
        if segment.isdigit() or re.fullmatch(r"[a-f0-9-]{6,}", segment):
            normalized_segments.append(":id")
        else:
            normalized_segments.append(segment)
    return "/" + "/".join(normalized_segments)


def _section_anchor(observation: AdapterObservation) -> str:
    tokens = _meaningful_tokens(
        " ".join([observation.title, observation.description, *observation.evidence])
    )
    anchors = tokens & SECTION_ANCHORS
    if not anchors:
        return "generic"
    for candidate in SECTION_ANCHOR_PRIORITY:
        if candidate in anchors:
            return SECTION_ANCHOR_ALIASES.get(candidate, candidate)
    resolved = sorted(anchors)[0]
    return SECTION_ANCHOR_ALIASES.get(resolved, resolved)


def _build_merge_key(observation: AdapterObservation) -> tuple[str, str, str]:
    issue_type = _classify_observation(observation)
    normalized_route = _route_family(observation.route)
    return (issue_type, normalized_route, _section_anchor(observation))


def _observations_match(left: AdapterObservation, right: AdapterObservation) -> bool:
    if _build_merge_key(left) != _build_merge_key(right):
        return False
    left_anchor = _section_anchor(left)
    left_title = _meaningful_tokens(left.title)
    right_title = _meaningful_tokens(right.title)
    left_context = _meaningful_tokens(f"{left.title} {left.description}")
    right_context = _meaningful_tokens(f"{right.title} {right.description}")
    if left_anchor != "generic":
        return True
    if left_title and right_title and len(left_title & right_title) >= max(1, min(len(left_title), len(right_title)) - 1):
        return True
    return bool(left_context & right_context) and len(left_context & right_context) >= 3


def merge_persona_run_results(results: list[PersonaRunResult]) -> AdapterRunResult:
    merged_observations: list[AdapterObservation] = []
    merged_artifacts: list[dict[str, str]] = []
    live_url: str | None = None
    final_url: str | None = None
    summaries: list[str] = []

    grouped: dict[tuple[str, str], list[list[AdapterObservation]]] = defaultdict(list)

    for result in results:
        if result.live_url and not live_url:
            live_url = result.live_url
        if result.final_url and not final_url:
            final_url = result.final_url
        if result.summary:
            summaries.append(f"{result.display_label}: {result.summary}")

        for artifact in result.artifacts:
            merged_artifacts.append(artifact)

        for observation in result.observations:
            personas = observation.personas or [result.persona_key]
            candidate = observation.model_copy(update={"personas": personas})
            clusters = grouped[_build_merge_key(candidate)]
            matched_cluster = next(
                (
                    cluster
                    for cluster in clusters
                    if any(_observations_match(existing, candidate) for existing in cluster)
                ),
                None,
            )
            if matched_cluster is None:
                clusters.append([candidate])
            else:
                matched_cluster.append(candidate)

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    for clusters in grouped.values():
        for grouped_observations in clusters:
            first = grouped_observations[0]
            merged_evidence: list[str] = []
            merged_personas: list[str] = []
            screenshot_url = None
            description = first.description
            severity = first.severity

            for observation in grouped_observations:
                for evidence in observation.evidence:
                    if evidence not in merged_evidence:
                        merged_evidence.append(evidence)
                for persona in observation.personas:
                    if persona not in merged_personas:
                        merged_personas.append(persona)
                if not screenshot_url and observation.screenshot_url:
                    screenshot_url = observation.screenshot_url
                if len(observation.description) > len(description):
                    description = observation.description
                if severity_rank[observation.severity] > severity_rank[severity]:
                    severity = observation.severity

            merged_observations.append(
                AdapterObservation(
                    route=first.route,
                    title=first.title,
                    description=description,
                    severity=severity,
                    evidence=merged_evidence,
                    screenshot_url=screenshot_url,
                    personas=merged_personas,
                )
            )

    merged_observations.sort(
        key=lambda observation: (
            severity_rank[observation.severity],
            len(observation.personas),
            len(observation.evidence),
            observation.title.lower(),
        ),
        reverse=True,
    )

    summary = " | ".join(summaries) if summaries else "Persona Browser Use audit completed."
    return AdapterRunResult(
        live_url=live_url,
        final_url=final_url,
        summary=summary,
        observations=merged_observations,
        artifacts=merged_artifacts,
        messages=[],
    )


def analyze_adapter_result(result: AdapterRunResult) -> AnalysisResult:
    issues: list[AnalysisIssue] = []
    recommendations_by_key: dict[tuple[str, str, str, str], AnalysisRecommendation] = {}
    artifacts: list[AnalysisArtifact] = []

    for observation in result.observations:
        issue_type = _classify_observation(observation)
        template = ISSUE_TEMPLATES[issue_type]

        issues.append(
            AnalysisIssue(
                issue_type=issue_type,
                title=observation.title,
                summary=observation.description,
                severity=observation.severity,
                route=observation.route,
                evidence=observation.evidence,
                confidence=0.92 if observation.severity == "high" else 0.81,
                personas=observation.personas,
                screenshot_url=observation.screenshot_url,
            )
        )
        recommendation = AnalysisRecommendation(
            title=template["title"],
            summary=template["summary"],
            likely_fix=template["likely_fix"],
        )
        recommendations_by_key[
            (
                recommendation.title,
                recommendation.summary,
                recommendation.likely_fix,
                recommendation.source,
            )
        ] = recommendation
        if observation.screenshot_url:
            provenance = ", ".join(
                PERSONA_DISPLAY_LABELS.get(persona, persona.replace("_", " "))
                for persona in observation.personas
            )
            artifacts.append(
                AnalysisArtifact(
                    kind="screenshot",
                    label=(
                        f"Evidence for {observation.title}"
                        if not provenance
                        else f"Evidence for {observation.title} ({provenance})"
                    ),
                    path_or_url=observation.screenshot_url,
                )
            )

    for artifact in result.artifacts:
        artifacts.append(
            AnalysisArtifact(
                kind=artifact.get("kind", "external"),
                label=artifact.get("label", "Artifact"),
                path_or_url=artifact.get("path_or_url", ""),
            )
        )

    if result.live_url and not any(
        artifact.kind == "live_url" and artifact.path_or_url == result.live_url
        for artifact in artifacts
    ):
        artifacts.append(
            AnalysisArtifact(
                kind="live_url",
                label="Browser Use live session",
                path_or_url=result.live_url,
            )
        )

    return AnalysisResult(
        issues=issues,
        recommendations=list(recommendations_by_key.values()),
        artifacts=artifacts,
    )
