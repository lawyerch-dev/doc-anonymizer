"""极简 OpenAI 兼容客户端(标准库, 适配 llama.cpp 的 llama-server)。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def chat(self, system: str, user: str, temperature: float = 0.0) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.config.disable_thinking:
            # llama.cpp: 关闭 Qwen3.x 的思考模式, 直接出结果
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def health(self) -> bool:
        try:
            url = self.config.base_url.rstrip("/") + "/models"
            with urllib.request.urlopen(url, timeout=5):
                return True
        except (urllib.error.URLError, OSError):
            return False
