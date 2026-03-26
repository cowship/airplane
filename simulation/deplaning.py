# simulation/deplaning.py
"""
하차 시뮬레이션 엔진 (우선순위 상속 기반 동적 물리 차단 적용).
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
    s = float(np.random.weibull(config.WEIBULL_K)) * config.WEIBULL_LAMBDA
    s = max(config.WEIBULL_MIN_SEC, min(config.WEIBULL_MAX_SEC, s))
    return max(1, round(s / config.TICK_DURATION))

def _assign_late_deplaners(passengers: list[Passenger]) -> set[int]:
    n_late = round(len(passengers) * config.LATE_ARRIVAL_RATE)
    late_pax = random.sample(passengers, n_late)
    return {p.id for p in late_pax}

def _get_blocking_seats(seat_col: str, channel_cols: list[str]) -> list[str]:
    """통로로 나가기 위해 물리적으로 거쳐야 하는 바깥쪽 좌석 계산"""
    sorted_cols = sorted(channel_cols)
    if seat_col not in sorted_cols:
        return []
    idx = sorted_cols.index(seat_col)
    mid_float = (len(sorted_cols) - 1) / 2.0
    
    blocking = []
    for i, other_seat in enumerate(sorted_cols):
        if i == idx: continue
        my_dist = abs(idx - mid_float)
        other_dist = abs(i - mid_float)
        same_side = (idx <= mid_float and i <= mid_float) or (idx >= mid_float and i >= mid_float)
        if same_side and other_dist < my_dist:
            blocking.append(other_seat)
    return blocking

def run_deplaning(
    airplane: AircraftBase,
    passengers: list[Passenger],
    deplane_method: Callable[[list[Passenger]], list[Passenger]],
) -> int:
    deplane_method(passengers)
    
    late_ids = _assign_late_deplaners(passengers)
    max_pri = max((p.deplane_priority for p in passengers), default=1)

    for p in passengers:
        p.deplane_state = "seated"
        p.collect_timer = _sample_collect_time()
        p.deplane_current = 0
        p.is_late_deplaner = p.id in late_ids
        # 늦게 내리는 승객은 기본 우선순위를 최하위로 밀어버림
        p.base_priority = max_pri + 1 if p.is_late_deplaner else p.deplane_priority

    # 채널별 길막(Blocking) 좌석 맵핑 미리 계산
    ch_blocks = {}
    for ch_idx, ch in enumerate(airplane.channels):
        ch_blocks[ch_idx] = {}
        for seat_col in ch.seat_cols:
            ch_blocks[ch_idx][seat_col] = _get_blocking_seats(seat_col, list(ch.seat_cols))

    for ch in airplane.channels:
        ch.aisle.cells = [None] * len(ch.aisle.cells)

    left = 0
    ticks = 0
    total = len(passengers)

    while left < total:
        ticks += 1
        if ticks > config.MAX_TICKS:
            return -1

        # ── 0) 우선순위 상속 (Priority Inheritance) ──
        # 안쪽 승객이 나가야 하는데 바깥쪽 승객이 막고 있다면,
        # 바깥쪽 승객은 안쪽 승객의 높은 우선순위(더 작은 숫자)를 상속받아 강제로 비켜주게 됨
        for p in passengers:
            if p.deplane_state in ("seated", "collecting"):
                p.effective_priority = p.base_priority

        changed = True
        while changed:
            changed = False
            for ch_idx, ch in enumerate(airplane.channels):
                for row in range(1, airplane.num_rows + 1):
                    for seat_col in ch.seat_cols:
                        p = airplane.seats[row].get(seat_col)
                        if not p or p.deplane_state not in ("seated", "collecting"):
                            continue
                        
                        blocking_me = ch_blocks[ch_idx][seat_col]
                        for b_seat in blocking_me:
                            blocker = airplane.seats[row].get(b_seat)
                            if blocker and blocker.deplane_state in ("seated", "collecting"):
                                # 내 앞길을 막는 사람이 나보다 여유부리고 있다면 순위 강제 조정
                                if blocker.effective_priority > p.effective_priority:
                                    blocker.effective_priority = p.effective_priority
                                    changed = True

        # 현재 틱에서 수행할 수 있는 가장 높은(숫자가 작은) 우선순위 결정
        active_pris = [p.effective_priority for p in passengers if p.deplane_state in ("seated", "collecting")]
        cur_pri = min(active_pris) if active_pris else max_pri + 1

        # ── 1) 좌석 처리: 짐 수거 & 통로 진입 ────────────────
        for ch_idx, ch in enumerate(airplane.channels):
            aisle = ch.aisle
            
            # 통로에 가까운 순서대로 처리하여 고스팅 방지
            sorted_cols = sorted(ch.seat_cols)
            mid_float = (len(sorted_cols) - 1) / 2.0
            seat_order = sorted(ch.seat_cols, key=lambda s: abs(sorted_cols.index(s) - mid_float))

            for row in range(1, airplane.num_rows + 1):
                aisle_free = (aisle.cells[row] is None)

                for seat_col in seat_order:
                    p = airplane.seats[row].get(seat_col)
                    if not p or p.deplane_state not in ("seated", "collecting"):
                        continue

                    # 현재 틱에서 허용된 우선순위인지 확인 (상속받은 우선순위 기준)
                    if p.effective_priority > cur_pri:
                        continue

                    # 나를 가로막는 사람이 아직 앉아있는지 물리적 차단 확인
                    is_blocked = False
                    for b_seat in ch_blocks[ch_idx][seat_col]:
                        other = airplane.seats[row].get(b_seat)
                        if other and other.deplane_state in ("seated", "collecting"):
                            is_blocked = True
                            break
                    
                    if is_blocked:
                        continue

                    # 짐 수거 진행
                    if p.collect_timer > 0:
                        p.collect_timer -= 1
                        p.deplane_state = "collecting"
                        continue

                    # 짐 수거 완료 → 통로 진입
                    if aisle_free:
                        airplane.seats[row][seat_col] = None
                        aisle.cells[row] = p
                        p.deplane_current = row
                        p.deplane_state = "walking"
                        aisle_free = False

        # ── 2) 통로 내 이동 ────────────────
        for ch in airplane.channels:
            aisle = ch.aisle
            for pos in range(1, airplane.num_rows + 1):
                p = aisle.cells[pos]
                if not p or p.deplane_state != "walking":
                    continue

                if pos == 1:
                    aisle.cells[pos] = None
                    p.deplane_state = "left"
                    left += 1
                elif aisle.cells[pos - 1] is None:
                    aisle.cells[pos - 1] = p
                    aisle.cells[pos] = None
                    p.deplane_current = pos - 1

    return ticks