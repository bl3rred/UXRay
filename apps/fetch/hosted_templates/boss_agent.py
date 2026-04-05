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


class BossReviewRequestEnvelope(Model):
    correlation_id: str
    issue_json: str
    reviews_json: str


class BossReviewEnvelope(Model):
    correlation_id: str
    boss_review_json: str


def build_boss_review(correlation_id: str, issue: IssuePacket, reviews: list[AudienceReview]) -> BossReview:
    priorities = [review.priority_score for review in reviews]
    spread = (max(priorities) - min(priorities)) if priorities else 0
    directions = {review.fix_direction for review in reviews}
    consensus_level = "high"
    main_conflict = None
    rebuttal_required = False
    rebuttal_request = None

    if spread >= 3 or len(directions) > 1:
        consensus_level = "low"
        main_conflict = (
            "Priority spread is wide across audiences."
            if spread >= 3
            else "Fix direction differs across audiences."
        )
        rebuttal_required = True
        rebuttal_request = (
            "Explain why this issue should be handled before adjacent friction points "
            "and whether the primary fix should favor clarity, trust, or speed."
        )
    elif spread == 2:
        consensus_level = "medium"
        main_conflict = "Audience urgency differs slightly."

    average_priority = round(sum(priorities) / len(priorities), 1) if priorities else 0
    summary = (
        f"Boss agent sees {consensus_level} consensus for issue {issue.issue_id}. "
        f"Average priority score: {average_priority}."
    )

    return BossReview(
        correlation_id=correlation_id,
        issue_id=issue.issue_id,
        consensus_level=consensus_level,
        main_conflict=main_conflict,
        rebuttal_required=rebuttal_required,
        rebuttal_request=rebuttal_request,
        summary=summary,
    )


def render_role_text() -> str:
    return (
        "I resolve disagreement across audience reviews. I decide whether consensus is strong enough or whether one "
        "controlled rebuttal round is needed. Use uxray_orchestrator_agent for the full UXRay multi-agent workflow."
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
protocol = Protocol(name="uxray_boss_protocol")
chat_protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(BossReviewRequestEnvelope)
async def handle_boss_review(ctx: Context, sender: str, msg: BossReviewRequestEnvelope) -> None:
    issue = IssuePacket.parse_raw(msg.issue_json)
    reviews = [AudienceReview.parse_obj(item) for item in json.loads(msg.reviews_json)]
    boss_review = build_boss_review(msg.correlation_id, issue, reviews)
    await ctx.send(
        sender,
        BossReviewEnvelope(
            correlation_id=msg.correlation_id,
            boss_review_json=boss_review.json(),
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
