import asyncio
import random
from typing import AsyncGenerator, Dict, Any


class ChatService:
    """
    Minimal streaming chat for M1.
    - No external LLM dependency; generates a friendly template reply.
    - Streams by word with small delays to simulate tokenization.
    - Keeps last_token_count for metrics.
    """

    def __init__(self) -> None:
        self.last_token_count: int = 0

    async def stream_reply(self, session_id: str, user_text: str, meta: Dict[str, Any] | None = None) -> AsyncGenerator[str, None]:
        """
        Produce a simple, deterministic reply and stream it word-by-word.
        In later milestones, replace with real LLM streaming.
        """
        meta = meta or {}
        # A simple styled reply; keep it friendly and short for demo
        base = self._craft_reply(user_text=user_text, lang=(meta.get("lang") or "zh"))
        words = base.split()
        self.last_token_count = len(words)

        # Simulate token emission with small jitter
        for w in words:
            await asyncio.sleep(0.02 + random.random() * 0.03)
            yield w + (" " if not w.endswith("\n") else "")

    def _craft_reply(self, user_text: str, lang: str) -> str:
        if lang.lower().startswith("zh"):
            return (
                f"你说「{user_text.strip()}」，这很有意思！我在这儿，随时可以继续聊聊。"
                " 如果你愿意，也可以告诉我你现在在做什么～"
            )
        # Fallback EN
        return (
            f"You said: '{user_text.strip()}'. That sounds interesting! I'm here to chat whenever you like. "
            "Feel free to share what you're up to!"
        )

