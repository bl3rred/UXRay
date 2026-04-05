from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass

from uxray_fetch.compat import ensure_supported_python
from uxray_fetch.events import WebSocketEventBridge
from uxray_fetch.logic import render_chat_summary
from uxray_fetch.models import (
    AudienceReview,
    BossReview,
    BridgeEvent,
    EvaluateIssuesRequest,
    EvaluateIssuesResponse,
    IssuePacket,
    SynthesizedRecommendation,
)
from uxray_fetch.runtime_registry import register_agent_runtime, resolve_agent_address


@dataclass
class PendingReviews:
    expected: set[str]
    future: asyncio.Future[list[AudienceReview]]
    reviews: dict[str, AudienceReview]


class OrchestratorState:
    def __init__(self, bridge: WebSocketEventBridge) -> None:
        self.bridge = bridge
        self.review_batches: dict[str, PendingReviews] = {}
        self.boss_futures: dict[str, asyncio.Future[BossReview]] = {}
        self.synthesis_futures: dict[str, asyncio.Future[SynthesizedRecommendation]] = {}
        self.latest_recommendations: list[SynthesizedRecommendation] = []

    def open_review_batch(self, correlation_id: str, expected: set[str]) -> asyncio.Future[list[AudienceReview]]:
        future: asyncio.Future[list[AudienceReview]] = asyncio.get_running_loop().create_future()
        self.review_batches[correlation_id] = PendingReviews(expected=expected, future=future, reviews={})
        return future

    def add_review(self, correlation_id: str, review: AudienceReview) -> None:
        batch = self.review_batches.get(correlation_id)
        if batch is None or batch.future.done():
            return
        batch.reviews[review.audience] = review
        if batch.expected.issubset(batch.reviews.keys()):
            batch.future.set_result(list(batch.reviews.values()))
            self.review_batches.pop(correlation_id, None)

    def open_boss_future(self, correlation_id: str) -> asyncio.Future[BossReview]:
        future: asyncio.Future[BossReview] = asyncio.get_running_loop().create_future()
        self.boss_futures[correlation_id] = future
        return future

    def set_boss_review(self, correlation_id: str, boss_review: BossReview) -> None:
        future = self.boss_futures.pop(correlation_id, None)
        if future is not None and not future.done():
            future.set_result(boss_review)

    def open_synthesis_future(self, correlation_id: str) -> asyncio.Future[SynthesizedRecommendation]:
        future: asyncio.Future[SynthesizedRecommendation] = asyncio.get_running_loop().create_future()
        self.synthesis_futures[correlation_id] = future
        return future

    def set_synthesized_recommendation(self, correlation_id: str, recommendation: SynthesizedRecommendation) -> None:
        future = self.synthesis_futures.pop(correlation_id, None)
        if future is not None and not future.done():
            future.set_result(recommendation)


async def _emit(
    state: OrchestratorState,
    *,
    stage: str,
    correlation_id: str,
    issue_id: str,
    message: str,
    payload: dict[str, str] | None = None,
) -> None:
    await state.bridge.emit(
        BridgeEvent(
            stage=stage,
            correlation_id=correlation_id,
            issue_id=issue_id,
            message=message,
            payload=payload or {},
        )
    )


async def _await_reviews(
    ctx,
    state: OrchestratorState,
    *,
    correlation_id: str,
    issue: IssuePacket,
    audience_map: dict[str, str],
    ReviewRequestEnvelope,
    timeout_seconds: float,
    round_number: int = 1,
    rebuttal_request: str | None = None,
) -> list[AudienceReview]:
    future = state.open_review_batch(correlation_id, set(audience_map))
    await _emit(
        state,
        stage="review_dispatch_started",
        correlation_id=correlation_id,
        issue_id=issue.issue_id,
        message=f"Dispatching round {round_number} reviews.",
        payload={"round_number": str(round_number)},
    )
    for _, address in audience_map.items():
        await ctx.send(
            address,
            ReviewRequestEnvelope(
                correlation_id=correlation_id,
                issue_json=issue.model_dump_json(),
                round_number=round_number,
                rebuttal_request=rebuttal_request,
            ),
        )
    return await asyncio.wait_for(future, timeout=timeout_seconds)


async def _await_boss_review(
    ctx,
    state: OrchestratorState,
    *,
    correlation_id: str,
    issue: IssuePacket,
    boss_address: str,
    BossReviewRequestEnvelope,
    reviews: list[AudienceReview],
    timeout_seconds: float,
) -> BossReview:
    future = state.open_boss_future(correlation_id)
    await ctx.send(
        boss_address,
        BossReviewRequestEnvelope(
            correlation_id=correlation_id,
            issue_json=issue.model_dump_json(),
            reviews_json=json.dumps([review.model_dump() for review in reviews]),
        ),
    )
    return await asyncio.wait_for(future, timeout=timeout_seconds)


async def _await_synthesis(
    ctx,
    state: OrchestratorState,
    *,
    correlation_id: str,
    issue: IssuePacket,
    reviews: list[AudienceReview],
    boss_review: BossReview,
    synthesis_address: str,
    SynthesisRequestEnvelope,
    timeout_seconds: float,
) -> SynthesizedRecommendation:
    future = state.open_synthesis_future(correlation_id)
    await ctx.send(
        synthesis_address,
        SynthesisRequestEnvelope(
            correlation_id=correlation_id,
            issue_json=issue.model_dump_json(),
            reviews_json=json.dumps([review.model_dump() for review in reviews]),
            boss_review_json=boss_review.model_dump_json(),
        ),
    )
    return await asyncio.wait_for(future, timeout=timeout_seconds)


def _resolve_required_addresses(config) -> tuple[dict[str, str], str, str]:
    audience_map: dict[str, str] = {}
    for audience, settings in {
        "first_time_visitor": config.first_time_visitor,
        "intent_driven": config.intent_driven,
        "trust_evaluator": config.trust_evaluator,
        "custom_audience": config.custom_audience,
    }.items():
        address = resolve_agent_address(settings.name)
        if not address:
            raise RuntimeError(f"Specialist agent {settings.name} is not registered in the local runtime registry yet.")
        audience_map[audience] = address
    boss_address = resolve_agent_address(config.boss.name)
    synthesis_address = resolve_agent_address(config.synthesis.name)
    if not boss_address or not synthesis_address:
        raise RuntimeError("Boss and synthesis agents must be running before the orchestrator can evaluate issues.")
    return audience_map, boss_address, synthesis_address


def build_orchestrator_agent(*, config):
    ensure_supported_python()

    from datetime import datetime, timezone
    from pathlib import Path

    from uagents import Agent, Context, Protocol
    from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, EndSessionContent, TextContent, chat_protocol_spec

    from uxray_fetch.agent_messages import (
        AudienceReviewEnvelope,
        BossReviewEnvelope,
        BossReviewRequestEnvelope,
        RestEvaluateRequestEnvelope,
        RestEvaluateResponseEnvelope,
        ReviewRequestEnvelope,
        SynthesizedRecommendationEnvelope,
        SynthesisRequestEnvelope,
    )

    bridge = WebSocketEventBridge(host=config.ws_host, port=config.ws_port, enabled=config.ws_enabled)
    state = OrchestratorState(bridge=bridge)

    agent = Agent(
        name=config.orchestrator.name,
        seed=config.orchestrator.seed,
        port=config.orchestrator.port,
        agentverse=config.orchestrator.agentverse_url,
        mailbox=True,
        publish_agent_details=True,
        readme_path=str(Path(__file__).resolve().parents[2] / "README.md"),
    )
    internal_protocol = Protocol(name="uxray_internal_orchestration")
    chat_protocol = Protocol(spec=chat_protocol_spec)

    async def evaluate_payload(ctx: Context, payload: EvaluateIssuesRequest) -> EvaluateIssuesResponse:
        audience_map, boss_address, synthesis_address = _resolve_required_addresses(config)
        recommendations: list[SynthesizedRecommendation] = []
        for issue in payload.issues:
            correlation_id = f"{issue.issue_id}_{uuid.uuid4().hex[:8]}"
            reviews = await _await_reviews(
                ctx,
                state,
                correlation_id=correlation_id,
                issue=issue,
                audience_map=audience_map,
                ReviewRequestEnvelope=ReviewRequestEnvelope,
                timeout_seconds=config.orchestrator_timeout_seconds,
            )
            boss_review = await _await_boss_review(
                ctx,
                state,
                correlation_id=correlation_id,
                issue=issue,
                boss_address=boss_address,
                BossReviewRequestEnvelope=BossReviewRequestEnvelope,
                reviews=reviews,
                timeout_seconds=config.orchestrator_timeout_seconds,
            )
            await _emit(
                state,
                stage="boss_review_completed",
                correlation_id=correlation_id,
                issue_id=issue.issue_id,
                message=boss_review.summary,
                payload={"consensus_level": boss_review.consensus_level},
            )
            await _emit(
                state,
                stage="rebuttal_skipped",
                correlation_id=correlation_id,
                issue_id=issue.issue_id,
                message="Single-round mode enabled. Skipping round two rebuttals.",
            )
            recommendation = await _await_synthesis(
                ctx,
                state,
                correlation_id=correlation_id,
                issue=issue,
                reviews=reviews,
                boss_review=boss_review,
                synthesis_address=synthesis_address,
                SynthesisRequestEnvelope=SynthesisRequestEnvelope,
                timeout_seconds=config.orchestrator_timeout_seconds,
            )
            recommendations.append(recommendation)
            await _emit(
                state,
                stage="synthesis_completed",
                correlation_id=correlation_id,
                issue_id=issue.issue_id,
                message=f"Final priority: {recommendation.final_priority}",
            )
        state.latest_recommendations = recommendations
        return EvaluateIssuesResponse(status="completed", recommendations=recommendations)

    @agent.on_event("startup")
    async def on_startup(ctx: Context) -> None:
        register_agent_runtime(config.orchestrator.name, agent.address, config.orchestrator.port, "orchestrator")
        await bridge.start()
        ctx.logger.info("Registered %s at %s", config.orchestrator.name, agent.address)
        if config.ws_enabled:
            ctx.logger.info("WebSocket bridge available at ws://%s:%s", config.ws_host, config.ws_port)

    @agent.on_event("shutdown")
    async def on_shutdown(ctx: Context) -> None:
        await bridge.stop()
        ctx.logger.info("Orchestrator shutdown complete.")

    @agent.on_rest_post("/evaluate", RestEvaluateRequestEnvelope, RestEvaluateResponseEnvelope)
    async def handle_evaluate(ctx: Context, request: RestEvaluateRequestEnvelope) -> RestEvaluateResponseEnvelope:
        if request.api_key != config.api_key:
            return RestEvaluateResponseEnvelope(status="failed", error="Invalid API key")
        try:
            payload = EvaluateIssuesRequest.model_validate_json(request.payload_json)
            response = await evaluate_payload(ctx, payload)
            return RestEvaluateResponseEnvelope(status=response.status, response_json=response.model_dump_json())
        except Exception as exc:
            return RestEvaluateResponseEnvelope(status="failed", error=str(exc))

    @internal_protocol.on_message(AudienceReviewEnvelope)
    async def handle_audience_review(ctx: Context, sender: str, msg: AudienceReviewEnvelope) -> None:
        review = AudienceReview.model_validate_json(msg.review_json)
        state.add_review(msg.correlation_id, review)
        await _emit(
            state,
            stage="review_received",
            correlation_id=msg.correlation_id,
            issue_id=review.issue_id,
            message=f"Received {review.audience} review from {sender}.",
        )

    @internal_protocol.on_message(BossReviewEnvelope)
    async def handle_boss_review_message(ctx: Context, sender: str, msg: BossReviewEnvelope) -> None:
        boss_review = BossReview.model_validate_json(msg.boss_review_json)
        state.set_boss_review(msg.correlation_id, boss_review)
        ctx.logger.info("Received boss review from %s for %s", sender, boss_review.issue_id)

    @internal_protocol.on_message(SynthesizedRecommendationEnvelope)
    async def handle_synthesis_message(ctx: Context, sender: str, msg: SynthesizedRecommendationEnvelope) -> None:
        recommendation = SynthesizedRecommendation.model_validate_json(msg.recommendation_json)
        state.set_synthesized_recommendation(msg.correlation_id, recommendation)
        ctx.logger.info("Received synthesis output from %s for %s", sender, recommendation.issue_id)

    @chat_protocol.on_message(ChatMessage)
    async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )
        text = "".join(item.text for item in msg.content if isinstance(item, TextContent)).strip()
        if not text:
            return
        try:
            payload = EvaluateIssuesRequest(
                project_name="ASI:One Session",
                project_url="https://agentverse.ai",
                issues=[IssuePacket.model_validate_json(text)],
            )
            response = await evaluate_payload(ctx, payload)
            reply = render_chat_summary(response.recommendations)
        except Exception:
            if state.latest_recommendations and "why" in text.lower():
                latest = state.latest_recommendations[0]
                reply = f"{latest.issue_title} was prioritized as {latest.final_priority}. {latest.merged_rationale}"
            else:
                reply = "Send a JSON IssuePacket to trigger a UXRay Fetch review, or ask why the latest recommendation was prioritized."
        await ctx.send(
            sender,
            ChatMessage(
                content=[
                    TextContent(type="text", text=reply),
                    EndSessionContent(type="end-session"),
                ]
            ),
        )

    agent.include(internal_protocol, publish_manifest=False)
    agent.include(chat_protocol, publish_manifest=True)
    return agent
