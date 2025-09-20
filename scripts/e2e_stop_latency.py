#!/usr/bin/env python3
"""
E2E STOP latency benchmark for M2 audio streaming.

Measures two latencies across multiple runs:
- stop_ack_latency_ms: time from sending STOP (HTTP) to receiving CONTROL STOP_ACK on WS
- last_chunk_latency_ms: time from sending STOP to the last audio chunk observed on WS

Usage (defaults target local dev):
  python scripts/e2e_stop_latency.py \
    --gateway http://localhost:8000 \
    --dialog  http://localhost:8100 \
    --runs 10 \
    --start-delay-ms 1500 \
    --chunk-delay-ms 250 \
    --chunk-count 200 \
    --quiet-ms 300

Requires: websockets, httpx
  pip install websockets httpx
"""
import argparse
import asyncio
import contextlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import websockets


@dataclass
class RunResult:
    session_id: str
    stop_ack_latency_ms: Optional[float]
    last_chunk_latency_ms: Optional[float]


def percentile(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


async def one_run(
    gateway_base: str,
    dialog_base: str,
    start_delay_ms: int,
    chunk_delay_ms: int,
    chunk_count: int,
    quiet_ms: int,
) -> RunResult:
    session_id = str(uuid.uuid4())
    gateway_base = gateway_base.rstrip("/")
    dialog_base = dialog_base.rstrip("/")

    def _http_to_ws(url: str) -> str:
        parsed = urlparse(url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunparse(parsed._replace(scheme=scheme))

    ws_base = _http_to_ws(gateway_base)
    ws_url = urljoin(ws_base + "/", f"ws/output/{session_id}")
    stop_url = urljoin(gateway_base + "/", "control/stop")
    mock_url = urljoin(dialog_base + "/", "tts/mock")

    last_msg_at: Optional[float] = None
    stop_sent_at: Optional[float] = None
    stop_ack_at: Optional[float] = None
    stop_ack_event = asyncio.Event()
    connected_event = asyncio.Event()

    async def receiver():
        nonlocal last_msg_at, stop_ack_at
        try:
            async with websockets.connect(ws_url) as ws:
                connected_event.set()
                async for msg in ws:
                    now = time.perf_counter()
                    # bytes => audio frame
                    if isinstance(msg, (bytes, bytearray)):
                        last_msg_at = now
                        continue
                    # text => parse json and inspect type
                    try:
                        data = json.loads(msg)
                    except Exception:
                        continue
                    mtype = str(data.get("type", "")).lower()
                    if mtype == "audio_chunk":
                        last_msg_at = now
                    elif mtype == "control":
                        action = str(data.get("action", "")).upper()
                        if action == "STOP_ACK":
                            stop_ack_at = now
                            stop_ack_event.set()
        except asyncio.CancelledError:
            # normal shutdown path
            if not connected_event.is_set():
                connected_event.set()
            return
        except Exception:
            if not connected_event.is_set():
                connected_event.set()
            return

    async def trigger_and_stop():
        nonlocal stop_sent_at
        # Use generous timeout; /tts/mock now returns immediately, but be safe
        # Provide a default plus explicit connect override to satisfy httpx requirements
        timeout = httpx.Timeout(30.0, connect=5.0, read=30.0, write=30.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            # trigger mock stream
            payload = {
                "sessionId": session_id,
                "text": "benchmark-stream",
                "chunkDelayMs": int(chunk_delay_ms),
                "chunkCount": int(chunk_count),
            }
            r = await client.post(mock_url, json=payload)
            r.raise_for_status()
            await asyncio.sleep(start_delay_ms / 1000.0)
            stop_sent_at = time.perf_counter()
            r2 = await client.post(stop_url, json={"sessionId": session_id})
            r2.raise_for_status()

    # run both tasks
    recv_task = asyncio.create_task(receiver())
    try:
        try:
            await asyncio.wait_for(connected_event.wait(), timeout=5.0)
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"failed to connect to gateway output WS at {ws_url}"
            ) from exc
        if recv_task.done():
            exc = recv_task.exception()
            if exc:
                raise RuntimeError(f"output websocket error: {exc}") from exc
        await trigger_and_stop()
        # wait for STOP_ACK or quiet period after stop
        waited = 0.0
        step = 0.02
        while True:
            if stop_ack_event.is_set():
                break
            if stop_sent_at is not None and last_msg_at is not None:
                if (time.perf_counter() - last_msg_at) * 1000.0 >= quiet_ms:
                    break
            await asyncio.sleep(step)
            waited += step
            if waited > 10.0:  # safety timeout
                break
    finally:
        recv_task.cancel()
        try:
            await recv_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    if last_msg_at is None:
        raise RuntimeError(
            f"session {session_id}: Mock TTS produced no audio chunks; ensure SYNC_TTS_STREAMING=true on dialog-engine/output-handler and that dialog-engine reaches OUTPUT_INGEST_WS_URL."
        )

    # compute latencies
    ack_ms = None
    last_ms = None
    if stop_sent_at and stop_ack_at:
        ack_ms = (stop_ack_at - stop_sent_at) * 1000.0
    if stop_sent_at and last_msg_at:
        last_ms = (last_msg_at - stop_sent_at) * 1000.0
    return RunResult(session_id=session_id, stop_ack_latency_ms=ack_ms, last_chunk_latency_ms=last_ms)


async def main():
    parser = argparse.ArgumentParser(description="E2E STOP latency benchmark")
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--dialog", default="http://localhost:8100")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--start-delay-ms", type=int, default=1500)
    parser.add_argument("--chunk-delay-ms", type=int, default=250)
    parser.add_argument("--chunk-count", type=int, default=200)
    parser.add_argument("--quiet-ms", type=int, default=300)
    args = parser.parse_args()

    results: List[RunResult] = []
    for i in range(args.runs):
        try:
            res = await one_run(
                gateway_base=args.gateway,
                dialog_base=args.dialog,
                start_delay_ms=args.start_delay_ms,
                chunk_delay_ms=args.chunk_delay_ms,
                chunk_count=args.chunk_count,
                quiet_ms=args.quiet_ms,
            )
        except RuntimeError as exc:
            print(f"run {i+1}/{args.runs} failed: {exc}")
            return
        results.append(res)

        def _fmt(value: Optional[float]) -> str:
            return f"{value:.1f}" if value is not None else "--"

        print(
            f"run {i+1}/{args.runs} sid={res.session_id[:8]} stop_ack={_fmt(res.stop_ack_latency_ms)}ms "
            f"last_chunk={_fmt(res.last_chunk_latency_ms)}ms"
        )

    acks = [r.stop_ack_latency_ms for r in results if r.stop_ack_latency_ms is not None]
    lasts = [r.last_chunk_latency_ms for r in results if r.last_chunk_latency_ms is not None]
    print("\nSummary:")
    if acks:
        print(
            f"STOP_ACK latency: p50={percentile(acks,50):.1f}ms p95={percentile(acks,95):.1f}ms n={len(acks)}"
        )
    else:
        print("STOP_ACK latency: no ACKs observed")
    if lasts:
        print(
            f"Last-chunk latency: p50={percentile(lasts,50):.1f}ms p95={percentile(lasts,95):.1f}ms n={len(lasts)}"
        )
    else:
        print("Last-chunk latency: no chunks observed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
