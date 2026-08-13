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

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
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
        },
        "timeout": 60,
    }


def test_chat_omits_json_mode_for_plain_text_requests():
    http = FakeHttp()
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2", http=http)

    client.chat_json_instruction("Write a short note", "Training went well", require_json=False)

    assert "format" not in http.calls[0]["json"]


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
