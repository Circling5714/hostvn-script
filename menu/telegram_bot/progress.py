"""Thanh tien trinh dong cho bot.

Phan lon tac vu la subprocess blocking (khong bao % that) -> dung thanh tien trinh
TIEM CAN: chay muot tien toi ~96% trong luc cho, khi tac vu xong thi nhay 100%.
- run(edit, title, coro, ...): hien thanh dong trong khi await coro, tra ket qua coro.
- edit: async callable edit(text) -> sua tin nhan dang animate.
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Awaitable, Callable, Optional

FILL = "▰"
EMPTY = "▱"


def bar(pct: float, width: int = 14) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100 * width))
    return f"{FILL * filled}{EMPTY * (width - filled)} {int(round(pct))}%"


def _pct(elapsed: float, est: float) -> float:
    # tiem can toi 96%: nhanh luc dau, cham dan; +0.5s de khung dau khong phai 0%
    return min(96.0, 100.0 * (1.0 - math.exp(-(elapsed + 0.5) / max(1.0, est))))


async def _animate(edit: Callable[[str], Awaitable[None]], title: str,
                   stop: asyncio.Event, est: float,
                   stages: Optional[list[tuple[float, str]]]) -> None:
    start = time.monotonic()
    last = None
    while not stop.is_set():
        elapsed = time.monotonic() - start
        pct = _pct(elapsed, est)
        head = title
        if stages:
            for thr, txt in stages:
                if pct >= thr:
                    head = txt
        text = f"{head}\n<code>{bar(pct)}</code>"
        if text != last:
            try:
                await edit(text)
            except Exception:  # noqa: BLE001 - loi sua tin (rate/khong doi) bo qua
                pass
            last = text
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.1)
        except asyncio.TimeoutError:
            pass


async def run(edit: Callable[[str], Awaitable[None]], title: str, coro: Awaitable,
              est: float = 5.0, stages: Optional[list[tuple[float, str]]] = None):
    """Hien thanh tien trinh dong trong khi await coro. Tra ket qua cua coro."""
    stop = asyncio.Event()
    anim = asyncio.create_task(_animate(edit, title, stop, est, stages))
    try:
        return await coro
    finally:
        stop.set()
        try:
            await anim
        except Exception:  # noqa: BLE001
            pass


async def done(edit: Callable[[str], Awaitable[None]], title: str) -> None:
    """Ve thanh 100% (dung khi muon chot 1 nhip truoc khi hien ket qua)."""
    try:
        await edit(f"{title}\n<code>{bar(100)}</code>")
    except Exception:  # noqa: BLE001
        pass
