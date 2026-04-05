from __future__ import annotations

from statistics import mean

from uxray_fetch.models import AudienceReview, BossReview, ConsensusLevel, IssuePacket, Priority, SynthesizedRecommendation


SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
AUDIENCE_BIASES = {
    "first_time_visitor": {"cta_feedback": 2, "navigation_discoverability": 2, "trust_signal": 2, "form_feedback": 1},
    "intent_driven": {"cta_feedback": 3, "form_feedback": 2, "navigation_discoverability": 1, "trust_signal": 1},
    "trust_evaluator": {"trust_signal": 3, "cta_feedback": 1, "navigation_discoverability": 1, "form_feedback": 1},
    "custom_audience": {"cta_feedback": 2, "navigation_discoverability": 2, "trust_signal": 2, "form_feedback": 2},
}


def _clamp_score(score: int) -> int:
    return max(1, min(10, score))


def _bias_for_issue(audience: str, issue_type: str) -> int:
    return AUDIENCE_BIASES.get(audience, AUDIENCE_BIASES["custom_audience"]).get(issue_type, 1)


def _issue_direction(issue: IssuePacket) -> str:
    if issue.issue_type == "cta_feedback":
        return "Add an obvious CTA interaction state and clearer completion feedback."
    if issue.issue_type == "form_feedback":
        return "Improve inline validation and request-state feedback around the form."
    if issue.issue_type == "trust_signal":
        return "Increase trust signals and tighten the credibility cues near the decision point."
    return "Increase the prominence and clarity of the next-step navigation path."


def build_audience_review(
    *,
    correlation_id: str,
    issue: IssuePacket,
    audience: str,
    agent_name: str,
    round_number: int = 1,
    rebuttal_request: str | None = None,
) -> AudienceReview:
    severity_weight = SEVERITY_WEIGHT[issue.severity]
    audience_bias = _bias_for_issue(audience, issue.issue_type)
    evidence_weight = min(len(issue.evidence), 3)
    custom_weight = 1 if issue.custom_audience and audience == "custom_audience" else 0
    impact_score = _clamp_score(3 + severity_weight + audience_bias + custom_weight)
    priority_score = _clamp_score(impact_score + evidence_weight)
    rationale = (
        f"{audience.replace('_', ' ')} sees {issue.issue_type.replace('_', ' ')} on "
        f"{issue.route} as a {issue.severity}-severity blocker for {issue.persona}. "
        f"Evidence counted: {len(issue.evidence)}."
    )
    if rebuttal_request:
        rationale = f"{rationale} Rebuttal focus: {rebuttal_request}"
        priority_score = _clamp_score(priority_score + 1)
    if audience == "trust_evaluator" and issue.issue_type == "trust_signal":
        rationale = f"{rationale} Trust-sensitive users will hesitate if the interface feels ambiguous at the point of conversion."
    if audience == "intent_driven" and issue.issue_type in {"cta_feedback", "form_feedback"}:
        rationale = f"{rationale} This interrupts users who arrived ready to complete a task."
    return AudienceReview(
        correlation_id=correlation_id,
        issue_id=issue.issue_id,
        agent_name=agent_name,
        audience=audience,
        impact_score=impact_score,
        priority_score=priority_score,
        fix_direction=_issue_direction(issue),
        rationale=rationale,
        round_number=round_number,
    )


def build_boss_review(*, correlation_id: str, issue: IssuePacket, reviews: list[AudienceReview]) -> BossReview:
    priorities = [review.priority_score for review in reviews]
    spread = max(priorities) - min(priorities) if priorities else 0
    directions = {review.fix_direction for review in reviews}
    consensus_level: ConsensusLevel = "high"
    main_conflict: str | None = None
    rebuttal_required = False
    rebuttal_request: str | None = None
    if spread >= 3 or len(directions) > 1:
        consensus_level = "low"
        main_conflict = "Priority spread is wide across audiences." if spread >= 3 else "Fix direction differs across audiences."
        rebuttal_required = True
        rebuttal_request = "Explain why this issue should be handled before adjacent friction points and whether the primary fix should favor clarity, trust, or speed."
    elif spread == 2:
        consensus_level = "medium"
        main_conflict = "Audience urgency differs slightly."
    summary = f"Boss agent sees {consensus_level} consensus for issue {issue.issue_id}. Average priority score: {round(mean(priorities), 1) if priorities else 0}."
    return BossReview(
        correlation_id=correlation_id,
        issue_id=issue.issue_id,
        consensus_level=consensus_level,
        main_conflict=main_conflict,
        rebuttal_required=rebuttal_required,
        rebuttal_request=rebuttal_request,
        summary=summary,
    )


def pick_rebuttal_targets(reviews: list[AudienceReview]) -> list[str]:
    if len(reviews) < 2:
        return []
    ordered = sorted(reviews, key=lambda review: review.priority_score)
    return [ordered[0].audience, ordered[-1].audience]


def _priority_from_score(score: float) -> Priority:
    if score >= 8.5:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 5.0:
        return "medium"
    return "low"


def build_synthesized_recommendation(
    *,
    issue: IssuePacket,
    reviews: list[AudienceReview],
    boss_review: BossReview,
) -> SynthesizedRecommendation:
    average_priority = mean(review.priority_score for review in reviews) if reviews else 1
    final_priority = _priority_from_score(average_priority)
    impact_summary = "; ".join(f"{review.audience.replace('_', ' ')}={review.impact_score}/10" for review in reviews)
    merged_rationale = " ".join(review.rationale for review in reviews[:4]).strip()
    fix_direction = max(reviews, key=lambda review: (review.priority_score, review.impact_score)).fix_direction if reviews else _issue_direction(issue)
    gpt_handoff_string = (
        f"Prioritize {issue.issue_type} on {issue.route} for {issue.persona}. "
        f"Consensus={boss_review.consensus_level}. Recommended direction: {fix_direction} "
        f"Evidence: {'; '.join(issue.evidence[:3]) or issue.screenshot_summary}."
    )
    return SynthesizedRecommendation(
        issue_id=issue.issue_id,
        issue_title=issue.issue_title,
        final_priority=final_priority,
        audience_impact_summary=impact_summary,
        merged_rationale=merged_rationale,
        recommended_fix_direction=fix_direction,
        gpt_handoff_string=gpt_handoff_string,
        consensus_level=boss_review.consensus_level,
    )


def render_chat_summary(recommendations: list[SynthesizedRecommendation]) -> str:
    if not recommendations:
        return "No issue packet was provided."
    return " ".join(
        f"{recommendation.issue_title}: {recommendation.final_priority} priority. {recommendation.recommended_fix_direction}"
        for recommendation in recommendations
    )
