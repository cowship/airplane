# aircraft/twin_aisle.py
"""
2통로 항공기 (Twin-aisle).

2022031 논문 Aircraft III 기준:
  - 240석, 30행 × 8열 (A B C D | E F G H)
  - 왼쪽 통로(D|E 사이), 오른쪽 없음 → D/E 기준 분리
  - 왼쪽 그룹(A-D) → 왼쪽 통로, 오른쪽 그룹(E-H) → 오른쪽 통로
  - 오버헤드 빈 8칸/행
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import config
from aircraft.base import AircraftBase, Aisle, BoardingChannel

if TYPE_CHECKING:
    from passenger import Passenger

_LEFT_COLS  = frozenset({'A', 'B', 'C', 'D'})
_RIGHT_COLS = frozenset({'E', 'F', 'G', 'H'})

_AISLE_DIST: dict[str, int] = {
    'D': 0, 'C': 1, 'B': 2, 'A': 3,
    'E': 0, 'F': 1, 'G': 2, 'H': 3,
}


class TwinAisle(AircraftBase):
    """2통로, 4+4 좌석 배열."""

    name                  = "TwinAisle"
    num_rows              = 30
    overhead_bin_capacity = 8

    _SEAT_COLS = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H')

    def __init__(self) -> None:
        # 채널 먼저 생성 → super().__init__()이 reset()에서 channels 접근
        self._left_aisle    = Aisle(self.num_rows)
        self._right_aisle   = Aisle(self.num_rows)
        self._left_channel  = BoardingChannel(self._left_aisle,  1, set(_LEFT_COLS))
        self._right_channel = BoardingChannel(self._right_aisle, 1, set(_RIGHT_COLS))
        super().__init__()

    @property
    def channels(self) -> list[BoardingChannel]:
        return [self._left_channel, self._right_channel]

    @property
    def seat_cols(self) -> tuple[str, ...]:
        return self._SEAT_COLS

    def channel_for_seat(self, seat_col: str) -> BoardingChannel:
        return self._left_channel if seat_col in _LEFT_COLS else self._right_channel

    def aisle_distance(self, seat_col: str) -> int:
        return _AISLE_DIST.get(seat_col, 0)

    def calculate_interference(self, row: int, seat: str) -> int:
        row_seats = self.seats[row]
        delay = 0
        if seat == 'A':
            for s in ('D', 'C', 'B'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat == 'B':
            for s in ('D', 'C'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat == 'C':
            if row_seats.get('D') is not None:
                delay += config.STAND_UP_TICKS
        elif seat == 'H':
            for s in ('E', 'F', 'G'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat == 'G':
            for s in ('E', 'F'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat == 'F':
            if row_seats.get('E') is not None:
                delay += config.STAND_UP_TICKS
        return delay