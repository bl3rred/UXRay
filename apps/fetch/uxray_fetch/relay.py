from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from uagents_core.envelope import Envelope
from uagents_core.identity import Identity

from uxray_fetch.models import (
    BackendEvaluateEnvelope,
    BackendEvaluateResponseEnvelope,
    EvaluateIssuesRequest,
    EvaluateIssuesResponse,
)


ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = ROOT_DIR / ".env.local"
BACKEND_PROTOCOL_NAME = "uxray_hosted_backend_evaluation"
DEFAULT_RELAY_AGENT_SEED = "replace-this-with-a-new-seed-phrase"
DEFAULT_RELAY_AGENT_ADDRESS = Identity.from_seed(DEFAULT_RELAY_AGENT_SEED, 0).address


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required for the UXRay Fetch relay.")
    return value


@dataclass(slots=True)
class RelaySettings:
    shared_secret: str
    agentverse_api_key: str
    relay_agent_address: str
    orchestrator_address: str
    relay_agent_seed: str | None = None
    timeout_seconds: float = 170.0
    sync_submit_timeout_seconds: float = 8.0
    poll_interval_seconds: float = 1.0
    agentverse_base_url: str = "https://agentverse.ai"

    @classmethod
    def from_env(cls) -> "RelaySettings":
        _load_env_file(ROOT_ENV_FILE)
        return cls(
            shared_secret=_required_env("FETCH_EVALUATION_API_KEY"),
            agentverse_api_key=_required_env("AGENTVERSE_API_KEY"),
            relay_agent_address=_required_env("FETCH_RELAY_AGENT_ADDRESS"),
            orchestrator_address=_required_env("FETCH_RELAY_ORCHESTRATOR_ADDRESS"),
            relay_agent_seed=os.getenv("FETCH_RELAY_AGENT_SEED", "").strip() or None,
            timeout_seconds=float(os.getenv("FETCH_RELAY_TIMEOUT_SECONDS", "170")),
            sync_submit_timeout_seconds=float(
                os.getenv("FETCH_RELAY_SYNC_SUBMIT_TIMEOUT_SECONDS", "8")
            ),
            poll_interval_seconds=float(os.getenv("FETCH_RELAY_POLL_INTERVAL_SECONDS", "1")),
            agentverse_base_url=os.getenv("FETCH_RELAY_AGENTVERSE_BASE_URL", "https://agentverse.ai").rstrip("/"),
        )


class RelayEvaluateRequest(BaseModel):
    api_key: str
    payload_json: str


class RelayEvaluateResponse(BaseModel):
    status: str
    response_json: str = ""
    error: str | None = None


@dataclass(slots=True)
class BackendProtocolInfo:
    protocol_digest: str
    request_schema_digest: str
    response_schema_digest: str | None = None
    delivery_endpoints: tuple[str, ...] = ()


class AgentverseMailboxClient:
    def __init__(
        self,
        settings: RelaySettings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self._protocol_info: BackendProtocolInfo | None = None
        self._relay_identity: Identity | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.agentverse_api_key}",
            "Content-Type": "application/json",
        }

    def evaluate(self, request: RelayEvaluateRequest) -> RelayEvaluateResponse:
        if request.api_key != self.settings.shared_secret:
            return RelayEvaluateResponse(status="failed", error="Invalid API key.")

        try:
            payload = EvaluateIssuesRequest.model_validate_json(request.payload_json)
        except Exception as exc:
            return RelayEvaluateResponse(status="failed", error=f"Invalid payload_json: {exc}")

        try:
            session = str(uuid.uuid4())
            protocol_info = self._get_backend_protocol_info()
            signed_envelope = self._sign_backend_envelope(session, protocol_info, payload)
            response_envelope = self._submit_for_response(signed_envelope, protocol_info)
            if response_envelope is None:
                response_envelope = self._poll_for_response(session, protocol_info)
            return self._decode_response(response_envelope)
        except Exception as exc:
            return RelayEvaluateResponse(status="failed", error=str(exc))

    def _get_backend_protocol_info(self) -> BackendProtocolInfo:
        if self._protocol_info is not None:
            return self._protocol_info

        agent = self._get_json(
            f"{self.settings.agentverse_base_url}/v1/almanac/agents/{self.settings.orchestrator_address}"
        )
        endpoints = tuple(
            item.get("url")
            for item in (agent.get("endpoints") or [])
            if isinstance(item, dict) and item.get("url")
        )
        protocol_digests = agent.get("protocols") or []
        for digest in protocol_digests:
            manifest = self._get_optional_json(
                f"{self.settings.agentverse_base_url}/v1/almanac/manifests/protocols/{digest}"
            )
            if manifest is None:
                continue
            metadata = manifest.get("metadata") or []
            if isinstance(metadata, dict):
                metadata_items = [metadata]
            else:
                metadata_items = metadata
            names = {item.get("name") for item in metadata_items if isinstance(item, dict)}
            if BACKEND_PROTOCOL_NAME not in names:
                continue
            interactions = manifest.get("interactions") or []
            if not interactions:
                raise ValueError("Backend protocol manifest does not expose any interactions.")
            interaction = interactions[0]
            request_digest = interaction.get("request")
            response_digests = interaction.get("responses") or []
            response_digest = response_digests[0] if response_digests else None
            if not request_digest:
                raise ValueError("Backend protocol manifest is missing the request schema digest.")
            self._protocol_info = BackendProtocolInfo(
                protocol_digest=digest,
                request_schema_digest=request_digest,
                response_schema_digest=response_digest,
                delivery_endpoints=endpoints,
            )
            return self._protocol_info

        raise ValueError(
            f"Could not find published backend protocol '{BACKEND_PROTOCOL_NAME}' on orchestrator "
            f"{self.settings.orchestrator_address}."
        )

    def _sign_backend_envelope(
        self,
        session: str,
        protocol_info: BackendProtocolInfo,
        payload: EvaluateIssuesRequest,
    ) -> dict[str, Any]:
        envelope = Envelope(
            version=1,
            sender=self.settings.relay_agent_address,
            target=self.settings.orchestrator_address,
            session=uuid.UUID(session),
            schema_digest=protocol_info.request_schema_digest,
            protocol_digest=protocol_info.protocol_digest,
        )
        envelope.encode_payload(
            BackendEvaluateEnvelope(
                session=session,
                api_key=self.settings.shared_secret,
                payload_json=payload.model_dump_json(),
            ).model_dump_json()
        )
        envelope.sign(self._get_relay_identity())
        return envelope.model_dump(mode="json")

    def _submit_for_response(
        self,
        signed_envelope: dict[str, Any],
        protocol_info: BackendProtocolInfo,
    ) -> dict[str, Any] | None:
        protocol_info = self._get_backend_protocol_info()
        if not protocol_info.delivery_endpoints:
            raise ValueError("Orchestrator does not publish any delivery endpoints.")
        errors: list[str] = []
        for endpoint in protocol_info.delivery_endpoints:
            try:
                maybe_response = self._post_exchange_envelope(endpoint, signed_envelope, sync=True)
                if maybe_response is not None:
                    return maybe_response
                return None
            except httpx.TimeoutException:
                return None
            except Exception as exc:
                errors.append(f"{endpoint}: {exc}")
        raise ValueError("Failed to submit envelope to orchestrator endpoints. " + "; ".join(errors))

    def _poll_for_response(
        self,
        session: str,
        protocol_info: BackendProtocolInfo,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.settings.timeout_seconds
        last_messages: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            messages = self._get_json(
                f"{self.settings.agentverse_base_url}/v2/agents/{self.settings.relay_agent_address}/mailbox"
            )
            if isinstance(messages, dict):
                mailbox_messages = messages.get("items") or messages.get("messages") or []
            else:
                mailbox_messages = messages
            last_messages = mailbox_messages

            for message in mailbox_messages:
                envelope = message.get("envelope") or {}
                if envelope.get("session") != session:
                    continue
                if envelope.get("sender") != self.settings.orchestrator_address:
                    continue
                if envelope.get("target") != self.settings.relay_agent_address:
                    continue
                if envelope.get("protocol_digest") != protocol_info.protocol_digest:
                    continue
                if (
                    protocol_info.response_schema_digest is not None
                    and envelope.get("schema_digest") != protocol_info.response_schema_digest
                ):
                    continue
                message_uuid = message.get("uuid")
                if message_uuid:
                    self._delete_mailbox_message(message_uuid)
                return envelope

            time.sleep(self.settings.poll_interval_seconds)

        raise TimeoutError(
            f"Timed out waiting for mailbox response for session {session}. "
            f"Last mailbox batch size: {len(last_messages)}"
        )

    def _decode_response(self, envelope: dict[str, Any]) -> RelayEvaluateResponse:
        try:
            decoded_envelope = Envelope.model_validate(envelope)
        except Exception as exc:
            return RelayEvaluateResponse(status="failed", error=f"Invalid mailbox response envelope: {exc}")

        payload = decoded_envelope.decode_payload()
        if not payload:
            return RelayEvaluateResponse(status="failed", error="Mailbox response envelope did not contain a payload.")

        try:
            response = BackendEvaluateResponseEnvelope.model_validate_json(payload)
        except Exception as exc:
            return RelayEvaluateResponse(status="failed", error=f"Invalid mailbox response payload: {exc}")

        if response.status == "completed":
            try:
                EvaluateIssuesResponse.model_validate_json(response.response_json)
            except Exception as exc:
                return RelayEvaluateResponse(status="failed", error=f"Invalid evaluation response_json: {exc}")

        return RelayEvaluateResponse(
            status=response.status,
            response_json=response.response_json,
            error=response.error,
        )

    def _get_json(self, url: str) -> Any:
        with httpx.Client(transport=self.transport, timeout=self.settings.timeout_seconds) as client:
            response = client.get(url, headers=self._headers)
        self._raise_for_status(response)
        return response.json()

    def _get_optional_json(self, url: str) -> Any | None:
        with httpx.Client(transport=self.transport, timeout=self.settings.timeout_seconds) as client:
            response = client.get(url, headers=self._headers)
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        return response.json()

    def _post_json(self, url: str, payload: dict[str, Any]) -> Any:
        with httpx.Client(transport=self.transport, timeout=self.settings.timeout_seconds) as client:
            response = client.post(url, headers=self._headers, json=payload)
        self._raise_for_status(response)
        if not response.content:
            return {}
        return response.json()

    def _post_exchange_envelope(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        sync: bool,
    ) -> dict[str, Any] | None:
        headers = {"content-type": "application/json"}
        if sync:
            headers["x-uagents-connection"] = "sync"
        request_timeout = (
            self.settings.sync_submit_timeout_seconds
            if sync
            else self.settings.timeout_seconds
        )
        with httpx.Client(transport=self.transport, timeout=request_timeout) as client:
            response = client.post(url, headers=headers, json=payload)
        self._raise_for_status(response)
        if not response.content:
            return None
        try:
            parsed = response.json()
        except Exception:
            return None
        if not isinstance(parsed, dict) or "payload" not in parsed:
            return None
        return parsed

    def _delete_mailbox_message(self, message_uuid: str) -> None:
        with httpx.Client(transport=self.transport, timeout=self.settings.timeout_seconds) as client:
            response = client.delete(
                f"{self.settings.agentverse_base_url}/v2/agents/{self.settings.relay_agent_address}/mailbox/{message_uuid}",
                headers=self._headers,
            )
        self._raise_for_status(response)

    def _get_relay_identity(self) -> Identity:
        if self._relay_identity is not None:
            return self._relay_identity

        seed = self.settings.relay_agent_seed
        if not seed and self.settings.relay_agent_address == DEFAULT_RELAY_AGENT_ADDRESS:
            seed = DEFAULT_RELAY_AGENT_SEED
        if not seed:
            raise ValueError(
                "FETCH_RELAY_AGENT_SEED is required for local mailbox signing when the relay agent "
                "was not created from the default scaffold seed."
            )

        identity = Identity.from_seed(seed, 0)
        if identity.address != self.settings.relay_agent_address:
            raise ValueError("FETCH_RELAY_AGENT_SEED does not match FETCH_RELAY_AGENT_ADDRESS.")
        self._relay_identity = identity
        return identity

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = response.text.strip()
            if body:
                raise ValueError(f"{exc}. Response body: {body}") from exc
            raise


def create_app(
    settings: RelaySettings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FastAPI:
    relay_settings = settings or RelaySettings.from_env()
    relay_client = AgentverseMailboxClient(relay_settings, transport=transport)
    app = FastAPI(title="UXRay Fetch Relay")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/evaluate", response_model=RelayEvaluateResponse)
    async def evaluate(request: RelayEvaluateRequest) -> RelayEvaluateResponse:
        return relay_client.evaluate(request)

    return app


def _create_default_app() -> FastAPI:
    try:
        return create_app()
    except ValueError:
        app = FastAPI(title="UXRay Fetch Relay")

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "misconfigured"}

        return app


app = _create_default_app()
