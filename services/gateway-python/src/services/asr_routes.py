import asyncio
import base64
import os
import uuid
from typing import Any, Dict

import httpx
from flask import Blueprint, jsonify, request

bp_asr = Blueprint("dialog", __name__)

DIALOG_ENGINE_URL = os.environ.get("DIALOG_ENGINE_URL", "http://dialog-engine:8100")
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=5.0, read=60.0, write=10.0)


def _build_url(path: str) -> str:
    return f"{DIALOG_ENGINE_URL.rstrip('/')}{path}"


def _guess_content_type(provided: str | None, filename: str | None) -> str:
    if provided and isinstance(provided, str) and provided.strip():
        return provided.strip()
    if not filename:
        return "audio/wav"
    suffix = os.path.splitext(filename)[1].lower()
    mapping = {
        ".webm": "audio/webm",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
    }
    return mapping.get(suffix, "audio/wav")


async def _invoke_dialog_engine(payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(_build_url("/chat/audio"), json=payload)
        resp.raise_for_status()
        return resp.json()


@bp_asr.route("/asr", methods=["POST"])
def proxy_audio_chat():
    """Compatibility endpoint: forward legacy /asr requests to dialog-engine."""
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "invalid_json"}), 400

    session_id = str(data.get("sessionId") or uuid.uuid4())
    audio_b64 = data.get("audio")
    source_path = data.get("path")

    if not audio_b64:
        if not source_path or not isinstance(source_path, str):
            return jsonify({"error": "audio_or_path_required"}), 400
        if not os.path.isabs(source_path):
            return jsonify({"error": "path_must_be_absolute"}), 400
        try:
            with open(source_path, "rb") as fh:
                audio_b64 = base64.b64encode(fh.read()).decode("ascii")
        except FileNotFoundError:
            return jsonify({"error": "file_not_found"}), 404
        except Exception as exc:
            return jsonify({"error": f"read_failed:{exc}"}), 500

    content_type = _guess_content_type(data.get("contentType"), source_path)
    payload: Dict[str, Any] = {
        "sessionId": session_id,
        "audio": audio_b64,
        "contentType": content_type,
    }

    lang = data.get("lang") or (data.get("options") or {}).get("lang")
    if lang:
        payload["lang"] = lang
    meta = data.get("meta") or {}
    if meta:
        payload["meta"] = meta

    try:
        result = asyncio.run(_invoke_dialog_engine(payload))
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text or exc.response.reason_phrase
        return jsonify({"error": "dialog_engine_error", "detail": detail}), exc.response.status_code
    except Exception as exc:  # pragma: no cover - defensive fallback
        return jsonify({"error": "dialog_engine_unavailable", "detail": str(exc)}), 502

    return jsonify(result)
