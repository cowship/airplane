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
    channel_weights: list[float] | None = None,
) -> int:
    """
    Returns
    -------
    int
        탑승 완료까지 소요된 틱 수. MAX_TICKS 초과 시 -1.

    Parameters
    ----------
    channel_weights : optional
        채널별 주입 가중치 (예: FlyingWing WeightedBySeat → [75,84,84,75]).
        None 이면 모든 채널 동일 속도(1.0).
    """
    seated = 0
    ticks  = 0
    channels = airplane.channels
    n_ch     = len(channels)

    # ── 채널 가중치 정규화 ──────────────────────────────────────
    # 평균을 1.0 으로 맞춰, 틱마다 각 채널에 norm_w[k] 씩 누적
    # 누적값 ≥ 1.0 이 되면 승객 1명 주입 → 가중치가 높은 채널이 더 빠르게 주입
    if channel_weights is not None and len(channel_weights) == n_ch:
        avg_w    = sum(channel_weights) / n_ch
        norm_w   = [w / avg_w for w in channel_weights]
    else:
        norm_w   = [1.0] * n_ch

    inject_accum = [0.0] * n_ch    # 채널별 주입 누적기

    # ── 전체 큐를 채널별로 분리 (순서 유지) ─────────────────────
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

        # ── 1) 모든 채널 통로 내 승객 행동 ────────────────────────
        # direction=+1: 뒤→앞 순서로 처리 (앞 먼저 비워야 연쇄 이동 방지)
        # direction=-1: 앞→뒤 순서로 처리
        for ch in channels:
            aisle = ch.aisle
            if ch.direction == 1:
                scan_range = range(airplane.num_rows, 0, -1)
            else:
                scan_range = range(1, airplane.num_rows + 1)
            for pos in scan_range:
                p = aisle.cells[pos]
                if p is None:
                    continue
                prev = p.state
                p.act(airplane)
                if prev != "seated" and p.state == "seated":
                    seated += 1

        # ── 2) 채널별 입구 처리 (가중치 누적기 방식) ───────────────
        for idx, ch in enumerate(channels):
            inject_accum[idx] += norm_w[idx]
            if inject_accum[idx] >= 1.0 and ch_queues[idx]:
                aisle = ch.aisle
                entry = ch.entrance_row
                if aisle.cells[entry] is None:
                    inject_accum[idx] -= 1.0
                    next_p: Passenger = ch_queues[idx].popleft()
                    aisle.cells[entry] = next_p
                    next_p.current_pos = entry
                    next_p.state       = "walking"

    return ticks