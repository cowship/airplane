# aircraft/twin_aisle.py
"""
2통로 항공기 (Twin-aisle / Two-entrance Two-aisle) — 2022031 논문 Aircraft III 정확 재현.

구조:
  - 242석: 전방 섹션 95석 + 후방 섹션 147석
  - 통로 2개, 입구 2개 (전방 + 후방)
  - 전방(Front): cols A-G, 행 1-14 (outer 14행, middle 13행 → 95석)
  - 후방(Back):  cols H-N, 행 1-21 (모든 열 21행 → 147석)

좌석 배열 (7열, 양 섹션 동일):
  A  B  | C  D  E | F  G
  ←left→ ←middle→ ←right→
  aisle-left          aisle-right

통로 담당:
  left channel (aisle-left):  A,B,C,D + H,I,J,K (= outer-left + half-middle, 양 섹션)
  right channel (aisle-right): E,F,G + L,M,N    (= half-middle + outer-right, 양 섹션)

※ 전방/후방 섹션은 물리적으로 분리된 공간 → 승객이 서로 간섭하지 않음.
   시뮬레이션에서는 전방/후방을 각각 독립 채널로 처리 (총 4 채널).
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import config
from aircraft.base import AircraftBase, Aisle, BoardingChannel

if TYPE_CHECKING:
    from passenger import Passenger

# 전방 섹션: cols A-G, 후방 섹션: cols H-N
_FRONT_COLS = frozenset('ABCDEFG')
_BACK_COLS  = frozenset('HIJKLMN')

# 전방 섹션 행 깊이
#   논문 기준: outer(A,B,F,G) = 14행, middle(C,D,E) = 13행
_FRONT_OUTER_ROWS  = 14   # A, B, F, G
_FRONT_MIDDLE_ROWS = 13   # C, D, E
_FRONT_OUTER_COLS  = frozenset('ABFG')
_FRONT_MIDDLE_COLS = frozenset('CDE')

# 후방 섹션 행 깊이: 전열 21행
_BACK_ROWS = 21

# 전방 left/right 채널 분할
_FRONT_LEFT  = frozenset('ABCD')   # left channel (aisle-left)
_FRONT_RIGHT = frozenset('EFG')    # right channel (aisle-right)
_BACK_LEFT   = frozenset('HIJK')   # same split for back section
_BACK_RIGHT  = frozenset('LMN')

# 통로 거리 (aisle_dist): 클수록 창가 → BySeat 에서 먼저 탑승
# 좌석 배열: A B | C D E | F G
#            left       right
# A=2(window), B=1, C=1(aisle-adj), D=2(middle), E=1(aisle-adj), F=1, G=2(window)
_AISLE_DIST: dict[str, int] = {
    'A': 2, 'B': 1, 'C': 1, 'D': 2, 'E': 1, 'F': 1, 'G': 2,
    'H': 2, 'I': 1, 'J': 1, 'K': 2, 'L': 1, 'M': 1, 'N': 2,
}


class TwinAisle(AircraftBase):
    """2통로, 전방/후방 2개 입구, 전체 242석."""

    name                  = "TwinAisle"
    num_rows              = 21   # 후방 섹션 최대 깊이
    overhead_bin_capacity = 8

    _SEAT_COLS = tuple('ABCDEFGHIJKLMN')

    def __init__(self) -> None:
        # 4개 독립 채널: 전방-left, 전방-right, 후방-left, 후방-right
        self._front_left_aisle  = Aisle(self.num_rows)
        self._front_right_aisle = Aisle(self.num_rows)
        self._back_left_aisle   = Aisle(self.num_rows)
        self._back_right_aisle  = Aisle(self.num_rows)

        self._front_left_ch  = BoardingChannel(
            self._front_left_aisle,  1, set(_FRONT_LEFT))
        self._front_right_ch = BoardingChannel(
            self._front_right_aisle, 1, set(_FRONT_RIGHT))
        self._back_left_ch   = BoardingChannel(
            self._back_left_aisle,   1, set(_BACK_LEFT))
        self._back_right_ch  = BoardingChannel(
            self._back_right_aisle,  1, set(_BACK_RIGHT))
        super().__init__()

    @property
    def channels(self) -> list[BoardingChannel]:
        return [
            self._front_left_ch, self._front_right_ch,
            self._back_left_ch,  self._back_right_ch,
        ]

    @property
    def seat_cols(self) -> tuple[str, ...]:
        return self._SEAT_COLS

    def channel_for_seat(self, seat_col: str) -> BoardingChannel:
        if seat_col in _FRONT_LEFT:  return self._front_left_ch
        if seat_col in _FRONT_RIGHT: return self._front_right_ch
        if seat_col in _BACK_LEFT:   return self._back_left_ch
        return self._back_right_ch

    def aisle_distance(self, seat_col: str) -> int:
        return _AISLE_DIST.get(seat_col, 0)

    def passenger_slots(self) -> list[tuple[int, str]]:
        """
        전방 섹션: outer(A,B,F,G) = 14행, middle(C,D,E) = 13행.
        후방 섹션: 전 열 21행.
        """
        slots = []
        # 전방
        for col in 'ABCDEFG':
            max_row = _FRONT_OUTER_ROWS if col in _FRONT_OUTER_COLS else _FRONT_MIDDLE_ROWS
            for row in range(1, max_row + 1):
                slots.append((row, col))
        # 후방
        for col in 'HIJKLMN':
            for row in range(1, _BACK_ROWS + 1):
                slots.append((row, col))
        return slots

    def calculate_interference(self, row: int, seat: str) -> int:
        row_seats = self.seats[row]
        delay = 0
        # 좌측 그룹 A,B,C,D / H,I,J,K: D 또는 K 가 통로석 (dist=0)
        if seat in ('A', 'H'):   # window
            for s in ('B' if seat == 'A' else 'I',
                      'C' if seat == 'A' else 'J',
                      'D' if seat == 'A' else 'K'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat in ('B', 'I'):   # second from window
            for s in ('C' if seat == 'B' else 'J',
                      'D' if seat == 'B' else 'K'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat in ('C', 'J'):   # aisle-adjacent left
            if row_seats.get('D' if seat == 'C' else 'K') is not None:
                delay += config.STAND_UP_TICKS
        # 우측 그룹 E,F,G / L,M,N: E 또는 L 이 통로석
        elif seat in ('G', 'N'):   # window
            for s in ('F' if seat == 'G' else 'M',
                      'E' if seat == 'G' else 'L'):
                if row_seats.get(s) is not None:
                    delay += config.STAND_UP_TICKS
        elif seat in ('F', 'M'):   # second from window
            if row_seats.get('E' if seat == 'F' else 'L') is not None:
                delay += config.STAND_UP_TICKS
        return delay