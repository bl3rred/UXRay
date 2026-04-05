from __future__ import annotations

import json

from uxray_fetch.compat import ensure_supported_python
from uxray_fetch.logic import build_boss_review
from uxray_fetch.models import AudienceReview, IssuePacket
from uxray_fetch.runtime_registry import register_agent_runtime


def build_boss_agent(*, settings):
    ensure_supported_python()

    from uagents import Agent, Context
    from uagents.protocol import Protocol

    from uxray_fetch.agent_messages import BossReviewEnvelope, BossReviewRequestEnvelope

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
        register_agent_runtime(settings.name, agent.address, settings.port, "boss")
        ctx.logger.info("Registered %s at %s", settings.name, agent.address)

    @protocol.on_message(BossReviewRequestEnvelope)
    async def handle_boss_review(ctx: Context, sender: str, msg: BossReviewRequestEnvelope) -> None:
        issue = IssuePacket.model_validate_json(msg.issue_json)
        reviews = [AudienceReview.model_validate(item) for item in json.loads(msg.reviews_json)]
        boss_review = build_boss_review(
            correlation_id=msg.correlation_id,
            issue=issue,
            reviews=reviews,
        )
        await ctx.send(
            sender,
            BossReviewEnvelope(
                correlation_id=msg.correlation_id,
                boss_review_json=boss_review.model_dump_json(),
            ),
        )

    agent.include(protocol, publish_manifest=settings.publish_agent_details)
    return agent
