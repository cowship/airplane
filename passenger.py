# passenger.py
from __future__ import annotations
from typing import Optional
import random
import numpy as np
import config

def _sample_bag_stow_time(n_bags: int, n_bins_used: int = 0) -> int:
    """짐 적재 틱 수 계산 (Weibull 분포 또는 포화도 수식 적용)."""
    if n_bags == 0:
        return 0

    if config.USE_WEIBULL:
        total_sec = 0.0
        for _ in range(n_bags):
            s = float(np.random.weibull(config.WEIBULL_K)) * config.WEIBULL_LAMBDA
            s = max(config.WEIBULL_MIN_SEC, min(config.WEIBULL_MAX_SEC, s))
            total_sec += s
        ticks = round(total_sec / config.TICK_DURATION)
    else:
        fill = min(n_bins_used / config.OVERHEAD_BIN_MAX, 0.95)
        t_sec = config.BAG_BASE_TIME_SEC / (1 - config.BAG_FILL_COEFF * fill)
        if n_bags == 2:
            fill2 = min((n_bins_used + 1) / config.OVERHEAD_BIN_MAX, 0.95)
            t_sec += config.BAG_EXTRA_SEC / (1 - fill2)
        ticks = round(t_sec / config.TICK_DURATION)

    return max(1, ticks)

class Passenger:
    """한 승객의 속성과 매 틱 행동을 담당하는 클래스."""

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
        # ── 1. 기본 인적 사항 ──
        self.id = pass_id
        self.target_row = target_row
        self.target_seat = target_seat
        self.age_group = age_group
        self.group_id = group_id
        self.disobedient = disobedient
        self.aisle_dist = 0  # 기종 설정 시 외부에서 덮어씌워짐

        # ── 2. 탑승(Boarding) 전용 상태 및 속성 ──
        self.state = "waiting"        # waiting → walking → stowing → seating → seated
        self.current_pos = 0          # 현재 통로 위치
        self.delay_timer = 0          # 각종 대기(짐 싣기, 길 비켜주기 등) 틱 타이머
        self.is_confused = random.random() < config.CONFUSED_PROB
        
        if age_group == "senior":
            self._walk_speed = config.SENIOR_WALK_SPEED
            self._stow_mult = config.SENIOR_STOW_MULT
        else:
            self._walk_speed = config.ADULT_WALK_SPEED
            self._stow_mult = 1.0

        self._walk_tick = 0
        weights = bag_weights or config.BAG_PROB
        self.num_bags = random.choices([0, 1, 2], weights=weights)[0]
        raw_ticks = _sample_bag_stow_time(self.num_bags, n_bins_used)
        self.stow_time = round(raw_ticks * self._stow_mult)

        # ── 3. 하차(Deplaning) 전용 상태 및 속성 (초기화 필수!) ──
        self.deplane_state = "seated" # seated → collecting → walking → left
        self.deplane_current = 0      # 하차 시 현재 통로 위치
        self.collect_timer = 0        # 하차 시 짐 수거 남은 틱
        self.is_late_deplaner = False # 늦게 내리는 승객 여부
        
        # 데드락 방지용 우선순위 속성들 (에러의 주원인이었던 부분)
        self.deplane_priority = 0     # 부여받은 기본 하차 순서
        self.base_priority = 0        # 늦게 내리기 등이 반영된 베이스 순서
        self.effective_priority = 0   # 앞길 막힘(Priority Inheritance)이 반영된 최종 순서

    # ── 공개 메서드 ─────────────────────────────────────────

    def act(self, airplane) -> None:
        """매 틱마다 호출되는 탑승(Boarding) 메인 행동 로직."""
        if self.state == "seated":
            return

        # 1. 대기 타이머가 있다면 틱 소모 후 행동 종료 (우선 처리)
        if self.delay_timer > 0:
            self.delay_timer -= 1
            return

        # 2. 상태 전이 로직 (타이머가 0일 때만 실행됨)
        if self.state == "stowing":
            # 짐 넣기 완료 → 자리에 앉기 위한 간섭(Interference) 틱 계산
            self.state = "seating"
            interference = airplane.calculate_interference(self.target_row, self.target_seat)
            self.delay_timer = config.SIT_DOWN_TICKS + interference
            
        elif self.state == "seating":
            # 자리 앉기 대기 완료 → 실제 착석
            self._sit_down(airplane)
            
        elif self.state == "walking":
            # 걷기 수행
            self._walk(airplane)

    # ── 내부 헬퍼 ───────────────────────────────────────────

    def _walk(self, airplane) -> None:
        """목표 행까지 통로를 이동하거나, 도착 시 짐 적재 시작."""
        ch = airplane.channel_for_seat(self.target_seat)
        aisle = ch.aisle
        direction = ch.direction  # +1: 앞→뒤, -1: 뒤→앞

        if self.current_pos == self.target_row:
            if self.is_confused:
                self.is_confused = False
                self.delay_timer = config.CONFUSED_DELAY_TICKS
                return
            self.state = "stowing"
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
        ch = airplane.channel_for_seat(self.target_seat)
        aisle = ch.aisle
        aisle.cells[self.current_pos] = None
        airplane.seats[self.target_row][self.target_seat] = self
        self.state = "seated"

    def __repr__(self) -> str:
        return (
            f"Passenger(id={self.id}, seat={self.target_row}{self.target_seat}, "
            f"board_state={self.state}, deplane_state={self.deplane_state})"
        )