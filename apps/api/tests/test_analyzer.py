from app.schemas import AdapterObservation, AdapterRunResult, PersonaRunResult
from app.services.analyzer import analyze_adapter_result, merge_persona_run_results


def test_analyzer_creates_issues_recommendations_and_artifacts() -> None:
    result = AdapterRunResult(
        live_url="https://browser-use.example/live",
        final_url="https://example.com/signup",
        summary="A primary action failed and pricing navigation was hard to spot.",
        observations=[
            AdapterObservation(
                route="/signup",
                title="Primary CTA did not respond",
                description="The signup button did not provide feedback after click.",
                severity="high",
                evidence=["No loading state", "Repeated click produced no visible change"],
                screenshot_url="https://example.com/cta.png",
                personas=["first_time_visitor"],
            ),
            AdapterObservation(
                route="/pricing",
                title="Pricing link is easy to miss",
                description="Low-contrast header link makes pricing harder to discover.",
                severity="medium",
                evidence=["Header contrast is weak"],
                screenshot_url=None,
                personas=["intent_driven"],
            ),
        ],
        artifacts=[],
        messages=[],
    )

    analysis = analyze_adapter_result(result)

    assert len(analysis.issues) == 2
    assert len(analysis.recommendations) == 2
    assert analysis.issues[0].issue_type == "cta_feedback"
    assert analysis.issues[0].severity == "high"
    assert analysis.issues[0].personas == ["first_time_visitor"]
    assert analysis.issues[0].screenshot_url == "https://example.com/cta.png"
    assert analysis.recommendations[0].source == "analyzer"
    assert analysis.artifacts[0].kind == "screenshot"


def test_analyzer_dedupes_repeated_recommendations() -> None:
    result = AdapterRunResult(
        summary="Two CTA issues should collapse to one recommendation.",
        observations=[
            AdapterObservation(
                route="/signup",
                title="Primary CTA did not respond",
                description="Signup action gives no feedback.",
                severity="high",
                evidence=["No loading state"],
                screenshot_url=None,
                personas=["first_time_visitor"],
            ),
            AdapterObservation(
                route="/checkout",
                title="Checkout CTA did not respond",
                description="Checkout action gives no feedback.",
                severity="high",
                evidence=["No loading state on checkout"],
                screenshot_url=None,
                personas=["intent_driven"],
            ),
        ],
        artifacts=[],
        messages=[],
    )

    analysis = analyze_adapter_result(result)

    assert len(analysis.issues) == 2
    assert len(analysis.recommendations) == 1


def test_merge_persona_run_results_collapses_duplicate_revisited_page_issues() -> None:
    merged = merge_persona_run_results(
        [
            PersonaRunResult(
                persona_key="first_time_visitor",
                display_label="First-time visitor",
                observations=[
                    AdapterObservation(
                        route="/pricing",
                        title="Pricing CTA blends into surrounding links",
                        description="The pricing CTA lacks enough contrast after the revisit.",
                        severity="medium",
                        evidence=["CTA looks secondary after returning to pricing"],
                        screenshot_url="https://example.com/pricing-a.png",
                        personas=["first_time_visitor"],
                    ),
                    AdapterObservation(
                        route="/pricing",
                        title="Pricing CTA is easy to miss on revisit",
                        description="The same low-contrast CTA is still hard to spot after looping back.",
                        severity="medium",
                        evidence=["Low contrast makes the CTA easy to miss"],
                        screenshot_url=None,
                        personas=["first_time_visitor"],
                    ),
                ],
            )
        ]
    )

    assert len(merged.observations) == 1
    assert merged.observations[0].route == "/pricing"
    assert len(merged.observations[0].evidence) == 2


def test_merge_persona_run_results_collapses_same_faq_section_repeats() -> None:
    merged = merge_persona_run_results(
        [
            PersonaRunResult(
                persona_key="first_time_visitor",
                display_label="First-time visitor",
                observations=[
                    AdapterObservation(
                        route="/",
                        title="FAQ accordion is easy to skip",
                        description="The FAQ section reads like passive body copy and does not pull the eye.",
                        severity="medium",
                        evidence=["FAQ questions blend into surrounding text"],
                        screenshot_url=None,
                        personas=["first_time_visitor"],
                    ),
                    AdapterObservation(
                        route="/",
                        title="FAQ answers feel buried in the accordion",
                        description="The FAQ content feels collapsed into a low-contrast accordion pattern.",
                        severity="medium",
                        evidence=["Accordion styling makes the FAQ section feel secondary"],
                        screenshot_url=None,
                        personas=["first_time_visitor"],
                    ),
                    AdapterObservation(
                        route="/",
                        title="FAQ section is too easy to miss",
                        description="The FAQ module is visually quiet compared with the surrounding sections.",
                        severity="medium",
                        evidence=["FAQ section lacks visual prominence"],
                        screenshot_url=None,
                        personas=["first_time_visitor"],
                    ),
                ],
            )
        ]
    )

    assert len(merged.observations) == 1
    assert "faq" in merged.observations[0].title.lower()


def test_merge_persona_run_results_keeps_distinct_same_route_components_separate() -> None:
    merged = merge_persona_run_results(
        [
            PersonaRunResult(
                persona_key="first_time_visitor",
                display_label="First-time visitor",
                observations=[
                    AdapterObservation(
                        route="/",
                        title="FAQ section is easy to miss",
                        description="The FAQ accordion does not stand out enough in the page flow.",
                        severity="medium",
                        evidence=["FAQ section lacks emphasis"],
                        screenshot_url=None,
                        personas=["first_time_visitor"],
                    ),
                    AdapterObservation(
                        route="/",
                        title="Primary CTA did not respond",
                        description="The main action near the hero area gave no visible feedback after click.",
                        severity="high",
                        evidence=["No loading state on the CTA"],
                        screenshot_url=None,
                        personas=["first_time_visitor"],
                    ),
                ],
            )
        ]
    )

    assert len(merged.observations) == 2
