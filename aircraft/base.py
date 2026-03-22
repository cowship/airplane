# aircraft/base.py
"""
항공기 추상 기반 클래스.

모든 기종은 AircraftBase를 상속하고
BoardingChannel 목록을 통해 탑승/하차 엔진에 자신의 구조를 노출한다.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
import config

if TYPE_CHECKING:
    from passenger import Passenger


# ── 통로 채널 ────────────────────────────────────────────────

class Aisle:
    """단일 통로(채널) 셀 상태 관리."""

    def __init__(self, num_rows: int) -> None:
        # index 0 = 미사용, 1 ~ num_rows = 각 행, num_rows+1 = 대기열 직전
        self.cells: list[Optional[Passenger]] = [None] * (num_rows + 2)

    def is_clear(self, pos: int, direction: int = 1) -> bool:
        """다음 이동 방향 칸이 비어 있는지 확인."""
        nxt = pos + direction
        return 0 < nxt < len(self.cells) and self.cells[nxt] is None

    def move_passenger(self, p: Passenger, frm: int, to: int) -> None:
        self.cells[frm] = None
        self.cells[to]  = p


class BoardingChannel:
    """
    탑승 채널 — 하나의 통로 + 입구.

    Parameters
    ----------
    aisle       : 이 채널이 관리하는 Aisle 객체
    entrance_row: 승객이 통로에 진입하는 행 번호
    seat_cols   : 이 채널을 사용하는 좌석 열 집합
    direction   : +1 = 앞→뒤(row 증가), -1 = 뒤→앞(row 감소)
    """

    def __init__(
        self,
        aisle: Aisle,
        entrance_row: int,
        seat_cols: set[str],
        direction: int = 1,
    ) -> None:
        self.aisle        = aisle
        self.entrance_row = entrance_row
        self.seat_cols    = seat_cols
        self.direction    = direction


# ── 항공기 추상 기반 ────────────────────────────────────────────

class AircraftBase(ABC):
    """모든 항공기 기종의 추상 기반 클래스."""

    # 서브클래스가 반드시 정의
    name: str
    num_rows: int
    overhead_bin_capacity: int

    # ── 추상 메서드 ────────────────────────────────────────────

    @property
    @abstractmethod
    def channels(self) -> list[BoardingChannel]:
        """이 기종의 모든 탑승 채널 목록."""
        ...

    @property
    @abstractmethod
    def seat_cols(self) -> tuple[str, ...]:
        """이 기종의 좌석 열 라벨 (왼쪽 → 오른쪽)."""
        ...

    @abstractmethod
    def channel_for_seat(self, seat_col: str) -> BoardingChannel:
        """주어진 좌석 열이 사용하는 채널 반환."""
        ...

    @abstractmethod
    def calculate_interference(self, row: int, seat: str) -> int:
        """해당 좌석 착석 시 추가 지연 틱 수."""
        ...

    # ── 공통 구현 ────────────────────────────────────────────

    def __init__(self) -> None:
        self.seats: dict[int, dict[str, Optional[Passenger]]] = {
            row: {col: None for col in self.seat_cols}
            for row in range(1, self.num_rows + 1)
        }
        self._bins_used: dict[int, int] = {
            row: 0 for row in range(1, self.num_rows + 1)
        }

    @property
    def total_seats(self) -> int:
        return len(self.passenger_slots())

    def bins_used(self, row: int) -> int:
        return self._bins_used.get(row, 0)

    def use_bin(self, row: int, n_bags: int) -> int:
        used = self._bins_used[row]
        self._bins_used[row] = min(
            used + n_bags, self.overhead_bin_capacity
        )
        return used

    def passenger_slots(self) -> list[tuple[int, str]]:
        """
        유효한 (행, 좌석열) 조합 목록 반환.
        비직사각형 기종(FlyingWing 등)에서 오버라이드.
        기본: num_rows × seat_cols 전체.
        """
        return [
            (row, col)
            for row in range(1, self.num_rows + 1)
            for col in self.seat_cols
        ]

    def aisle_distance(self, seat_col: str) -> int:
        """통로까지의 거리 (0 = 통로석, 클수록 창가)."""
        ch = self.channel_for_seat(seat_col)
        cols_in_ch = sorted(ch.seat_cols)
        # 통로에 가장 가까운 쪽: 채널 내에서 중앙에 가까운 방향
        # 기본 구현: 채널 내 인덱스로 거리 계산
        if seat_col in cols_in_ch:
            return cols_in_ch.index(seat_col)
        return 0
        return all(
            p is not None and p.state == "seated"
            for row_seats in self.seats.values()
            for p in row_seats.values()
        )

    def seated_count(self) -> int:
        return sum(
            1
            for row_seats in self.seats.values()
            for p in row_seats.values()
            if p is not None and p.state == "seated"
        )

    def reset(self) -> None:
        """시뮬레이션 재실행을 위해 상태 초기화."""
        for ch in self.channels:
            n = len(ch.aisle.cells)
            ch.aisle.cells = [None] * n
        self.seats = {
            row: {col: None for col in self.seat_cols}
            for row in range(1, self.num_rows + 1)
        }
        self._bins_used = {row: 0 for row in range(1, self.num_rows + 1)}