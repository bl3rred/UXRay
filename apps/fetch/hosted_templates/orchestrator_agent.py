import asyncio
import json
import os
import time
import urllib.error
import urllib.request
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


class EvaluateIssuesRequest(Model):
    project_name: str
    project_url: str
    issues: list[IssuePacket] = []


class EvaluateIssuesResponse(Model):
    status: str
    recommendations: list[SynthesizedRecommendation] = []
    error: str | None = None


class ReviewRequestEnvelope(Model):
    correlation_id: str
    issue_json: str
    round_number: int = 1
    rebuttal_request: str | None = None


class AudienceReviewEnvelope(Model):
    correlation_id: str
    review_json: str


class BossReviewRequestEnvelope(Model):
    correlation_id: str
    issue_json: str
    reviews_json: str


class BossReviewEnvelope(Model):
    correlation_id: str
    boss_review_json: str


class SynthesisRequestEnvelope(Model):
    correlation_id: str
    issue_json: str
    reviews_json: str
    boss_review_json: str


class SynthesizedRecommendationEnvelope(Model):
    correlation_id: str
    recommendation_json: str


class BackendEvaluateEnvelope(Model):
    session: str
    api_key: str
    payload_json: str


class BackendEvaluateResponseEnvelope(Model):
    session: str
    status: str
    response_json: str = ""
    error: str | None = None


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def storage_get_json(ctx: Context, key: str, default):
    raw = ctx.storage.get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def storage_set_json(ctx: Context, key: str, value) -> None:
    ctx.storage.set(key, json.dumps(value))


def append_trace(ctx: Context, correlation_id: str, stage: str, issue_id: str, message: str, payload: dict | None = None) -> None:
    trace_key = f"trace:{correlation_id}"
    trace = storage_get_json(ctx, trace_key, [])
    trace.append(
        {
            "stage": stage,
            "issue_id": issue_id,
            "message": message,
            "payload": payload or {},
            "created_at": current_timestamp(),
        }
    )
    storage_set_json(ctx, trace_key, trace)
    storage_set_json(ctx, "latest_trace", trace)


def pick_rebuttal_targets(reviews: list[AudienceReview]) -> list[str]:
    if len(reviews) < 2:
        return []
    ordered = sorted(reviews, key=lambda review: review.priority_score)
    return [ordered[0].audience, ordered[-1].audience]


def render_summary(recommendations: list[SynthesizedRecommendation]) -> str:
    if not recommendations:
        return "No issue packet was provided."
    return " ".join(
        f"{recommendation.issue_title}: {recommendation.final_priority} priority. {recommendation.recommended_fix_direction}"
        for recommendation in recommendations
    )


def render_why_text(recommendation: SynthesizedRecommendation) -> str:
    return (
        f"{recommendation.issue_title} was prioritized as {recommendation.final_priority}. "
        f"{recommendation.merged_rationale} Recommended direction: {recommendation.recommended_fix_direction}"
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


def maybe_rephrase_with_asi(text: str) -> str:
    if not env_bool("UXRAY_FETCH_ASI_REPHRASE_ENABLED", True):
        return text
    api_key = os.getenv("ASI_ONE_API_KEY", "").strip()
    if not api_key:
        return text

    payload = {
        "model": os.getenv("UXRAY_FETCH_ASI_MODEL", "asi1-mini"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Rewrite this UX evaluation explanation to be concise, plain, and judge-friendly. "
                    "Do not change the underlying meaning or numeric priority."
                ),
            },
            {"role": "user", "content": text},
        ],
    }
    request = urllib.request.Request(
        "https://api.asi1.ai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return text


async def wait_for_json_keys(ctx: Context, keys: list[str], timeout_seconds: float):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        values = []
        ready = True
        for key in keys:
            raw = ctx.storage.get(key)
            if raw is None:
                ready = False
                break
            values.append(json.loads(raw))
        if ready:
            ctx.logger.info(f"Resolved orchestration keys: {keys}")
            return values
        await asyncio.sleep(0.25)
    ctx.logger.error(f"Timed out waiting for keys: {keys}")
    raise TimeoutError(f"Timed out waiting for keys: {keys}")


def audience_addresses() -> dict[str, str]:
    return {
        "first_time_visitor": require_env("UXRAY_FETCH_FIRST_TIME_VISITOR_AGENT_ADDRESS"),
        "intent_driven": require_env("UXRAY_FETCH_INTENT_DRIVEN_AGENT_ADDRESS"),
        "trust_evaluator": require_env("UXRAY_FETCH_TRUST_EVALUATOR_AGENT_ADDRESS"),
        "custom_audience": require_env("UXRAY_FETCH_CUSTOM_AUDIENCE_AGENT_ADDRESS"),
    }


def boss_address() -> str:
    return require_env("UXRAY_FETCH_BOSS_AGENT_ADDRESS")


def synthesis_address() -> str:
    return require_env("UXRAY_FETCH_SYNTHESIS_AGENT_ADDRESS")


agent = Agent()
internal_protocol = Protocol(name="uxray_hosted_internal_orchestration")
backend_protocol = Protocol(name="uxray_hosted_backend_evaluation")
chat_protocol = Protocol(spec=chat_protocol_spec)


async def evaluate_issue(ctx: Context, issue: IssuePacket) -> SynthesizedRecommendation:
    correlation_id = f"{issue.issue_id}_{uuid.uuid4().hex[:8]}"
    timeout_seconds = env_float("UXRAY_FETCH_ORCHESTRATOR_TIMEOUT_SECONDS", 20.0)
    addresses = audience_addresses()

    append_trace(ctx, correlation_id, "review_dispatch_started", issue.issue_id, "Dispatching round 1 reviews.")
    review_requests = [
        ctx.send_and_receive(
            address,
            ReviewRequestEnvelope(
                correlation_id=correlation_id,
                issue_json=issue.json(),
                round_number=1,
                rebuttal_request=None,
            ),
            AudienceReviewEnvelope,
            timeout=int(timeout_seconds),
        )
        for address in addresses.values()
    ]
    review_results = await asyncio.gather(*review_requests)
    reviews = []
    for audience, (response, status) in zip(addresses, review_results, strict=True):
        if response is None:
            raise TimeoutError(f"Timed out waiting for {audience} review: {status.detail}")
        review = AudienceReview.parse_raw(response.review_json)
        reviews.append(review)
        append_trace(
            ctx,
            correlation_id,
            "review_received",
            review.issue_id,
            f"Received {review.audience} review synchronously.",
        )

    boss_response, boss_status = await ctx.send_and_receive(
        boss_address(),
        BossReviewRequestEnvelope(
            correlation_id=correlation_id,
            issue_json=issue.json(),
            reviews_json=json.dumps([review.dict() for review in reviews]),
        ),
        BossReviewEnvelope,
        timeout=int(timeout_seconds),
    )
    if boss_response is None:
        raise TimeoutError(f"Timed out waiting for boss review: {boss_status.detail}")
    boss_review = BossReview.parse_raw(boss_response.boss_review_json)
    append_trace(
        ctx,
        correlation_id,
        "boss_review_completed",
        issue.issue_id,
        boss_review.summary,
        {"consensus_level": boss_review.consensus_level},
    )

    append_trace(
        ctx,
        correlation_id,
        "rebuttal_skipped",
        issue.issue_id,
        "Single-round mode enabled. Skipping round two rebuttals.",
    )

    synthesis_response, synthesis_status = await ctx.send_and_receive(
        synthesis_address(),
        SynthesisRequestEnvelope(
            correlation_id=correlation_id,
            issue_json=issue.json(),
            reviews_json=json.dumps([review.dict() for review in reviews]),
            boss_review_json=boss_review.json(),
        ),
        SynthesizedRecommendationEnvelope,
        timeout=int(timeout_seconds),
    )
    if synthesis_response is None:
        raise TimeoutError(f"Timed out waiting for synthesis result: {synthesis_status.detail}")
    recommendation = SynthesizedRecommendation.parse_raw(synthesis_response.recommendation_json)
    append_trace(
        ctx,
        correlation_id,
        "synthesis_completed",
        issue.issue_id,
        f"Final priority: {recommendation.final_priority}",
    )
    storage_set_json(ctx, "latest_recommendations", [recommendation.dict()])
    return recommendation


async def evaluate_request(ctx: Context, payload: EvaluateIssuesRequest) -> EvaluateIssuesResponse:
    recommendations = []
    for issue in payload.issues:
        recommendations.append(await evaluate_issue(ctx, issue))
    return EvaluateIssuesResponse(status="completed", recommendations=recommendations)


async def handle_backend_evaluate(ctx: Context, request: BackendEvaluateEnvelope) -> str:
    if request.api_key != require_env("UXRAY_FETCH_SHARED_SECRET"):
        return BackendEvaluateResponseEnvelope(
            session=request.session,
            status="failed",
            error="Invalid API key.",
        ).json()
    try:
        payload = EvaluateIssuesRequest.parse_raw(request.payload_json)
        response = await evaluate_request(ctx, payload)
        return BackendEvaluateResponseEnvelope(
            session=request.session,
            status=response.status,
            response_json=response.json(),
        ).json()
    except Exception as exc:
        return BackendEvaluateResponseEnvelope(
            session=request.session,
            status="failed",
            error=str(exc),
        ).json()


@internal_protocol.on_message(AudienceReviewEnvelope)
async def handle_audience_review(ctx: Context, sender: str, msg: AudienceReviewEnvelope) -> None:
    review = AudienceReview.parse_raw(msg.review_json)
    key = f"review:{msg.correlation_id}:{review.audience}:{review.round_number}"
    ctx.logger.info(f"Storing audience review from {sender} under {key} for issue {review.issue_id}")
    storage_set_json(ctx, key, review.dict())
    append_trace(
        ctx,
        msg.correlation_id,
        "review_received",
        review.issue_id,
        f"Received {review.audience} review from {sender}.",
    )


@internal_protocol.on_message(BossReviewEnvelope)
async def handle_boss_review(ctx: Context, sender: str, msg: BossReviewEnvelope) -> None:
    boss_review = BossReview.parse_raw(msg.boss_review_json)
    ctx.logger.info(f"Storing boss review from {sender} for {msg.correlation_id}")
    storage_set_json(ctx, f"boss:{msg.correlation_id}", boss_review.dict())


@internal_protocol.on_message(SynthesizedRecommendationEnvelope)
async def handle_synthesis(ctx: Context, sender: str, msg: SynthesizedRecommendationEnvelope) -> None:
    recommendation = SynthesizedRecommendation.parse_raw(msg.recommendation_json)
    ctx.logger.info(f"Storing synthesis result from {sender} for {msg.correlation_id}")
    storage_set_json(ctx, f"synthesis:{msg.correlation_id}", recommendation.dict())


@backend_protocol.on_message(BackendEvaluateEnvelope, replies=BackendEvaluateResponseEnvelope)
async def handle_backend_evaluate_message(ctx: Context, sender: str, msg: BackendEvaluateEnvelope) -> None:
    response_json = await handle_backend_evaluate(ctx, msg)
    await ctx.send(sender, BackendEvaluateResponseEnvelope.parse_raw(response_json))


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
    if not text:
        return

    try:
        issue = IssuePacket.parse_raw(text)
        response = await evaluate_request(
            ctx,
            EvaluateIssuesRequest(
                project_name="ASI:One Session",
                project_url="https://agentverse.ai",
                issues=[issue],
            ),
        )
        reply = render_summary(response.recommendations)
    except Exception:
        latest_recommendations = storage_get_json(ctx, "latest_recommendations", [])
        if latest_recommendations and "why" in text.lower():
            recommendation = SynthesizedRecommendation.parse_obj(latest_recommendations[0])
            reply = render_why_text(recommendation)
        else:
            reply = "Send a JSON IssuePacket to trigger a UXRay review, or ask why the latest recommendation was prioritized."

    await ctx.send(sender, build_chat_reply(maybe_rephrase_with_asi(reply)))


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(f"Received ACP acknowledgement from {sender} for {msg.acknowledged_msg_id}")


agent.include(internal_protocol, publish_manifest=True)
agent.include(backend_protocol, publish_manifest=True)
agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
