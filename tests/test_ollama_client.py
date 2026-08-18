from src.ollama_client import OllamaClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout, headers=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout, "headers": headers})
        if url.endswith("/api/embed"):
            return FakeResponse({"embeddings": [[0.1, 0.2, 0.3]]})
        return FakeResponse({"message": {"content": '{"goal_type":"fat_loss"}'}})


def test_chat_posts_to_ollama_chat_api_and_returns_content():
    http = FakeHttp()
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2", http=http)

    content = client.chat_json_instruction(
        "Extract JSON", "I want fat loss over 8 weeks", require_json=True
    )

    assert content == '{"goal_type":"fat_loss"}'
    assert http.calls[0] == {
        "url": "http://localhost:11434/api/chat",
        "json": {
            "model": "llama3.2",
            "messages": [
                {"role": "system", "content": "Extract JSON"},
                {"role": "user", "content": "I want fat loss over 8 weeks"},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        },
        "timeout": 60,
        "headers": None,
    }


def test_chat_omits_json_mode_for_plain_text_requests():
    http = FakeHttp()
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2", http=http)

    client.chat_json_instruction("Write a short note", "Training went well", require_json=False)

    assert "format" not in http.calls[0]["json"]


def test_chat_uses_configured_request_timeout(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "180")
    http = FakeHttp()
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2", http=http)

    client.chat_json_instruction("Extract JSON", "I slept 7 hours", require_json=True)

    assert http.calls[0]["timeout"] == 180


def test_remote_chat_uses_bearer_auth_and_omits_native_json_mode(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "remote-secret")
    http = FakeHttp()
    client = OllamaClient(base_url="https://ollama.com", model="gpt-oss:20b", http=http)

    client.chat_json_instruction("Extract JSON", "I slept 7 hours", require_json=True)

    assert http.calls[0]["url"] == "https://ollama.com/api/chat"
    assert http.calls[0]["headers"] == {"Authorization": "Bearer remote-secret"}
    assert "format" not in http.calls[0]["json"]


def test_remote_embedding_uses_bearer_auth(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "remote-secret")
    http = FakeHttp()
    client = OllamaClient(base_url="https://ollama.com", embed_model="embeddinggemma", http=http)

    client.embed("Badminton footwork")

    assert http.calls[0]["headers"] == {"Authorization": "Bearer remote-secret"}


def test_hybrid_client_uses_remote_chat_and_local_embeddings(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "remote-secret")
    monkeypatch.setenv("OLLAMA_EMBED_BASE_URL", "http://ollama:11434")
    http = FakeHttp()
    client = OllamaClient(base_url="https://ollama.com", model="gpt-oss:20b", http=http)

    client.chat_json_instruction("Extract JSON", "I slept 7 hours", require_json=True)
    client.embed("Badminton footwork")

    assert http.calls[0]["url"] == "https://ollama.com/api/chat"
    assert http.calls[0]["headers"] == {"Authorization": "Bearer remote-secret"}
    assert "format" not in http.calls[0]["json"]
    assert http.calls[1]["url"] == "http://ollama:11434/api/embed"
    assert http.calls[1]["headers"] is None


def test_embed_posts_to_ollama_embed_api_and_returns_first_embedding():
    http = FakeHttp()
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.2",
        embed_model="embeddinggemma",
        http=http,
    )

    embedding = client.embed("I want upper body strength for badminton")

    assert embedding == [0.1, 0.2, 0.3]
    assert http.calls[0]["url"] == "http://localhost:11434/api/embed"
    assert http.calls[0]["json"] == {
        "model": "embeddinggemma",
        "input": "I want upper body strength for badminton",
    }
