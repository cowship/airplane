# simulation/engine.py
"""
탑승 시뮬레이션 코어 루프.
AircraftBase + QueueManager를 받아 모든 승객이 착석할 때까지 틱을 돌린다.
다중 채널(통로) 병렬 처리를 지원한다.

수정 사항:
  - 착석 카운트를 aisle 루프 밖에서 집계해 이중 집계 방지
  - 채널 큐가 비어있고 aisle도 비어있을 때 조기 종료 추가
  - 스톨 감지(연속 N틱 동안 seated 변화 없음) 로직 추가
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from collections import deque

import config
from aircraft.base import AircraftBase
from boarding.queue_model import QueueManager

if TYPE_CHECKING:
    from passenger import Passenger

# 연속으로 이 틱 수 동안 착석 진전이 없으면 데드락으로 판단
_STALL_LIMIT = 5_000


def run_boarding(
    airplane: AircraftBase,
    queue_manager: QueueManager,
    total_passengers: int,
) -> int:
    """
    Returns
    -------
    int
        탑승 완료까지 소요된 틱 수.
        MAX_TICKS 초과 또는 스톨 감지 시 -1.
    """
    seated = 0
    ticks  = 0
    channels = airplane.channels

    # 전체 큐를 채널별로 분리 (순서 유지)
    ch_queues: list[deque[Passenger]] = [deque() for _ in channels]
    while True:
        p = queue_manager.pop_next()
        if p is None:
            break
        assigned = False
        for idx, ch in enumerate(channels):
            if p.target_seat in ch.seat_cols:
                ch_queues[idx].append(p)
                assigned = True
                break
        # 어느 채널에도 배정되지 않은 경우 방어 처리
        if not assigned:
            ch_queues[0].append(p)

    stall_counter = 0
    last_seated   = 0

    while seated < total_passengers:
        ticks += 1
        if ticks > config.MAX_TICKS:
            return -1

        # 스톨 감지: 일정 틱 동안 새로 착석한 승객이 없으면 데드락
        if seated == last_seated:
            stall_counter += 1
            if stall_counter >= _STALL_LIMIT:
                return -1
        else:
            stall_counter = 0
            last_seated   = seated

        # ── 1) 모든 채널 통로 내 승객 행동 (뒤 → 앞) ──────────
        for ch in channels:
            aisle = ch.aisle
            for pos in range(airplane.num_rows, 0, -1):
                p = aisle.cells[pos]
                if p is None:
                    continue
                prev_state = p.state
                p.act(airplane)
                if prev_state != "seated" and p.state == "seated":
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