"""Cliente servidor para Supabase Auth, sem persistir tokens em URL ou logs."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests


class AuthError(RuntimeError):
    """Erro seguro para apresentação ao usuário, sem corpo de resposta sensível."""


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    expires_at: float
    user_id: str
    email: str

    @property
    def expires_soon(self) -> bool:
        return self.expires_at <= time.time() + 60


class SupabaseAuth:
    """API oficial Auth via HTTP; chaves permanecem no processo Streamlit."""

    def __init__(self, url: str | None = None, publishable_key: str | None = None, session=None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = publishable_key or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        self.http = session or requests.Session()

    @property
    def configured(self) -> bool:
        return self.url.startswith("https://") and bool(self.key)

    def _headers(self, token: str | None = None) -> dict[str, str]:
        if not self.configured:
            raise AuthError("Autenticação não está configurada neste ambiente.")
        headers = {"apikey": self.key, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, method: str, path: str, *, payload=None, token=None):
        try:
            response = self.http.request(method, self.url + path, headers=self._headers(token), json=payload, timeout=10)
        except requests.RequestException as exc:
            raise AuthError("Não foi possível validar sua sessão. Tente novamente.") from exc
        if response.status_code >= 400:
            raise AuthError("Credenciais inválidas ou sessão expirada.")
        # O endpoint de logout do GoTrue responde com 204 No Content após
        # revogar a sessão. Tratar sucesso sem corpo evita apresentar um
        # falso erro de sessão na interface.
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise AuthError("Resposta inválida do serviço de autenticação.") from exc

    @staticmethod
    def _session(payload: dict) -> AuthSession:
        user = payload.get("user") or {}
        access, refresh = payload.get("access_token"), payload.get("refresh_token")
        if not access or not refresh or not user.get("id") or not user.get("email"):
            raise AuthError("Sessão inválida.")
        return AuthSession(access, refresh, time.time() + int(payload.get("expires_in", 0)),
                           str(user["id"]), str(user["email"]))

    def sign_in(self, email: str, password: str) -> AuthSession:
        payload = self._request("POST", "/auth/v1/token?grant_type=password", payload={"email": email, "password": password})
        return self._session(payload)

    def refresh(self, session: AuthSession) -> AuthSession:
        payload = self._request("POST", "/auth/v1/token?grant_type=refresh_token", payload={"refresh_token": session.refresh_token})
        return self._session(payload)

    def current_user(self, session: AuthSession) -> dict:
        return self._request("GET", "/auth/v1/user", token=session.access_token)

    def sign_out(self, session: AuthSession) -> None:
        """Revoga a sessão no Auth antes de remover o estado local."""
        self._request("POST", "/auth/v1/logout", token=session.access_token, payload={})

    def request_password_reset(self, email: str, redirect_to: str) -> None:
        # A resposta é intencionalmente uniforme para evitar enumeração de contas.
        self._request("POST", "/auth/v1/recover", payload={"email": email, "redirect_to": redirect_to})
