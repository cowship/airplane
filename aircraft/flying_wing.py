# aircraft/flying_wing.py
"""
전익기 (Flying Wing).

2022031 논문 Aircraft II 기준 단순화:
  - 320석, 20행 × 16열 (A-H 왼쪽, I-P 오른쪽)
  - 통로 2개, 오버헤드 빈 10칸/행
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import config
from aircraft.base import AircraftBase, Aisle, BoardingChannel

if TYPE_CHECKING:
    from passenger import Passenger

_LEFT_COLS  = frozenset('ABCDEFGH')
_RIGHT_COLS = frozenset('IJKLMNOP')

# H/I 가 통로석(거리 0), A/P 가 창가(거리 7)
_AISLE_DIST: dict[str, int] = {
    'H': 0, 'G': 1, 'F': 2, 'E': 3, 'D': 4, 'C': 5, 'B': 6, 'A': 7,
    'I': 0, 'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'O': 6, 'P': 7,
}


class FlyingWing(AircraftBase):
    """전익기 — 극도로 넓은 동체, 통로 2개."""

    name                  = "FlyingWing"
    num_rows              = 20
    overhead_bin_capacity = 10

    _SEAT_COLS = tuple('ABCDEFGHIJKLMNOP')

    def __init__(self) -> None:
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
        dist = _AISLE_DIST.get(seat, 0)
        # 통로 쪽 좌석(거리 < dist)이 점유돼 있으면 일어나야 함
        for col, d in _AISLE_DIST.items():
            if col in (
                _LEFT_COLS if seat in _LEFT_COLS else _RIGHT_COLS
            ) and d < dist:
                if row_seats.get(col) is not None:
                    delay += config.STAND_UP_TICKS
        return delay