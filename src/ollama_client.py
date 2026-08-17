import os

import requests


class OllamaClient:
    def __init__(
        self,
        base_url=None,
        model=None,
        embed_model=None,
        http=requests,
        timeout=None,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or "llama3.2"
        self.embed_model = embed_model or os.getenv("OLLAMA_EMBED_MODEL") or "embeddinggemma"
        self.embed_base_url = (
            os.getenv("OLLAMA_EMBED_BASE_URL") or self.base_url
        ).rstrip("/")
        self.http = http
        self.timeout = timeout if timeout is not None else int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        self.api_key = os.getenv("OLLAMA_API_KEY")
        self.embed_api_key = os.getenv("OLLAMA_EMBED_API_KEY")
        if self.embed_api_key is None and self.embed_base_url == self.base_url:
            self.embed_api_key = self.api_key
        self.is_direct_cloud = self.base_url.lower() == "https://ollama.com"

    def chat_json_instruction(self, instruction, user_text, *, require_json=True):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        if require_json and not self.is_direct_cloud:
            payload["format"] = "json"
        response = self._post("/api/chat", payload, base_url=self.base_url, api_key=self.api_key)
        response.raise_for_status()
        return response.json()["message"]["content"]

    def embed(self, text):
        response = self._post(
            "/api/embed",
            {"model": self.embed_model, "input": text},
            base_url=self.embed_base_url,
            api_key=self.embed_api_key,
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]

    def _post(self, path, payload, *, base_url, api_key):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        return self.http.post(
            f"{base_url}{path}",
            json=payload,
            timeout=self.timeout,
            headers=headers,
        )
