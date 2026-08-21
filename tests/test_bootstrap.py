import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.bootstrap import BootstrapError, bootstrap


class FakeLiteLLMHandler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        type(self).requests.append((self.path, self.headers.get("authorization"), payload))
        responses = {
            "/user/new": {"user_id": "user-123"},
            "/team/new": {"team_id": "team-456"},
            "/key/generate": {"key": "sk-created-once", "key_name": "example-key"},
        }
        if self.path not in responses:
            self.send_error(404)
            return
        body = json.dumps(responses[self.path]).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


@pytest.fixture
def fake_litellm():
    FakeLiteLLMHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeLiteLLMHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_bootstrap_creates_user_team_and_allowlisted_virtual_key(fake_litellm):
    output = io.StringIO()

    result = bootstrap(fake_litellm, "master-secret", output=output)

    assert result == {
        "user_id": "user-123",
        "team_id": "team-456",
        "virtual_key": "sk-created-once",
    }
    assert [request[0] for request in FakeLiteLLMHandler.requests] == [
        "/user/new",
        "/team/new",
        "/key/generate",
    ]
    assert all(request[1] == "Bearer master-secret" for request in FakeLiteLLMHandler.requests)

    user_payload = FakeLiteLLMHandler.requests[0][2]
    team_payload = FakeLiteLLMHandler.requests[1][2]
    key_payload = FakeLiteLLMHandler.requests[2][2]
    assert user_payload["max_budget"] == 25
    assert user_payload["budget_duration"] == "30d"
    assert user_payload["auto_create_key"] is False
    assert team_payload["models"] == ["DeepSeek-v4-vl"]
    assert team_payload["members_with_roles"] == [
        {"user_id": "user-123", "role": "user"}
    ]
    assert "members" not in team_payload
    assert team_payload["max_budget"] == 100
    assert key_payload["models"] == ["DeepSeek-v4-vl"]
    assert key_payload["user_id"] == "user-123"
    assert key_payload["team_id"] == "team-456"
    assert key_payload["max_budget"] == 25

    printed = output.getvalue()
    assert "user-123" in printed
    assert "team-456" in printed
    assert "sk-created-once" in printed


def test_bootstrap_does_not_print_key_when_key_creation_fails(fake_litellm, monkeypatch):
    original = FakeLiteLLMHandler.do_POST

    def fail_key(self):
        if self.path == "/key/generate":
            body = b'{"error":"failed"}'
            self.send_response(500)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        original(self)

    monkeypatch.setattr(FakeLiteLLMHandler, "do_POST", fail_key)
    output = io.StringIO()

    with pytest.raises(BootstrapError, match="/key/generate"):
        bootstrap(fake_litellm, "master-secret", output=output)

    assert "virtual key" not in output.getvalue().lower()
    assert "sk-" not in output.getvalue()
