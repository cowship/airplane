# simulation/engine.py
"""
탑승 시뮬레이션 코어 루프.
AircraftBase + QueueManager를 받아 모든 승객이 착석할 때까지 틱을 돌린다.
다중 채널(통로) 병렬 처리를 지원한다.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from collections import deque

import config
from aircraft.base import AircraftBase
from boarding.queue_model import QueueManager

if TYPE_CHECKING:
    from passenger import Passenger


def run_boarding(
    airplane: AircraftBase,
    queue_manager: QueueManager,
    total_passengers: int,
) -> int:
    """
    Returns
    -------
    int
        탑승 완료까지 소요된 틱 수. MAX_TICKS 초과 시 -1.
    """
    seated = 0
    ticks  = 0
    channels = airplane.channels

    # 시작 전: 전체 큐를 채널별로 분리 (순서 유지)
    ch_queues: list[deque[Passenger]] = [deque() for _ in channels]
    while True:
        p = queue_manager.pop_next()
        if p is None:
            break
        for idx, ch in enumerate(channels):
            if p.target_seat in ch.seat_cols:
                ch_queues[idx].append(p)
                break

    while seated < total_passengers:
        ticks += 1
        if ticks > config.MAX_TICKS:
            return -1

        # ── 1) 모든 채널 통로 내 승객 행동 (뒤 → 앞) ──────────
        for ch in channels:
            aisle = ch.aisle
            for pos in range(airplane.num_rows, 0, -1):
                p = aisle.cells[pos]
                if p is None:
                    continue
                prev = p.state
                p.act(airplane)
                if prev != "seated" and p.state == "seated":
                    seated += 1

        # ── 2) 채널별 입구 처리 ────────────────────────────────
        for idx, ch in enumerate(channels):
            aisle = ch.aisle
            entry = ch.entrance_row
            if aisle.cells[entry] is None and ch_queues[idx]:
                next_p: Passenger = ch_queues[idx].popleft()
                aisle.cells[entry] = next_p
                next_p.current_pos = entry
                next_p.state       = "walking"

    return ticks