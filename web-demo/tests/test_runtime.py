"""Servidor Streamlit real: WebSocket, reinício de instância, persistência e controle de acesso."""
import http.server
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import services
from conftest import DEMO_DAY
from database import connect
from seed import reset_demo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_deploy  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port: int, env: dict) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.address=127.0.0.1", f"--server.port={port}", "--server.headless=true"],
        cwd=APP_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            status, _, body = check_deploy.http_get(base + "/_stcore/health", timeout=2)
            if status == 200 and body.strip() == b"ok":
                return proc
        except OSError:
            pass
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("Streamlit não iniciou")


def stop_server(proc: subprocess.Popen) -> None:
    proc.kill()  # encerramento abrupto, como uma instância reciclada
    proc.wait(timeout=20)


@pytest.fixture
def server_env(open_db, backend, tmp_path):
    env = dict(os.environ)
    env.update(
        STREAMLIT_BROWSER_GATHER_USAGE_STATS="false",
        STREAMLIT_SERVER_COOKIE_SECRET="segredo-de-teste-compartilhado-0123456789",
        STREAMLIT_SERVER_FILE_WATCHER_TYPE="none",
    )
    db = open_db()
    reset_demo(db, DEMO_DAY)
    if backend == "sqlite":
        env.pop("DATABASE_URL", None)
        env["AGENDE_BEM_DB"] = str(tmp_path / "test.db")
    return env, db


def test_websocket_survives_instance_restart_and_data_persists(server_env):
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect as ws_connect

    env, db = server_env
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    proc = start_server(port, env)
    try:
        ok, detail = check_deploy.ws_handshake(base)
        assert ok, detail
        with ws_connect(check_deploy.ws_url(base), subprotocols=["streamlit"], open_timeout=10) as live:
            marcos = next(a for a in services.list_appointments(db) if a.patient_name == "Marcos Vieira")
            services.cancel_appointment(db, marcos.id)

            stop_server(proc)
            with pytest.raises(ConnectionClosed):  # o cliente percebe a queda e deve reconectar
                for _ in range(50):
                    try:
                        live.recv(timeout=0.5)
                    except TimeoutError:
                        continue

        proc = start_server(port, env)  # nova instância, nenhum estado em memória
        ok, detail = check_deploy.ws_handshake(base)
        assert ok, detail
        fresh = connect() if env.get("DATABASE_URL") else connect(env["AGENDE_BEM_DB"])
        assert next(a for a in services.list_appointments(fresh)
                    if a.patient_name == "Marcos Vieira").status == "cancelado"
    finally:
        stop_server(proc)


def test_access_checker_flags_unprotected_deployment(server_env):
    env, _ = server_env
    port = free_port()
    proc = start_server(port, env)
    try:
        checks = check_deploy.run(f"http://127.0.0.1:{port}", bypass=None)
        by_name = {c.name: c for c in checks}
        assert by_name["Sem autenticação, a página NÃO é servida"].ok is False
        assert by_name["Sem autenticação, o WebSocket é recusado"].ok is False
    finally:
        stop_server(proc)


@pytest.mark.parametrize("backend", ["sqlite"])  # não usa banco
def test_access_checker_accepts_protected_deployment(backend):
    class Protected(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Authentication Required")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Protected)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        checks = check_deploy.run(f"http://127.0.0.1:{server.server_address[1]}", bypass=None)
        assert all(c.ok for c in checks), checks
    finally:
        server.shutdown()
