# simulation/engine.py
"""
탑승 시뮬레이션 코어 루프.
Airplane + QueueManager를 받아 모든 승객이 착석할 때까지 틱을 돌린다.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import config
from airplane import Airplane
from boarding.queue_model import QueueManager

if TYPE_CHECKING:
    from passenger import Passenger


def run_boarding(
    airplane: Airplane,
    queue_manager: QueueManager,
    total_passengers: int,
) -> int:
    """
    Returns
    -------
    int
        탑승 완료까지 소요된 틱 수.
        config.MAX_TICKS 초과 시 -1 반환 (데드락 의심).
    """
    seated = 0
    ticks  = 0
    aisle  = airplane.aisle

    while seated < total_passengers:
        ticks += 1
        if ticks > config.MAX_TICKS:
            return -1   # 데드락 감지

        # ── 1) 통로 내 승객 행동 (뒤 → 앞 순서로 처리) ──────────
        for pos in range(airplane.num_rows, 0, -1):
            p = aisle.cells[pos]
            if p is None:
                continue
            prev_state = p.state
            p.act(airplane)
            if prev_state != "seated" and p.state == "seated":
                seated += 1

        # ── 2) 입구(pos=1)가 비어 있으면 다음 승객 입장 ──────────
        if aisle.cells[1] is None:
            next_p: Passenger | None = queue_manager.pop_next()
            if next_p is not None:
                aisle.cells[1]     = next_p
                next_p.current_pos = 1
                next_p.state       = "walking"

    return ticks