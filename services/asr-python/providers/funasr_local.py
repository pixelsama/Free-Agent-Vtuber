from __future__ import annotations

import os
from typing import Optional, Dict, Any

from .asr_provider import BaseASRProvider, ASRResult


class FunASRLocalProvider(BaseASRProvider):
    """
    基于 FunASR / ModelScope 的本地离线 ASR Provider（优先中文通用模型）。
    首版仅返回整体文本，不输出词级时间戳或说话人分离结果。
    """

    def __init__(self, model_id: str, device: str = "cpu", cache_dir: Optional[str] = None) -> None:
        """
        :param model_id: modelscope 上的模型标识或本地模型目录
        :param device: "cpu" 或 "cuda"
        :param cache_dir: 模型缓存目录（可选）。不传则走默认 ~/.cache/modelscope
        """
        self.model_id = model_id
        self.device = device
        self.cache_dir = cache_dir

        # 延迟导入，避免在未安装 funasr/modelscope 的环境下启动即报错
        try:
            # FunASR 典型入口：ASRModel（也有基于 modelscope.pipeline 的方式）
            from funasr import AutoModel  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "FunASR not available. Please ensure 'funasr' is installed. "
                f"Underlying import error: {e}"
            )

        # 构建加载参数
        load_kwargs: Dict[str, Any] = {}
        if cache_dir:
            # ModelScope 与 FunASR 均遵循环境变量或显式参数控制缓存目录
            # 这里显式传递给 AutoModel（如未来版本不支持，可退回设置环境变量）
            os.makedirs(cache_dir, exist_ok=True)
            load_kwargs["cache_dir"] = cache_dir

        try:
            # AutoModel 会根据 model_id 解析最佳配置并下载到缓存目录
            # 注意：不同 FunASR 版本 API 可能略有差异，如遇不兼容请据实调整
            self._backend = AutoModel(model=self.model_id, **load_kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to load FunASR model '{self.model_id}': {e}")

    async def transcribe_file(
        self,
        path: str,
        lang: Optional[str],
        timestamps: bool,
        diarization: bool,
    ) -> ASRResult:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"audio file not found: {path}")

        # FunASR 当前以同步推理为主，这里在异步环境中直接调用；
        # 如果后续需要可将其放入线程池执行以避免阻塞事件循环。
        try:
            # 典型调用：返回包含文本的字典或对象
            # 常见字段可能为 {"text": "..."} 或 [{"text": "..."}]，视模型与版本而定
            # 这里做兼容解析，保证返回 str 文本
            result = self._backend.generate(input=path, device=self.device)  # type: ignore[attr-defined]

            text = None
            if isinstance(result, dict):
                text = result.get("text") or result.get("raw_text") or result.get("sentence")
            elif isinstance(result, list) and result:
                item = result[0]
                if isinstance(item, dict):
                    text = item.get("text") or item.get("raw_text") or item.get("sentence")
                elif isinstance(item, str):
                    text = item
            elif isinstance(result, str):
                text = result

            if not text:
                # 兜底：尝试转成字符串
                text = str(result)

            return ASRResult(
                text=text,
                words=[],  # 首版仅整体文本
                lang=(lang or "zh"),
                provider_meta={"provider": "funasr_local", "model": self.model_id},
            )
        except Exception as e:
            raise RuntimeError(f"FunASR transcription failed: {e}")
