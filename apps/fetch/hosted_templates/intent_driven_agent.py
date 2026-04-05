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


AUDIENCE = "intent_driven"
AGENT_NAME = "uxray_intent_driven_agent"
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
AUDIENCE_BIASES = {
    "cta_feedback": 3,
    "form_feedback": 2,
    "navigation_discoverability": 1,
    "trust_signal": 1,
}


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


class ReviewRequestEnvelope(Model):
    correlation_id: str
    issue_json: str
    round_number: int = 1
    rebuttal_request: str | None = None


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


class AudienceReviewEnvelope(Model):
    correlation_id: str
    review_json: str


def clamp_score(score: int) -> int:
    return max(1, min(10, score))


def issue_direction(issue: IssuePacket) -> str:
    if issue.issue_type == "cta_feedback":
        return "Add an obvious CTA interaction state and clearer completion feedback."
    if issue.issue_type == "form_feedback":
        return "Improve inline validation and request-state feedback around the form."
    if issue.issue_type == "trust_signal":
        return "Increase trust signals and tighten the credibility cues near the decision point."
    return "Increase the prominence and clarity of the next-step navigation path."


def build_review(correlation_id: str, issue: IssuePacket, round_number: int, rebuttal_request: str | None) -> AudienceReview:
    severity_weight = SEVERITY_WEIGHT.get(issue.severity, 1)
    audience_bias = AUDIENCE_BIASES.get(issue.issue_type, 1)
    impact_score = clamp_score(3 + severity_weight + audience_bias)
    priority_score = clamp_score(impact_score + min(len(issue.evidence), 3))
    rationale = (
        f"Intent-driven users see {issue.issue_type.replace('_', ' ')} on {issue.route} "
        f"as a {issue.severity}-severity blocker for {issue.persona}. Evidence counted: {len(issue.evidence)}. "
        f"This interrupts users who arrived ready to complete a task."
    )
    if rebuttal_request:
        rationale = f"{rationale} Rebuttal focus: {rebuttal_request}"
        priority_score = clamp_score(priority_score + 1)
    return AudienceReview(
        correlation_id=correlation_id,
        issue_id=issue.issue_id,
        agent_name=AGENT_NAME,
        audience=AUDIENCE,
        impact_score=impact_score,
        priority_score=priority_score,
        fix_direction=issue_direction(issue),
        rationale=rationale,
        round_number=round_number,
    )


def render_specialist_summary(issue: IssuePacket) -> str:
    review = build_review("chat", issue, 1, None)
    return (
        f"Intent-driven lens: {review.priority_score}/10 urgency. "
        f"{review.fix_direction} {review.rationale} "
        "Use uxray_orchestrator_agent for the full multi-agent UXRay workflow."
    )


def render_role_text() -> str:
    return (
        "I evaluate issues through an intent-driven lens, focusing on whether ready-to-act users can finish their task "
        "without friction or hesitation. Use uxray_orchestrator_agent for the full UXRay multi-agent review."
    )


def extract_text(msg: ChatMessage) -> str:
    return "".join(item.text for item in msg.content if isinstance(item, TextContent)).strip()


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
protocol = Protocol(name="uxray_intent_driven_protocol")
chat_protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(ReviewRequestEnvelope)
async def handle_review(ctx: Context, sender: str, msg: ReviewRequestEnvelope) -> None:
    issue = IssuePacket.parse_raw(msg.issue_json)
    review = build_review(msg.correlation_id, issue, msg.round_number, msg.rebuttal_request)
    await ctx.send(
        sender,
        AudienceReviewEnvelope(
            correlation_id=msg.correlation_id,
            review_json=review.json(),
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
    text = extract_text(msg)
    try:
        issue = IssuePacket.parse_raw(text)
        reply = render_specialist_summary(issue)
    except Exception:
        reply = render_role_text()
    await ctx.send(sender, build_chat_reply(reply))


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info("Received ACP acknowledgement from %s for %s", sender, msg.acknowledged_msg_id)


agent.include(protocol, publish_manifest=True)
agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
