from uxray_fetch.logic import build_audience_review, build_boss_review, build_synthesized_recommendation, pick_rebuttal_targets
from uxray_fetch.models import AudienceReview
from uxray_fetch.models import IssuePacket


def test_build_audience_review_is_deterministic() -> None:
    issue = IssuePacket(
        issue_id="issue_1",
        issue_title="Primary CTA appears disabled",
        route="/signup",
        persona="first_time_visitor",
        viewport="desktop",
        issue_type="cta_feedback",
        severity="high",
        evidence=["No loading state", "No success state"],
        screenshot_summary="CTA remains muted after click",
        dom_snippet="<button disabled>Start free</button>",
    )
    review = build_audience_review(
        correlation_id="corr_1",
        issue=issue,
        audience="intent_driven",
        agent_name="uxray_intent_driven_agent",
    )
    assert review.priority_score >= review.impact_score
    assert "ready to complete a task" in review.rationale


def test_boss_review_requests_rebuttal_for_large_priority_spread() -> None:
    issue = IssuePacket(
        issue_id="issue_2",
        issue_title="Navigation link is too subtle",
        route="/pricing",
        persona="first_time_visitor",
        viewport="desktop",
        issue_type="navigation_discoverability",
        severity="medium",
        evidence=["Low-contrast link"],
        screenshot_summary="Pricing link blends into header",
        dom_snippet="<a class='muted'>Pricing</a>",
    )
    reviews = [
        build_audience_review(
            correlation_id="corr_2",
            issue=issue,
            audience="first_time_visitor",
            agent_name="a",
        ),
        AudienceReview(
            correlation_id="corr_2",
            issue_id=issue.issue_id,
            agent_name="b",
            audience="custom_audience",
            impact_score=5,
            priority_score=9,
            fix_direction="Treat pricing visibility as a top-of-funnel revenue path blocker.",
            rationale="Custom audience sees pricing visibility as a major acquisition risk.",
            round_number=1,
        ),
    ]
    boss_review = build_boss_review(correlation_id="corr_2", issue=issue, reviews=reviews)
    assert boss_review.rebuttal_required is True
    assert boss_review.consensus_level == "low"
    assert pick_rebuttal_targets(reviews)


def test_synthesis_outputs_gpt_handoff_string() -> None:
    issue = IssuePacket(
        issue_id="issue_3",
        issue_title="Trust section is easy to miss",
        route="/checkout",
        persona="first_time_visitor",
        viewport="desktop",
        issue_type="trust_signal",
        severity="high",
        evidence=["Guarantee copy below fold"],
        screenshot_summary="Trust badges are off-screen on first load",
        dom_snippet="<section class='guarantee offscreen'>",
    )
    reviews = [
        build_audience_review(
            correlation_id="corr_3",
            issue=issue,
            audience="trust_evaluator",
            agent_name="uxray_trust_evaluator_agent",
        ),
        build_audience_review(
            correlation_id="corr_3",
            issue=issue,
            audience="first_time_visitor",
            agent_name="uxray_first_time_visitor_agent",
        ),
    ]
    boss_review = build_boss_review(correlation_id="corr_3", issue=issue, reviews=reviews)
    recommendation = build_synthesized_recommendation(issue=issue, reviews=reviews, boss_review=boss_review)
    assert recommendation.gpt_handoff_string.startswith("Prioritize trust_signal")
    assert recommendation.issue_title == issue.issue_title
