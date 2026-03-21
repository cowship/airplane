# passenger.py
from __future__ import annotations
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

    def __init__(
        self,
        pass_id: int,
        target_row: int,
        target_seat: str,
        age_group: str = "adult",
        n_bins_used: int = 0,
        bag_weights: tuple = None,
    ):
        self.id          = pass_id
        self.target_row  = target_row
        self.target_seat = target_seat
        self.age_group   = age_group

        # ── 상태 ────────────────────────────────────────────
        self.state       = "waiting"
        self.current_pos = 0          # 현재 통로 위치 (1-indexed row)

        # ── 이동 속도 ────────────────────────────────────────
        if age_group == "senior":
            self._walk_speed   = config.SENIOR_WALK_SPEED    # 틱/칸
            self._stow_mult    = config.SENIOR_STOW_MULT
        else:
            self._walk_speed   = config.ADULT_WALK_SPEED
            self._stow_mult    = 1.0

        self._walk_tick = 0   # 이동 속도 조절용 내부 카운터

        # ── 짐 ──────────────────────────────────────────────
        weights = bag_weights or config.BAG_PROB
        self.num_bags = random.choices([0, 1, 2], weights=weights)[0]
        raw_ticks     = _sample_bag_stow_time(self.num_bags, n_bins_used)
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
        """목표 행까지 통로를 전진하거나, 도착 시 짐 적재 시작."""
        # 목표 행 도달
        if self.current_pos == self.target_row:
            # 착각 이벤트: 한 번만 발동
            if self.is_confused:
                self.is_confused = False
                self.delay_timer = config.CONFUSED_DELAY_TICKS
                return
            self.state       = "stowing"
            self.delay_timer = self.stow_time
            return

        # 전진 시도
        self._walk_tick += 1
        if self._walk_tick >= self._walk_speed:
            self._walk_tick = 0
            next_pos = self.current_pos + 1
            if airplane.aisle.is_clear(self.current_pos):
                airplane.aisle.move_passenger(self, self.current_pos, next_pos)
                self.current_pos = next_pos
            # 막혀 있으면 그냥 대기 (walk_tick은 0으로 리셋됐으므로 다음 틱에 재시도)

    def _sit_down(self, airplane) -> None:
        """통로에서 빠져나와 좌석에 착석."""
        airplane.aisle.cells[self.current_pos] = None
        airplane.seats[self.target_row][self.target_seat] = self
        self.state = "seated"

    def __repr__(self) -> str:
        return (
            f"Passenger(id={self.id}, seat={self.target_row}{self.target_seat}, "
            f"state={self.state}, bags={self.num_bags})"
        )