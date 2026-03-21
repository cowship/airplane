# deplaning/methods.py
"""
하차 방법(Deplaning Strategy)별 우선순위 배정.

우선순위 숫자가 작을수록 먼저 하차.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from passenger import Passenger


def random_deplaning(passengers: list[Passenger]) -> list[Passenger]:
    """모든 승객 우선순위 1 — 통로석부터 자연스럽게 나감."""
    for p in passengers:
        p.deplane_priority = 1
    return passengers


def front_to_back(passengers: list[Passenger]) -> list[Passenger]:
    """앞열부터 하차 — 우선순위 = 행 번호."""
    for p in passengers:
        p.deplane_priority = p.target_row
    return passengers


def back_to_front(passengers: list[Passenger]) -> list[Passenger]:
    """뒷열부터 하차 — 항공사 일반 관행의 반대."""
    max_row = max(p.target_row for p in passengers)
    for p in passengers:
        p.deplane_priority = max_row - p.target_row + 1
    return passengers


def row_by_row(passengers: list[Passenger]) -> list[Passenger]:
    """한 행씩 순서대로 하차 — front_to_back과 동일하나 엄격 적용."""
    return front_to_back(passengers)


DEPLANE_METHODS: dict[str, object] = {
    "Random":       random_deplaning,
    "FrontToBack":  front_to_back,
    "BackToFront":  back_to_front,
    "RowByRow":     row_by_row,
}


def get_deplane_method(name: str):  # type: ignore[return]
    if name not in DEPLANE_METHODS:
        raise ValueError(
            f"알 수 없는 하차 방법: '{name}'. "
            f"가능한 방법: {list(DEPLANE_METHODS.keys())}"
        )
    return DEPLANE_METHODS[name]