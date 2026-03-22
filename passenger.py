# passenger.py
from __future__ import annotations
from typing import Optional
import random
import numpy as np
import config


def _sample_bag_stow_time(n_bags: int, n_bins_used: int = 0) -> int:
    """
    짐 적재 틱 수 계산.

    USE_WEIBULL=True  → 2022031 Weibull 샘플링 (k=5.153, λ=7.774)
    USE_WEIBULL=False → 2022019 포화도 수식
    """
    if n_bags == 0:
        return 0

    if config.USE_WEIBULL:
        # numpy Weibull: np.random.weibull(k) * λ
        total_sec = 0.0
        for _ in range(n_bags):
            s = float(np.random.weibull(config.WEIBULL_K)) * config.WEIBULL_LAMBDA
            s = max(config.WEIBULL_MIN_SEC, min(config.WEIBULL_MAX_SEC, s))
            total_sec += s
        ticks = round(total_sec / config.TICK_DURATION)
    else:
        # 2022019 포화도 수식
        fill = min(n_bins_used / config.OVERHEAD_BIN_MAX, 0.95)
        t_sec = config.BAG_BASE_TIME_SEC / (1 - config.BAG_FILL_COEFF * fill)
        if n_bags == 2:
            fill2 = min((n_bins_used + 1) / config.OVERHEAD_BIN_MAX, 0.95)
            t_sec += config.BAG_EXTRA_SEC / (1 - fill2)
        ticks = round(t_sec / config.TICK_DURATION)

    return max(1, ticks)


class Passenger:
    """
    한 승객의 속성과 매 틱 행동을 담당.

    state 흐름:
        waiting → walking → stowing → seating → seated
    """

    # ── 클래스 레벨 어노테이션 (Pyright 인식용) ─────────────────
    id:               int
    target_row:       int
    target_seat:      str
    age_group:        str
    group_id:         int    # 0 = 그룹 없음
    disobedient:      bool   # 비순응 여부 (그룹 단위로 결정)
    state:            str
    current_pos:      int
    num_bags:         int
    stow_time:        int
    is_confused:      bool
    delay_timer:      int
    # ── 하차 전용 속성 ────────────────────────────────────────
    deplane_state:    str    # "seated" | "collecting" | "walking" | "left"
    deplane_priority: int    # 낮을수록 먼저 하차
    deplane_current:  int    # 현재 통로 위치
    collect_timer:    int    # 짐 수거 남은 틱
    is_late_deplaner: bool   # 늦게 일어나는 승객 여부
    # ── 기종 공통 ─────────────────────────────────────────────
    aisle_dist:       int    # 통로까지 거리 (0=통로석, 클수록 창가)

    def __init__(
        self,
        pass_id: int,
        target_row: int,
        target_seat: str,
        age_group: str = "adult",
        n_bins_used: int = 0,
        bag_weights: Optional[tuple] = None,
        group_id: int = 0,
        disobedient: bool = False,
    ):
        self.id           = pass_id
        self.target_row   = target_row
        self.target_seat  = target_seat
        self.age_group    = age_group
        self.group_id     = group_id       # 0 = 그룹 없음
        self.disobedient  = disobedient    # 비순응 여부 (그룹 단위로 결정)

        # ── 상태 ────────────────────────────────────────────
        self.state       = "waiting"
        self.current_pos = 0          # 현재 통로 위치 (1-indexed row)

        # ── 이동 속도 ────────────────────────────────────────
        if age_group == "senior":
            self._walk_speed = config.SENIOR_WALK_SPEED
            self._stow_mult  = config.SENIOR_STOW_MULT
        else:
            self._walk_speed = config.ADULT_WALK_SPEED
            self._stow_mult  = 1.0

        self._walk_tick = 0

        # ── 짐 ──────────────────────────────────────────────
        weights = bag_weights or config.BAG_PROB
        self.num_bags  = random.choices([0, 1, 2], weights=weights)[0]
        raw_ticks      = _sample_bag_stow_time(self.num_bags, n_bins_used)
        self.stow_time = round(raw_ticks * self._stow_mult)

        # ── 기타 속성 ────────────────────────────────────────
        self.is_confused = random.random() < config.CONFUSED_PROB
        self.delay_timer = 0

    # ── 공개 메서드 ─────────────────────────────────────────

    def act(self, airplane) -> None:
        """매 틱마다 호출. 상태 전이 및 이동 처리."""
        if self.state == "seated":
            return

        # 1) stowing 완료 → seating 진입
        if self.state == "stowing" and self.delay_timer <= 0:
            self.state = "seating"
            interference = airplane.calculate_interference(
                self.target_row, self.target_seat
            )
            self.delay_timer = config.SIT_DOWN_TICKS + interference

        # 2) seating 완료 → seated
        if self.state == "seating" and self.delay_timer <= 0:
            self._sit_down(airplane)
            return

        # 3) 대기 중인 타이머 소모
        if self.delay_timer > 0:
            self.delay_timer -= 1
            return

        # 4) 통로 이동 로직
        if self.state == "walking":
            self._walk(airplane)

    # ── 내부 헬퍼 ───────────────────────────────────────────

    def _walk(self, airplane) -> None:
        """목표 행까지 통로를 이동하거나, 도착 시 짐 적재 시작."""
        ch        = airplane.channel_for_seat(self.target_seat)
        aisle     = ch.aisle
        direction = ch.direction   # +1: 앞→뒤, -1: 뒤→앞

        if self.current_pos == self.target_row:
            if self.is_confused:
                self.is_confused = False
                self.delay_timer = config.CONFUSED_DELAY_TICKS
                return
            self.state       = "stowing"
            self.delay_timer = self.stow_time
            return

        self._walk_tick += 1
        if self._walk_tick >= self._walk_speed:
            self._walk_tick = 0
            next_pos = self.current_pos + direction
            if aisle.is_clear(self.current_pos, direction):
                aisle.move_passenger(self, self.current_pos, next_pos)
                self.current_pos = next_pos

    def _sit_down(self, airplane) -> None:
        """통로에서 빠져나와 좌석에 착석."""
        ch    = airplane.channel_for_seat(self.target_seat)
        aisle = ch.aisle
        aisle.cells[self.current_pos] = None
        airplane.seats[self.target_row][self.target_seat] = self
        self.state = "seated"

    def __repr__(self) -> str:
        return (
            f"Passenger(id={self.id}, seat={self.target_row}{self.target_seat}, "
            f"state={self.state}, bags={self.num_bags})"
        )