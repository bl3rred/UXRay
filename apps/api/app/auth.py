from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    user_id: str | None = None
    user_email: str | None = None
    guest_session_id: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_id)

    @property
    def is_guest(self) -> bool:
        return bool(self.guest_session_id) and not self.user_id


class SupabaseAuthService:
    def __init__(
        self,
        supabase_url: str | None,
        publishable_key: str | None,
        client: httpx.Client | None = None,
    ) -> None:
        self.supabase_url = (supabase_url or "").rstrip("/")
        self.publishable_key = publishable_key or ""
        self._client = client or httpx.Client(timeout=10.0)

    @property
    def enabled(self) -> bool:
        return bool(self.supabase_url and self.publishable_key)

    def close(self) -> None:
        self._client.close()

    def get_user(self, access_token: str) -> AuthenticatedUser | None:
        if not self.enabled:
            return None

        response = self._client.get(
            f"{self.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": self.publishable_key,
            },
        )

        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            return None

        response.raise_for_status()
        payload = response.json()
        user_id = payload.get("id")
        if not user_id:
            return None

        return AuthenticatedUser(
            id=str(user_id),
            email=payload.get("email"),
        )


def resolve_request_identity(request: Request) -> RequestIdentity:
    authorization = request.headers.get("Authorization", "").strip()
    auth_service: SupabaseAuthService | None = getattr(request.app.state, "auth_service", None)

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )

        if not auth_service or not auth_service.enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Supabase auth is not configured on the backend",
            )

        user = auth_service.get_user(token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Supabase access token",
            )

        return RequestIdentity(user_id=user.id, user_email=user.email)

    guest_session_id = request.headers.get("X-Guest-Session", "").strip()
    if guest_session_id:
        return RequestIdentity(guest_session_id=guest_session_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication or guest session is required",
    )
