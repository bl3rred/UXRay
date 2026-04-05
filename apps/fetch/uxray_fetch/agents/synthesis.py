from __future__ import annotations

import json

from uxray_fetch.compat import ensure_supported_python
from uxray_fetch.logic import build_synthesized_recommendation
from uxray_fetch.models import AudienceReview, BossReview, IssuePacket
from uxray_fetch.runtime_registry import register_agent_runtime


def build_synthesis_agent(*, settings):
    ensure_supported_python()

    from uagents import Agent, Context
    from uagents.protocol import Protocol

    from uxray_fetch.agent_messages import SynthesizedRecommendationEnvelope, SynthesisRequestEnvelope

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
        register_agent_runtime(settings.name, agent.address, settings.port, "synthesis")
        ctx.logger.info("Registered %s at %s", settings.name, agent.address)

    @protocol.on_message(SynthesisRequestEnvelope)
    async def handle_synthesis(ctx: Context, sender: str, msg: SynthesisRequestEnvelope) -> None:
        issue = IssuePacket.model_validate_json(msg.issue_json)
        reviews = [AudienceReview.model_validate(item) for item in json.loads(msg.reviews_json)]
        boss_review = BossReview.model_validate_json(msg.boss_review_json)
        recommendation = build_synthesized_recommendation(
            issue=issue,
            reviews=reviews,
            boss_review=boss_review,
        )
        await ctx.send(
            sender,
            SynthesizedRecommendationEnvelope(
                correlation_id=msg.correlation_id,
                recommendation_json=recommendation.model_dump_json(),
            ),
        )

    agent.include(protocol, publish_manifest=settings.publish_agent_details)
    return agent
