import os

import requests


class OllamaClient:
    def __init__(
        self,
        base_url=None,
        model=None,
        embed_model=None,
        http=requests,
        timeout=60,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or "llama3.2"
        self.embed_model = embed_model or os.getenv("OLLAMA_EMBED_MODEL") or "embeddinggemma"
        self.http = http
        self.timeout = timeout

    def chat_json_instruction(self, instruction, user_text, *, require_json=True):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
        }
        if require_json:
            payload["format"] = "json"
        response = self.http.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def embed(self, text):
        response = self.http.post(
            f"{self.base_url}/api/embed",
            json={"model": self.embed_model, "input": text},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]
