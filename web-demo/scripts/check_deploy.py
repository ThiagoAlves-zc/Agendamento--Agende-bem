"""Verificação pós-deploy (somente leitura; não altera dados).

Uso:
    python scripts/check_deploy.py https://<deployment>.vercel.app
    VERCEL_AUTOMATION_BYPASS_SECRET=... python scripts/check_deploy.py https://...

Sem o segredo de bypass, verifica apenas que a URL está PROTEGIDA (não serve o app).
Com o segredo (Deployment Protection → Protection Bypass for Automation), verifica
também saúde do Streamlit, cabeçalhos de segurança e o handshake do WebSocket.
Código de saída 0 = todas as verificações passaram.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

BYPASS_HEADER = "x-vercel-protection-bypass"
SECURITY_HEADERS = ("strict-transport-security", "x-content-type-options", "x-frame-options")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 15):
    """GET sem seguir redirecionamentos. Retorna (status, cabeçalhos, corpo)."""
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with opener.open(request, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read(4096)
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read(4096)


def ws_url(base: str) -> str:
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/_stcore/stream"


def ws_handshake(base: str, headers: dict[str, str] | None = None, timeout: float = 15) -> tuple[bool, str]:
    """Abre o WebSocket do Streamlit e fecha em seguida. Retorna (abriu, detalhe)."""
    from websockets.sync.client import connect

    try:
        with connect(
            ws_url(base),
            subprotocols=["streamlit"],
            additional_headers=headers or {},
            open_timeout=timeout,
        ) as ws:
            return True, f"subprotocolo={ws.subprotocol}"
    except Exception as exc:  # recusado, 401/403, timeout etc.
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"


def run(base: str, bypass: str | None) -> list[Check]:
    base = base.rstrip("/")
    checks: list[Check] = []

    status, headers, body = http_get(base + "/")
    served_app = status == 200 and b"streamlit" in body.lower()
    checks.append(Check(
        "Sem autenticação, a página NÃO é servida",
        not served_app and status in (401, 403, 302, 303, 307, 308),
        f"HTTP {status} {headers.get('location', '')[:80]}",
    ))
    opened, detail = ws_handshake(base)
    checks.append(Check("Sem autenticação, o WebSocket é recusado", not opened, detail))

    if not bypass:
        checks.append(Check("Verificações autenticadas", True, "ignoradas (sem segredo de bypass)"))
        return checks

    auth = {BYPASS_HEADER: bypass}
    status, headers, body = http_get(base + "/_stcore/health", auth)
    checks.append(Check("Saúde do Streamlit (/_stcore/health)", status == 200 and body.strip() == b"ok",
                        f"HTTP {status}"))
    status, headers, _ = http_get(base + "/", auth)
    missing = [h for h in SECURITY_HEADERS if h not in headers]
    checks.append(Check("Cabeçalhos de segurança", status == 200 and not missing,
                        f"HTTP {status}; ausentes: {missing or 'nenhum'}"))
    opened, detail = ws_handshake(base, auth)
    checks.append(Check("WebSocket autenticado abre", opened, detail))
    reopened, detail = ws_handshake(base, auth)
    checks.append(Check("Reconexão do WebSocket", reopened, detail))
    return checks


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith(("https://", "http://")):
        print(__doc__)
        return 2
    checks = run(sys.argv[1], os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET"))
    for check in checks:
        print(f"[{'OK ' if check.ok else 'FALHA'}] {check.name} — {check.detail}")
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
