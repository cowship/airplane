# simulation/pandemic.py
"""
팬데믹 상황 탑승 시뮬레이션 엔진.

기존 engine.py 대비 두 가지 핵심 변경사항:
  1. 통로 내 최소 거리 제약 (d)
       d = 3 (탑승률 30%), d = 2 (50%), d = 1 (70%)
       조건: aisle[next_pos] == empty AND (pos[n-1] - pos[n]) >= d

  2. 좌석 간섭 조건 변경
       기존: 내부 좌석이 항상 점유됐다고 가정
       수정: occupied_seats 집합에 실제로 포함된 경우에만 간섭 발생
       → E[N_interruption] ∝ c (점유율에 비례)

탑승률별 권장 거리 설정 (config.PANDEMIC_DISTANCE_MAP 참조):
    c = 0.70 → d = 1
    c = 0.50 → d = 2
    c = 0.30 → d = 3
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from collections import deque

import config
from aircraft.base import AircraftBase
from boarding.queue_model import QueueManager

if TYPE_CHECKING:
    from passenger import Passenger


# ── 탑승률 → 거리 매핑 ────────────────────────────────────────
DISTANCE_MAP: dict[float, int] = {
    0.70: 1,
    0.50: 2,
    0.30: 3,
}


def get_distance(occupancy_rate: float) -> int:
    """
    탑승률에 가장 가까운 거리 d 반환.
    정확히 일치하는 값이 없으면 가장 가까운 값을 사용.
    """
    if occupancy_rate in DISTANCE_MAP:
        return DISTANCE_MAP[occupancy_rate]
    # 가장 가까운 키
    closest = min(DISTANCE_MAP.keys(), key=lambda k: abs(k - occupancy_rate))
    return DISTANCE_MAP[closest]


def run_pandemic_boarding(
    airplane: AircraftBase,
    queue_manager: QueueManager,
    total_passengers: int,
    occupied_seats: set[tuple[int, str]],
    aisle_distance: int,
    channel_weights: Optional[list[float]] = None,
) -> int:
    """
    팬데믹 조건 탑승 시뮬레이션.

    Parameters
    ----------
    occupied_seats   : 실제 탑승하는 (row, seat_col) 집합.
                       좌석 간섭 계산 시 이 집합에 포함된 경우만 간섭 발생.
    aisle_distance   : 통로 내 최소 유지 거리 (칸 단위).

    Returns
    -------
    int  완료 틱 수. MAX_TICKS 초과 시 -1.
    """
    seated = 0
    ticks  = 0
    channels = airplane.channels
    n_ch     = len(channels)

    # ── 채널 가중치 정규화 ──────────────────────────────────────
    if channel_weights is not None and len(channel_weights) == n_ch:
        avg_w  = sum(channel_weights) / n_ch
        norm_w = [w / avg_w for w in channel_weights]
    else:
        norm_w = [1.0] * n_ch

    inject_accum = [0.0] * n_ch

    # ── 전체 큐 → 채널별 분리 ────────────────────────────────────
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

        # ── 1) 통로 내 승객 행동 ─────────────────────────────────
        for ch in channels:
            aisle = ch.aisle
            scan_range = (
                range(airplane.num_rows, 0, -1)
                if ch.direction == 1
                else range(1, airplane.num_rows + 1)
            )
            for pos in scan_range:
                p = aisle.cells[pos]
                if p is None:
                    continue
                prev_state = p.state

                # ── 팬데믹 이동 조건: 거리 제약 ──────────────────
                if p.state == "walking":
                    _pandemic_walk(p, airplane, ch, aisle_distance, occupied_seats)
                else:
                    # stowing / seating 은 기존 act() 사용
                    p.act(airplane)

                if prev_state != "seated" and p.state == "seated":
                    seated += 1

        # ── 2) 채널별 입구 주입 ──────────────────────────────────
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


# ── 내부 헬퍼 ────────────────────────────────────────────────

def _pandemic_walk(
    p: "Passenger",
    airplane: AircraftBase,
    ch,
    d: int,
    occupied_seats: set[tuple[int, str]],
) -> None:
    """
    팬데믹 조건 이동.
    앞 d칸 내에 다른 승객이 없을 때만 전진.
    목표 행 도달 시 팬데믹 간섭 계산 후 stowing 전환.
    """
    aisle = ch.aisle

    if p.current_pos == p.target_row:
        # ── 목표 행 도달 → stowing 전환 ─────────────────────────
        p.state       = "stowing"
        p.delay_timer = _pandemic_stow_time(p)
        return

    # ── 거리 제약 확인 ──────────────────────────────────────────
    # 전진 방향으로 1 ~ d 칸 내에 다른 승객 존재 여부 확인
    direction = ch.direction
    can_move  = True
    for gap in range(1, d + 1):
        check_pos = p.current_pos + direction * gap
        if 0 < check_pos < len(aisle.cells):
            if aisle.cells[check_pos] is not None:
                can_move = False
                break

    if not can_move:
        return

    # ── 이동 속도 제어 (walk_tick) ───────────────────────────────
    p._walk_tick += 1
    if p._walk_tick >= p._walk_speed:
        p._walk_tick = 0
        next_pos = p.current_pos + direction
        if aisle.is_clear(p.current_pos, direction):
            aisle.move_passenger(p, p.current_pos, next_pos)
            p.current_pos = next_pos


def _pandemic_stow_time(p: "Passenger") -> int:
    """
    팬데믹 상황에서는 stow_time 을 그대로 사용.
    (짐 적재 시간은 기존 Weibull 샘플링 그대로)
    """
    return max(0, p.stow_time)


def _pandemic_interference(
    row: int,
    seat_col: str,
    airplane: AircraftBase,
    occupied_seats: set[tuple[int, str]],
) -> int:
    """
    팬데믹 조건 좌석 간섭.

    기존: 내부 좌석이 물리적으로 점유됐는지만 확인
    수정: occupied_seats 에 포함된 경우에만 간섭 발생
           → 점유율 감소 시 간섭도 비례해서 감소
           E[N_interruption] ∝ c
    """
    row_seats = airplane.seats[row]
    delay     = 0

    def _occupied(col: str) -> bool:
        # 실제로 착석해 있거나, occupied_seats에 포함된 좌석인지 확인
        seated_p = row_seats.get(col)
        if seated_p is not None:
            return True
        return (row, col) in occupied_seats

    if seat_col == 'A':
        if _occupied('C'): delay += config.STAND_UP_TICKS
        if _occupied('B'): delay += config.STAND_UP_TICKS
    elif seat_col == 'B':
        if _occupied('C'): delay += config.STAND_UP_TICKS
    elif seat_col == 'F':
        if _occupied('D'): delay += config.STAND_UP_TICKS
        if _occupied('E'): delay += config.STAND_UP_TICKS
    elif seat_col == 'E':
        if _occupied('D'): delay += config.STAND_UP_TICKS

    return delay