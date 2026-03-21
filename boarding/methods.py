# boarding/methods.py
"""
탑승 방법(Boarding Strategy)별 승객 큐 생성.
각 함수는 Passenger 리스트를 받아 정렬된 리스트를 반환한다.
"""
import random
from typing import Callable


# ── 개별 전략 ────────────────────────────────────────────────

def random_boarding(passengers: list) -> list:
    """완전 무작위 탑승."""
    result = list(passengers)
    random.shuffle(result)
    return result


def back_to_front(passengers: list) -> list:
    """뒷열부터 앞열 순서로 탑승."""
    return sorted(passengers, key=lambda p: -p.target_row)


def front_to_back(passengers: list) -> list:
    """앞열부터 뒷열 순서로 탑승."""
    return sorted(passengers, key=lambda p: p.target_row)


def by_section(passengers: list, n_sections: int = 3, aft_first: bool = True) -> list:
    """
    비행기를 n_sections 구역으로 나눠 탑승.
    aft_first=True → 뒤 구역부터 (항공사 일반 관행).
    """
    max_row = max(p.target_row for p in passengers)

    def section_of(row: int) -> int:
        # 0 = 뒤, n_sections-1 = 앞
        return int((row - 1) / max_row * n_sections)

    return sorted(
        passengers,
        key=lambda p: (section_of(p.target_row) if not aft_first
                       else -section_of(p.target_row))
    )


def by_seat(passengers: list) -> list:
    """
    창가(A/F) → 중간(B/E) → 통로(C/D) 순서로 탑승.
    같은 우선순위 그룹 내부는 완전 랜덤 — 이것이 핵심.
    (2022031 논문 구현 방식과 동일)
    """
    priority = {'A': 0, 'F': 0, 'B': 1, 'E': 1, 'C': 2, 'D': 2}
    # 그룹별로 분리 후 각 그룹 내부를 셔플
    groups: dict[int, list] = {0: [], 1: [], 2: []}
    for p in passengers:
        groups[priority[p.target_seat]].append(p)
    result = []
    for g in (0, 1, 2):
        grp = list(groups[g])
        random.shuffle(grp)
        result.extend(grp)
    return result


def steffen_method(passengers: list) -> list:
    """
    Steffen (2008): 짝수열 창가 → 홀수열 창가 → 짝수열 중간 ...
    이론적 최적이나 현실 적용 어려움.
    """
    col_priority = {'A': 0, 'F': 0, 'B': 2, 'E': 2, 'C': 4, 'D': 4}

    def steffen_key(p):
        cp = col_priority[p.target_seat]
        # 짝수열이 홀수열보다 먼저 (0/1 로 구분)
        parity = 0 if p.target_row % 2 == 0 else 1
        return (cp + parity, -p.target_row)

    return sorted(passengers, key=steffen_key)


# ── 전략 레지스트리 ───────────────────────────────────────────

STRATEGIES: dict[str, Callable] = {
    "Random":       random_boarding,
    "BackToFront":  back_to_front,
    "FrontToBack":  front_to_back,
    "BySection":    by_section,
    "BySeat":       by_seat,
    "Steffen":      steffen_method,
}


def get_strategy(name: str) -> Callable:
    if name not in STRATEGIES:
        raise ValueError(
            f"알 수 없는 전략: '{name}'. "
            f"가능한 전략: {list(STRATEGIES.keys())}"
        )
    return STRATEGIES[name]