# simulation/deplaning.py
"""
하차 시뮬레이션 엔진.

상태 흐름 (Passenger.deplane_state):
    "seated"     → 자기 우선순위 차례가 될 때까지 대기
    "collecting" → 짐 수거 중 (Weibull 시간, 좌석에서 진행)
    "walking"    → 통로를 통해 출구로 이동 중
    "left"       → 하차 완료

늦게 일어나는 승객(is_late_deplaner):
    같은 행의 일반 승객이 모두 "collecting" 이상 진행할 때까지 대기.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import random
import numpy as np

import config
from aircraft.base import AircraftBase

if TYPE_CHECKING:
    from passenger import Passenger


def _sample_collect_time() -> int:
    """짐 수거 시간 샘플링 (Weibull, 탑승 적재 시간과 동일 분포)."""
    s = float(np.random.weibull(config.WEIBULL_K)) * config.WEIBULL_LAMBDA
    s = max(config.WEIBULL_MIN_SEC, min(config.WEIBULL_MAX_SEC, s))
    return max(1, round(s / config.TICK_DURATION))


def _assign_late_deplaners(passengers: list[Passenger]) -> set[int]:
    n_late = round(len(passengers) * config.LATE_ARRIVAL_RATE)
    if n_late == 0:
        return set()
    return {p.id for p in random.sample(passengers, n_late)}


def run_deplaning(
    airplane: AircraftBase,
    passengers: list[Passenger],
    deplane_method: Callable[[list[Passenger]], list[Passenger]],
) -> int:
    """
    Returns
    -------
    int  하차 완료까지 소요된 틱 수. MAX_TICKS 초과 시 -1.
    """
    # ── 초기화 ───────────────────────────────────────────────
    deplane_method(passengers)           # deplane_priority 배정

    late_ids = _assign_late_deplaners(passengers)
    max_pri  = max(p.deplane_priority for p in passengers)  # type: ignore[attr-defined]

    for p in passengers:
        p.deplane_state    = "seated"
        p.collect_timer    = _sample_collect_time()
        p.deplane_current  = 0
        p.is_late_deplaner = p.id in late_ids
        if p.is_late_deplaner:
            p.deplane_priority = max_pri + 1  # type: ignore[attr-defined]

    # 통로 초기화 (탑승 엔진이 남긴 상태 제거)
    for ch in airplane.channels:
        ch.aisle.cells = [None] * len(ch.aisle.cells)

    left  = 0
    ticks = 0
    total = len(passengers)

    while left < total:
        ticks += 1
        if ticks > config.MAX_TICKS:
            return -1

        # 현재 최소 활성 우선순위
        cur_pri = min(
            (p.deplane_priority for p in passengers  # type: ignore[attr-defined]
             if p.deplane_state != "left"),
            default=max_pri + 1,
        )

        # ── 1) 좌석 처리: 짐 수거 & 통로 진입 ────────────────
        for ch in airplane.channels:
            aisle = ch.aisle
            # 행별로 통로 진입을 제한하기 위해 행 단위 처리
            for row in range(1, airplane.num_rows + 1):
                # 이 행 통로 칸이 비어 있어야 진입 가능
                aisle_free = (aisle.cells[row] is None)

                for seat_col in sorted(ch.seat_cols):   # 통로석 먼저 처리
                    p = airplane.seats[row].get(seat_col)
                    if p is None:
                        continue
                    # "seated" 또는 "collecting" 상태만 처리
                    if p.deplane_state not in ("seated", "collecting"):
                        continue
                    # 우선순위 확인
                    if p.deplane_priority > cur_pri:    # type: ignore[attr-defined]
                        continue
                    # 지각 승객: 같은 행 일반 승객이 모두 떠날 때까지 대기
                    if p.is_late_deplaner:
                        others_remain = any(
                            other is not None
                            and other is not p
                            and not other.is_late_deplaner
                            and other.deplane_state in ("seated", "collecting")
                            for other in airplane.seats[row].values()
                        )
                        if others_remain:
                            continue

                    # 짐 수거 진행
                    if p.collect_timer > 0:
                        p.collect_timer   -= 1
                        p.deplane_state    = "collecting"
                        continue

                    # 짐 수거 완료 → 통로 진입 시도
                    if aisle_free:
                        airplane.seats[row][seat_col] = None
                        aisle.cells[row]  = p
                        p.deplane_current = row
                        p.deplane_state   = "walking"
                        aisle_free        = False   # 이번 틱 이 행 통로 칸 점유됨

        # ── 2) 통로 내 이동 (앞에서부터 처리 → 연쇄 이동 방지) ──
        for ch in airplane.channels:
            aisle = ch.aisle
            # pos=1부터 처리해서 출구 쪽 먼저 비워야 뒤가 이동 가능
            for pos in range(1, airplane.num_rows + 1):
                p = aisle.cells[pos]
                if p is None or p.deplane_state != "walking":
                    continue

                if pos == 1:
                    # 출구 탈출
                    aisle.cells[pos] = None
                    p.deplane_state  = "left"
                    left += 1
                elif aisle.cells[pos - 1] is None:
                    # 앞 칸으로 전진
                    aisle.cells[pos - 1] = p
                    aisle.cells[pos]     = None
                    p.deplane_current    = pos - 1

    return ticks