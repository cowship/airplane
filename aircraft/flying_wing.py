# aircraft/flying_wing.py
"""
전익기 (Flying Wing) — 2022031 논문 Aircraft II 정확 재현.

구조:
  - 318석, 통로 4개, 24개 좌석열 (A~X)
  - 외곽 날개(A-C, V-X): 행 4-14 (11행, 날개 끝이 좁음)
  - 내부 섹션(D-U):     행 1-14 (14행, 중앙이 넓음)

통로 배치 (좌 → 우):
  A B C  |aisle0|  D E F  G H I  |aisle1|  J K L  M N O  |aisle2|  P Q R  S T U  |aisle3|  V W X
  ←outer→         ←inner-L-A→   ←inner-L-B→             ←center-L→←center-R→              ←inner-R-A→←inner-R-B→        ←outer→

통로별 담당 열:
  channel 0 (aisle 0): A,B,C (outer-left) + D,E,F (inner-left-A)
  channel 1 (aisle 1): G,H,I (inner-left-B) + J,K,L (center-left)
  channel 2 (aisle 2): M,N,O (center-right) + P,Q,R (inner-right-A)
  channel 3 (aisle 3): S,T,U (inner-right-B) + V,W,X (outer-right)
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import config
from aircraft.base import AircraftBase, Aisle, BoardingChannel

if TYPE_CHECKING:
    from passenger import Passenger

# ── 채널별 좌석열 ──────────────────────────────────────────────
_CH0_COLS = frozenset('ABCDEF')   # outer-left + inner-left-A
_CH1_COLS = frozenset('GHIJKL')   # inner-left-B + center-left
_CH2_COLS = frozenset('MNOPQR')   # center-right + inner-right-A
_CH3_COLS = frozenset('STUVWX')   # inner-right-B + outer-right

# 외곽 날개 열 (행 4-14만 유효, 11행)
_OUTER_COLS = frozenset('ABCVWX')
_OUTER_ROW_START = 4   # 날개 끝 부분: 행 1-3 없음

# 통로 거리 (aisle_dist): 클수록 창가·외곽 → BySeat 에서 먼저 탑승
# 각 채널: 양쪽 3열씩, 통로에 가까운 쪽 = 0, 먼 쪽 = 2
_AISLE_DIST: dict[str, int] = {
    # channel 0: A,B,C (outer-left) / D,E,F (inner-left-A)
    'A': 2, 'B': 1, 'C': 0,
    'D': 0, 'E': 1, 'F': 2,
    # channel 1: G,H,I (inner-left-B) / J,K,L (center-left)
    'G': 2, 'H': 1, 'I': 0,
    'J': 0, 'K': 1, 'L': 2,
    # channel 2: M,N,O (center-right) / P,Q,R (inner-right-A)
    'M': 2, 'N': 1, 'O': 0,
    'P': 0, 'Q': 1, 'R': 2,
    # channel 3: S,T,U (inner-right-B) / V,W,X (outer-right)
    'S': 2, 'T': 1, 'U': 0,
    'V': 0, 'W': 1, 'X': 2,
}


class FlyingWing(AircraftBase):
    """전익기 — 4통로, 비직사각형 날개 형태."""

    name                  = "FlyingWing"
    num_rows              = 14   # 내부 최대 깊이
    overhead_bin_capacity = 10

    # A~X = 24열
    _SEAT_COLS = tuple('ABCDEFGHIJKLMNOPQRSTUVWX')

    # 시각화: 채널당 내부 통로 1개씩 (채널 경계는 물리적 통로 아님)
    DISPLAY_COLS = (
        'A', 'B', 'C', 'AISLE', 'D', 'E', 'F',
        'G', 'H', 'I', 'AISLE', 'J', 'K', 'L',
        'M', 'N', 'O', 'AISLE', 'P', 'Q', 'R',
        'S', 'T', 'U', 'AISLE', 'V', 'W', 'X',
    )
    AISLE_CH_MAP: dict[int, int] = {0: 0, 1: 1, 2: 2, 3: 3}

    def __init__(self) -> None:
        self._aisles   = [Aisle(self.num_rows) for _ in range(4)]
        self._channels = [
            BoardingChannel(self._aisles[0], 1, set(_CH0_COLS)),
            BoardingChannel(self._aisles[1], 1, set(_CH1_COLS)),
            BoardingChannel(self._aisles[2], 1, set(_CH2_COLS)),
            BoardingChannel(self._aisles[3], 1, set(_CH3_COLS)),
        ]
        super().__init__()

    @property
    def channels(self) -> list[BoardingChannel]:
        return self._channels

    @property
    def seat_cols(self) -> tuple[str, ...]:
        return self._SEAT_COLS

    def channel_for_seat(self, seat_col: str) -> BoardingChannel:
        if seat_col in _CH0_COLS: return self._channels[0]
        if seat_col in _CH1_COLS: return self._channels[1]
        if seat_col in _CH2_COLS: return self._channels[2]
        return self._channels[3]

    def aisle_distance(self, seat_col: str) -> int:
        return _AISLE_DIST.get(seat_col, 0)

    def passenger_slots(self) -> list[tuple[int, str]]:
        """외곽 날개(A,B,C,V,W,X)는 행 4-14만 유효."""
        slots = []
        for col in self._SEAT_COLS:
            start = _OUTER_ROW_START if col in _OUTER_COLS else 1
            for row in range(start, self.num_rows + 1):
                slots.append((row, col))
        return slots

    def calculate_interference(self, row: int, seat: str) -> int:
        """통로쪽 좌석이 이미 착석한 경우 일어나야 하는 지연."""
        row_seats = self.seats[row]
        delay = 0
        dist  = _AISLE_DIST.get(seat, 0)
        # 같은 채널에서 dist 가 더 작은(통로에 가까운) 좌석이 점유 시 지연
        ch_cols = (
            _CH0_COLS if seat in _CH0_COLS else
            _CH1_COLS if seat in _CH1_COLS else
            _CH2_COLS if seat in _CH2_COLS else
            _CH3_COLS
        )
        for col in ch_cols:
            if _AISLE_DIST.get(col, 0) < dist:
                if row_seats.get(col) is not None:
                    delay += config.STAND_UP_TICKS
        return delay