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


def aisle_first(passengers: list[Passenger]) -> list[Passenger]:
    """
    진짜 통로 우선 하차(Aisle → Middle → Window).
    행(Row) 번호와 무관하게 비행기 전체의 통로석 그룹부터 일제히 하차합니다.
    """
    seat_priority = {
        "A": 3, "B": 2, "C": 1,
        "D": 1, "E": 2, "F": 3,
        # Flying Wing 등 대형기 확장 좌석
        "G": 1, "H": 1, "I": 2, "J": 2, "K": 3,
        "L": 1, "M": 1, "N": 2, "O": 3
    }

    for p in passengers:
        # 튜플(Tuple) 구조를 버리고, 순수하게 좌석 타입(1, 2, 3)만 우선순위로 부여
        priority_value = seat_priority.get(p.target_seat, 3) # 매칭 안 되면 일단 창가석(3) 취급
        p.deplane_priority = priority_value

    return passengers


DEPLANE_METHODS: dict[str, object] = {
    "Random":       random_deplaning,
    "FrontToBack":  front_to_back,
    "BackToFront":  back_to_front,
    "AisleFirst":   aisle_first,
}


def get_deplane_method(name: str):  # type: ignore[return]
    if name not in DEPLANE_METHODS:
        raise ValueError(
            f"알 수 없는 하차 방법: '{name}'. "
            f"가능한 방법: {list(DEPLANE_METHODS.keys())}"
        )
    return DEPLANE_METHODS[name]