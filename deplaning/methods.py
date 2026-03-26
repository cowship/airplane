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
    통로 우선 하차(Aisle → Middle → Window).
    seat_col을 기준으로 우선순위를 부여한다.
    """
    seat_priority = {
        "A": 3, "B": 2, "C": 1,
        "D": 1, "E": 2, "F": 3,
        "G": 1, "H": 1, "I": 2, "J": 2, "K": 3
    }
    
    # 현재 비행기의 좌석 알파벳 종류 스캔
    unique_seats = set(p.target_seat for p in passengers)
    
    # 좌석 종류가 K(11개)를 초과하는 초대형기(Flying Wing 등)인지 확인
    is_mega_aircraft = len(unique_seats) > 11
    
    for p in passengers:
        if is_mega_aircraft:
            # 특수 대형기는 통로 구조가 다르고 복잡하여 기존 규칙 적용 시 데드락이 발생함.
            # 따라서 데드락 위험이 없는 행(Row) 기준 하차로 자동 폴백(Fallback) 적용.
            p.deplane_priority = p.target_row
        else:
            priority_value = seat_priority.get(p.target_seat, 2)
            p.deplane_priority = p.target_row * 10 + priority_value
            
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