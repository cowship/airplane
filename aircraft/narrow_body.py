# aircraft/narrow_body.py
"""
좁은 동체 항공기 (Narrow-body).

2022031 논문 Aircraft I 기준:
  - 198석, 33행 × 6열 (A B C | D E F)
  - 중앙 통로 1개, 오버헤드 빈 6칸/행
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import config
from aircraft.base import AircraftBase, Aisle, BoardingChannel

if TYPE_CHECKING:
    from passenger import Passenger

_ALL_COLS = frozenset('ABCDEF')

_AISLE_DIST: dict[str, int] = {
    'C': 0, 'D': 0,
    'B': 1, 'E': 1,
    'A': 2, 'F': 2,
}


class NarrowBody(AircraftBase):
    """단일 통로, 3+3 좌석 배열."""

    name                  = "NarrowBody"
    num_rows              = 33
    overhead_bin_capacity = 6

    _SEAT_COLS = ('A', 'B', 'C', 'D', 'E', 'F')

    def __init__(self) -> None:
        self._aisle   = Aisle(self.num_rows)
        self._channel = BoardingChannel(self._aisle, 1, set(_ALL_COLS))
        super().__init__()

    @property
    def channels(self) -> list[BoardingChannel]:
        return [self._channel]

    @property
    def seat_cols(self) -> tuple[str, ...]:
        return self._SEAT_COLS

    def channel_for_seat(self, seat_col: str) -> BoardingChannel:
        return self._channel

    # 기존 코드 호환용 편의 속성
    @property
    def aisle(self) -> Aisle:
        return self._aisle

    def aisle_distance(self, seat_col: str) -> int:
        return _AISLE_DIST.get(seat_col, 0)

    def calculate_interference(self, row: int, seat: str) -> int:
        row_seats = self.seats[row]
        delay = 0
        if seat == 'A':
            if row_seats.get('C') is not None:
                delay += config.STAND_UP_TICKS
            if row_seats.get('B') is not None:
                delay += config.STAND_UP_TICKS
        elif seat == 'B':
            if row_seats.get('C') is not None:
                delay += config.STAND_UP_TICKS
        elif seat == 'F':
            if row_seats.get('D') is not None:
                delay += config.STAND_UP_TICKS
            if row_seats.get('E') is not None:
                delay += config.STAND_UP_TICKS
        elif seat == 'E':
            if row_seats.get('D') is not None:
                delay += config.STAND_UP_TICKS
        return delay