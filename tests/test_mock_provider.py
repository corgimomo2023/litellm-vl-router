import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from tests.mock_provider import Handler


@pytest.fixture
def mock_provider():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def post(base_url, path):
    request = Request(
        f"{base_url}{path}",
        data=json.dumps({"model": "mock-model", "messages": []}).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        return json.load(response)


def test_mock_provider_identifies_opencode_go_backend(mock_provider):
    body = post(mock_provider, "/opencode-go/v1/chat/completions")

    assert body["choices"][0]["message"]["content"] == "provider=opencode-go model=mock-model"


def test_mock_provider_identifies_gpt_luna_backend(mock_provider):
    body = post(mock_provider, "/gpt-luna/v1/chat/completions")

    assert body["choices"][0]["message"]["content"] == "provider=gpt-luna model=mock-model"
