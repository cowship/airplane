# boarding/methods.py
"""
탑승 방법(Boarding Strategy)별 승객 큐 생성.

각 함수는 Passenger 리스트를 받아 정렬된 리스트를 반환한다.
그룹 승객이 있을 경우 group_model.sort_group_internally() 로
그룹 내부를 창가→중간→통로 순으로 후처리한다.
"""
from __future__ import annotations
from typing import Callable
import math
import random


# ── 내부 유틸 ────────────────────────────────────────────────

def _sort_groups(passengers: list) -> list:
    """그룹 내부를 창가→중간→통로 순으로 재정렬."""
    from boarding.group_model import sort_group_internally
    return sort_group_internally(passengers)


def _has_groups(passengers: list) -> bool:
    """승객에 group_id 속성이 있는지 확인."""
    return passengers and hasattr(passengers[0], "group_id")


# ── 개별 전략 ────────────────────────────────────────────────

def random_boarding(passengers: list) -> list:
    """완전 무작위 탑승 — 우선순위 그룹 M=1, 복잡도 C=0."""
    result = list(passengers)
    random.shuffle(result)
    # 그룹 내부 순서 유지 (창가→통로)
    return _sort_groups(result) if _has_groups(result) else result


def back_to_front(passengers: list) -> list:
    """뒷열부터 3개 구역으로 탑승 — M=3."""
    result = sorted(passengers, key=lambda p: -p.target_row)
    return _sort_groups(result) if _has_groups(result) else result


def front_to_back(passengers: list) -> list:
    """앞열부터 탑승 — M=3."""
    result = sorted(passengers, key=lambda p: p.target_row)
    return _sort_groups(result) if _has_groups(result) else result


def by_section(passengers: list, n_sections: int = 3, aft_first: bool = True) -> list:
    """
    비행기를 n_sections 구역으로 나눠 탑승 — M=n_sections.
    aft_first=True → 뒤 구역부터 (항공사 일반 관행).
    """
    max_row = max(p.target_row for p in passengers)

    def section_of(row: int) -> int:
        return int((row - 1) / max_row * n_sections)

    result = sorted(
        passengers,
        key=lambda p: (-section_of(p.target_row) if aft_first
                       else section_of(p.target_row)),
    )
    return _sort_groups(result) if _has_groups(result) else result


def by_seat(passengers: list) -> list:
    """
    창가(A/F) → 중간(B/E) → 통로(C/D) 순서로 탑승 — M=3.
    같은 우선순위 그룹 내부는 완전 랜덤.
    """
    priority = {'A': 0, 'F': 0, 'B': 1, 'E': 1, 'C': 2, 'D': 2}
    buckets: dict[int, list] = {0: [], 1: [], 2: []}
    for p in passengers:
        buckets[priority[p.target_seat]].append(p)

    result = []
    for g in (0, 1, 2):
        grp = list(buckets[g])
        random.shuffle(grp)
        result.extend(grp)

    # by_seat 은 이미 창가→통로 순이므로 추가 정렬 불필요
    return result


def steffen_method(passengers: list) -> list:
    """
    Steffen (2008): 짝수열 창가 → 홀수열 창가 → ... — M=N.
    이론적 최적이나 현실 적용 어려움.
    """
    col_priority = {'A': 0, 'F': 0, 'B': 2, 'E': 2, 'C': 4, 'D': 4}

    def steffen_key(p):
        cp     = col_priority[p.target_seat]
        parity = 0 if p.target_row % 2 == 0 else 1
        return (cp + parity, -p.target_row)

    result = sorted(passengers, key=steffen_key)
    # Steffen 은 개인별 지정 순서 — 그룹 내부 재정렬 없음
    return result


# ── 전략 레지스트리 ───────────────────────────────────────────

STRATEGIES: dict[str, Callable] = {
    "Random":      random_boarding,
    "BackToFront": back_to_front,
    "FrontToBack": front_to_back,
    "BySection":   by_section,
    "BySeat":      by_seat,
    "Steffen":     steffen_method,
}

# 전략별 우선순위 그룹 수 M (복잡도 계산에 사용)
# Steffen 은 승객 수 N 과 동일 → None 으로 표시 (QueueManager 에서 N 으로 대체)
STRATEGY_M: dict[str, int | None] = {
    "Random":      1,
    "BackToFront": 3,
    "FrontToBack": 3,
    "BySection":   3,
    "BySeat":      3,
    "Steffen":     None,   # M = N
}


def get_strategy(name: str) -> Callable:
    if name not in STRATEGIES:
        raise ValueError(
            f"알 수 없는 전략: '{name}'. "
            f"가능한 전략: {list(STRATEGIES.keys())}"
        )
    return STRATEGIES[name]


def boarding_complexity(strategy_name: str, n_passengers: int) -> float:
    """
    2022031 논문 복잡도 공식.
        C = ln(M) / ln(N)
    M=1(Random) → C=0,  M=N(Steffen) → C=1
    """
    m = STRATEGY_M.get(strategy_name)
    if m is None:
        m = n_passengers          # Steffen: M = N
    if m <= 1 or n_passengers <= 1:
        return 0.0
    return math.log(m) / math.log(n_passengers)