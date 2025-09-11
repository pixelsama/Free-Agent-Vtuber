import os
import json
import uuid
from typing import Any, Dict

from flask import Blueprint, request, jsonify
from redis.asyncio import Redis

bp_asr = Blueprint("asr", __name__)

# 读取简单配置（与 gateway 的 config.json 保持一致风格，如无则使用默认）
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
ASR_TASKS_QUEUE = os.environ.get("ASR_TASKS_QUEUE", "asr_tasks")

# 懒加载一个全局异步 Redis 客户端（Flask 本身是同步栈，这里仅用于简单入队）
_redis_client: Redis | None = None


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return _redis_client


@bp_asr.route("/asr", methods=["POST"])
def create_asr_task():
    """
    MVP: 仅接受已存在的本地 WAV 文件绝对路径，把任务写入 Redis list 队列，返回 task_id
    请求 JSON:
    {
      "path": "/abs/path/to/file.wav",
      "options": {"lang":"zh","timestamps":true}
    }
    """
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    path = data.get("path")
    options = data.get("options") or {}

    if not path or not isinstance(path, str):
        return jsonify({"error": "path is required"}), 400

    # 要求绝对路径（MVP）
    if not os.path.isabs(path):
        return jsonify({"error": "path must be absolute"}), 400

    # 不强制检查文件是否存在（避免容器间路径不一致导致阻断），但建议存在时更好
    task_id = str(uuid.uuid4())

    msg = {
        "task_id": task_id,
        "audio": {
            "type": "file",
            "path": path,
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1
        },
        "options": {
            "lang": options.get("lang", "zh"),
            "timestamps": bool(options.get("timestamps", True)),
            "diarization": bool(options.get("diarization", False))
        },
        "meta": {
            "source": "gateway",
        }
    }

    # Flask 同步视图内调用异步 Redis：使用 asyncio.run 会创建/关闭事件循环；
    # 这里入队一次成本可接受，若高并发可以改为后台任务或使用同步 redis 客户端。
    import asyncio
    asyncio.run(get_redis().lpush(ASR_TASKS_QUEUE, json.dumps(msg, ensure_ascii=False)))

    # 202 Accepted 也可，这里返回 200 便于前端处理
    return jsonify({"task_id": task_id}), 200
