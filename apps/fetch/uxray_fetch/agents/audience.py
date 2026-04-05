from __future__ import annotations

from uxray_fetch.compat import ensure_supported_python
from uxray_fetch.logic import build_audience_review
from uxray_fetch.models import IssuePacket
from uxray_fetch.runtime_registry import register_agent_runtime


def build_audience_agent(*, settings, audience: str):
    ensure_supported_python()

    from uagents import Agent, Context
    from uagents.protocol import Protocol

    from uxray_fetch.agent_messages import AudienceReviewEnvelope, ReviewRequestEnvelope

    agent = Agent(
        name=settings.name,
        seed=settings.seed,
        port=settings.port,
        agentverse=settings.agentverse_url,
        mailbox=True,
        publish_agent_details=settings.publish_agent_details,
    )
    protocol = Protocol(name=f"{settings.name}_protocol")

    @agent.on_event("startup")
    async def on_startup(ctx: Context) -> None:
        register_agent_runtime(settings.name, agent.address, settings.port, audience)
        ctx.logger.info("Registered %s at %s", settings.name, agent.address)

    @protocol.on_message(ReviewRequestEnvelope)
    async def handle_review(ctx: Context, sender: str, msg: ReviewRequestEnvelope) -> None:
        issue = IssuePacket.model_validate_json(msg.issue_json)
        review = build_audience_review(
            correlation_id=msg.correlation_id,
            issue=issue,
            audience=audience,
            agent_name=settings.name,
            round_number=msg.round_number,
            rebuttal_request=msg.rebuttal_request,
        )
        await ctx.send(
            sender,
            AudienceReviewEnvelope(
                correlation_id=msg.correlation_id,
                review_json=review.model_dump_json(),
            ),
        )

    agent.include(protocol, publish_manifest=settings.publish_agent_details)
    return agent
