import json
import uuid
from datetime import datetime, timezone

from uagents import Agent, Context, Model
from uagents.protocol import Protocol
from uagents_core.contrib.protocols.chat import (
    AgentContent,
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)


class IssuePacket(Model):
    issue_id: str
    issue_title: str
    route: str
    persona: str
    viewport: str
    issue_type: str
    severity: str
    evidence: list[str] = []
    screenshot_summary: str
    dom_snippet: str
    custom_audience: str | None = None


class AudienceReview(Model):
    correlation_id: str
    issue_id: str
    agent_name: str
    audience: str
    impact_score: int
    priority_score: int
    fix_direction: str
    rationale: str
    round_number: int = 1


class BossReview(Model):
    correlation_id: str
    issue_id: str
    consensus_level: str
    main_conflict: str | None = None
    rebuttal_required: bool = False
    rebuttal_request: str | None = None
    summary: str


class SynthesizedRecommendation(Model):
    issue_id: str
    issue_title: str
    final_priority: str
    audience_impact_summary: str
    merged_rationale: str
    recommended_fix_direction: str
    gpt_handoff_string: str
    consensus_level: str


class SynthesisRequestEnvelope(Model):
    correlation_id: str
    issue_json: str
    reviews_json: str
    boss_review_json: str


class SynthesizedRecommendationEnvelope(Model):
    correlation_id: str
    recommendation_json: str


def priority_from_score(score: float) -> str:
    if score >= 8.5:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 5.0:
        return "medium"
    return "low"


def build_synthesized_recommendation(
    issue: IssuePacket,
    reviews: list[AudienceReview],
    boss_review: BossReview,
) -> SynthesizedRecommendation:
    average_priority = (sum(review.priority_score for review in reviews) / len(reviews)) if reviews else 1
    final_priority = priority_from_score(average_priority)
    impact_summary = "; ".join(
        f"{review.audience.replace('_', ' ')}={review.impact_score}/10"
        for review in reviews
    )
    merged_rationale = " ".join(review.rationale for review in reviews[:4]).strip()
    highest_review = max(reviews, key=lambda review: (review.priority_score, review.impact_score)) if reviews else None
    fix_direction = (
        highest_review.fix_direction
        if highest_review
        else "Improve the clarity of the next step for the user."
    )
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


def render_role_text() -> str:
    return (
        "I merge audience reviews and boss guidance into one final UXRay priority, rationale, and fix direction "
        "handoff for the later GPT fix stage. Use uxray_orchestrator_agent for the full UXRay workflow."
    )


def build_chat_reply(text: str) -> ChatMessage:
    content: list[AgentContent] = [
        TextContent(type="text", text=text),
        EndSessionContent(type="end-session"),
    ]
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid.uuid4(),
        content=content,
    )


agent = Agent()
protocol = Protocol(name="uxray_synthesis_protocol")
chat_protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(SynthesisRequestEnvelope)
async def handle_synthesis(ctx: Context, sender: str, msg: SynthesisRequestEnvelope) -> None:
    issue = IssuePacket.parse_raw(msg.issue_json)
    reviews = [AudienceReview.parse_obj(item) for item in json.loads(msg.reviews_json)]
    boss_review = BossReview.parse_raw(msg.boss_review_json)
    recommendation = build_synthesized_recommendation(issue, reviews, boss_review)
    await ctx.send(
        sender,
        SynthesizedRecommendationEnvelope(
            correlation_id=msg.correlation_id,
            recommendation_json=recommendation.json(),
        ),
    )


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )
    reply = render_role_text()
    await ctx.send(sender, build_chat_reply(reply))


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info("Received ACP acknowledgement from %s for %s", sender, msg.acknowledged_msg_id)


agent.include(protocol, publish_manifest=True)
agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
