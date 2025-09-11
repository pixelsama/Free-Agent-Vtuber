import os
import json
from typing import Any, Dict, Optional

import httpx

# 轻量占位实现：读取本地 wav 文件并调用 OpenAI Whisper transcriptions API（可选）
# 受 OPENAI_API_KEY 控制，未设置时抛出异常以便测试中跳过或切换到 FakeProvider

class OpenAIWhisperProvider:
    def __init__(self, api_key_env: str = "OPENAI_API_KEY", base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")
        self.api_key = os.getenv(api_key_env)  # 若为 None，将在调用时报错

    async def transcribe_file(
        self, path: str, lang: Optional[str], timestamps: bool, diarization: bool
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(f"Missing API key in env: {self.api_key_env}")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        url = f"{self.base_url}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # OpenAI Whisper API 典型参数
        # model: "whisper-1"（或其他可用模型名）
        # language: 可传 "zh" 或 None
        # response_format: "json"
        # temperature / timestamp_granularities 可选
        form = {
            "model": (None, "whisper-1"),
            "response_format": (None, "json"),
        }
        if lang:
            form["language"] = (None, lang)

        # 注意：OpenAI 官方 API 用 multipart/form-data 传文件
        files = {
            "file": (os.path.basename(path), open(path, "rb"), "audio/wav"),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, files=files, data=form)
            resp.raise_for_status()
            data = resp.json()

        text = data.get("text", "")
        # 简化：不提供词级时间戳（需要更复杂参数或后处理）
        return {
            "text": text,
            "words": [],
            "lang": lang or data.get("language"),
            "provider_meta": {"provider": "openai_whisper"},
        }
