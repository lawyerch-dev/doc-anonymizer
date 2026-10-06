"""极简 OpenAI 兼容客户端(标准库, 适配 llama.cpp 的 llama-server)。

这个子包 + `detectors/llm_ner.py` 就是"本地大模型引擎", 只依赖 `docanon.contract`,
所以可以整块搬到别的项目里。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """引擎自己的参数, 不是 app 的配置类。"""

    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "qwen3.8-4b"
    timeout: int = 120
    chunk_size: int = 1000
    disable_thinking: bool = True


class LLMError(RuntimeError):
    """LLM 引擎没答上来(服务没起、超时、返回不像样)。

    这类失败不能吞掉: 一次没答上来就返回空, 等于一份"零命中"的文档被当成已脱敏。
    """


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
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except OSError as exc:
            raise LLMError(f"{url} 调不通: {exc}") from exc
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMError(f"{url} 返回的不是预期的 JSON: {exc}") from exc

    def health(self) -> bool:
        try:
            url = self.config.base_url.rstrip("/") + "/models"
            with urllib.request.urlopen(url, timeout=5):
                return True
        except (urllib.error.URLError, OSError):
            return False
