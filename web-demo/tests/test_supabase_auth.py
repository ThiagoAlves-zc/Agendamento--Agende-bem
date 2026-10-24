import time

import pytest

from supabase_auth import AuthError, AuthSession, SupabaseAuth


class Response:
    def __init__(self, status, payload): self.status_code, self._payload = status, payload
    def json(self): return self._payload


class Http:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_login_refresh_and_server_validation_do_not_log_tokens():
    http = Http([
        Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600,
                       "user": {"id": "u1", "email": "admin@example.test"}}),
        Response(200, {"access_token": "next", "refresh_token": "next-refresh", "expires_in": 3600,
                       "user": {"id": "u1", "email": "admin@example.test"}}),
        Response(200, {"id": "u1", "email": "admin@example.test"}),
        Response(200, {}),
    ])
    auth = SupabaseAuth("https://project.supabase.co", "publishable", http)
    session = auth.sign_in("admin@example.test", "not-in-url")
    renewed = auth.refresh(session)
    assert auth.current_user(renewed)["id"] == "u1"
    auth.sign_out(renewed)
    assert all("not-in-url" not in url for _, url, _ in http.calls)
    assert http.calls[2][2]["headers"]["Authorization"] == "Bearer next"
    assert http.calls[3][1].endswith("/auth/v1/logout")


def test_invalid_credentials_and_missing_configuration_are_safe():
    with pytest.raises(AuthError):
        SupabaseAuth().sign_in("a@example.test", "x")
    with pytest.raises(AuthError, match="Credenciais inválidas"):
        SupabaseAuth("https://project.supabase.co", "key", Http([Response(400, {})])).sign_in("a@example.test", "x")


def test_logout_accepts_supabase_no_content_response():
    class NoContent:
        status_code = 204

        def json(self):
            raise ValueError("sem corpo")

    session = AuthSession("access", "refresh", time.time() + 3600, "u1", "admin@example.test")
    auth = SupabaseAuth("https://project.supabase.co", "publishable", Http([NoContent()]))
    auth.sign_out(session)


def test_expiration_is_proactively_detected():
    assert AuthSession("a", "r", time.time() + 10, "u", "e@example.test").expires_soon
