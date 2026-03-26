# boarding/methods.py
"""
탑승 방법(Boarding Strategy)별 승객 큐 생성.

각 함수는 Passenger 리스트를 받아 정렬된 리스트를 반환한다.
그룹 승객이 있을 경우 group_model.sort_group_internally() 로
그룹 내부를 창가→중간→통로 순으로 후처리한다.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional
import math
import random

if TYPE_CHECKING:
    from passenger import Passenger


# ── 내부 유틸 ────────────────────────────────────────────────

def _sort_groups(passengers: list[Passenger]) -> list[Passenger]:
    """그룹 내부를 창가→중간→통로 순으로 재정렬."""
    from boarding.group_model import sort_group_internally
    return sort_group_internally(passengers)


def _has_groups(passengers: list[Passenger]) -> bool:
    """승객에 group_id 속성이 있는지 확인."""
    return bool(passengers) and hasattr(passengers[0], "group_id")


# ── 개별 전략 ────────────────────────────────────────────────

def random_boarding(passengers: list[Passenger]) -> list[Passenger]:
    """완전 무작위 탑승 — 우선순위 그룹 M=1, 복잡도 C=0."""
    result = list(passengers)
    random.shuffle(result)
    return _sort_groups(result) if _has_groups(result) else result


def back_to_front(passengers: list[Passenger]) -> list[Passenger]:
    """뒷열부터 3개 구역으로 탑승 — M=3."""
    result = sorted(passengers, key=lambda p: -p.target_row)
    return _sort_groups(result) if _has_groups(result) else result


def front_to_back(passengers: list[Passenger]) -> list[Passenger]:
    """앞열부터 탑승 — M=3."""
    result = sorted(passengers, key=lambda p: p.target_row)
    return _sort_groups(result) if _has_groups(result) else result


def by_section(
    passengers: list[Passenger],
    n_sections: int = 3,
    aft_first: bool = True,
) -> list[Passenger]:
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


def by_seat(passengers: list[Passenger]) -> list[Passenger]:
    """
    창가 → 중간 → 통로 순서로 탑승 — M=3.
    통로 거리는 Passenger.aisle_dist 속성을 사용 (기종별 사전 배정).
    같은 우선순위 그룹 내부는 완전 랜덤.
    """
    # aisle_dist 속성이 없으면 0으로 폴백
    max_dist = max((getattr(p, 'aisle_dist', 0) for p in passengers), default=2)
    buckets: dict[int, list[Passenger]] = {d: [] for d in range(max_dist + 1)}
    for p in passengers:
        dist = getattr(p, 'aisle_dist', 0)
        buckets[dist].append(p)

    result: list[Passenger] = []
    # 거리 큰 것(창가)부터 먼저
    for d in range(max_dist, -1, -1):
        grp = list(buckets[d])
        random.shuffle(grp)
        result.extend(grp)
    return result


def weighted_by_seat(passengers: list[Passenger]) -> list[Passenger]:
    """
    FlyingWing 전용: 가중치 채널 주입 BySeat 방식.

    BySeat와 동일하게 창가→중간→통로 순으로 정렬하되,
    엔진에서 채널별 진입 속도에 75:84:84:75 가중치를 적용한다.
    (외곽 통로 75석 : 내부 통로 84석 비율로 조밀하게 주입)

    가중치 처리는 engine.run_boarding()의 channel_weights 파라미터로 전달.
    """
    return by_seat(passengers)


def reverse_pyramid(passengers: list[Passenger]) -> list[Passenger]:
    """
    TwinAisle 전용: 양방향 역피라미드(V자형 대각선) 탑승 방식.
    
    [핵심 로직 변경]
    - 전방(앞문 진입): 기체 중간(max_row)이 가장 깊으므로 max_row부터 입구(1열) 방향으로 채움.
    - 후방(뒷문 진입): 기체 중간(min_row)이 가장 깊으므로 min_row부터 입구(끝열) 방향으로 채움.
    """
    _FRONT = frozenset('ABCDEFG')
    _BACK  = frozenset('HIJKLMN')

    _SEAT_ORDER: dict[str, int] = {
        'A': 3, 'B': 2, 'C': 1, 'D': 0, 'E': 1, 'F': 2, 'G': 3,
        'H': 3, 'I': 2, 'J': 1, 'K': 0, 'L': 1, 'M': 2, 'N': 3,
    }
    _MAX_ORDER = 3   # A, G, H, N의 seat_order 값

    front_pax = [p for p in passengers if p.target_seat in _FRONT]
    back_pax  = [p for p in passengers if p.target_seat in _BACK]

    def pyramid_key(p: Passenger, base_row: int, is_front_door: bool) -> tuple[int, int]:
        seat_order = _SEAT_ORDER.get(p.target_seat, 0)
        
        # 전방/후방 진입구 위치에 따른 행 깊이(row_depth) 계산 분리
        if is_front_door:
            row_depth = base_row - p.target_row  # 전방: 번호가 큰 행일수록 깊음
        else:
            row_depth = p.target_row - base_row  # 후방: 번호가 작은 행(중앙)일수록 깊음
            
        seat_depth = _MAX_ORDER - seat_order     # 창가=0, 중앙=3
        group      = row_depth + seat_depth      # 작을수록(깊을수록) 먼저 탑승
        return (group, seat_depth)               # 같은 그룹 내 창가 우선

    # 전방은 가장 큰 열 번호가 기준, 후방은 가장 작은 열 번호가 기준
    front_max = max((p.target_row for p in front_pax), default=1)
    back_min  = min((p.target_row for p in back_pax),  default=1)

    # 각각의 기준과 진입 방향 플래그(True/False)를 넣어 정렬
    front_sorted = sorted(front_pax, key=lambda p: pyramid_key(p, front_max, is_front_door=True))
    back_sorted  = sorted(back_pax,  key=lambda p: pyramid_key(p, back_min, is_front_door=False))

    # 전방(95석)·후방(147석) 교대 삽입 — 두 입구 동시 탑승 반영 (2:3 비율)
    result: list[Passenger] = []
    fi, bi = 0, 0
    while fi < len(front_sorted) or bi < len(back_sorted):
        for _ in range(2):
            if fi < len(front_sorted):
                result.append(front_sorted[fi]); fi += 1
        for _ in range(3):
            if bi < len(back_sorted):
                result.append(back_sorted[bi]); bi += 1

    return result


def steffen_method(passengers: list[Passenger]) -> list[Passenger]:
    """
    Steffen (2008): 짝수열 창가 → 홀수열 창가 → ... — M=N.
    이론적 최적이나 현실 적용 어려움.
    aisle_dist 속성 기반으로 기종 범용화.
    """
    def steffen_key(p: Passenger) -> tuple[int, int]:
        # aisle_dist 클수록 창가 → 먼저 탑승 (dist 내림차순)
        dist   = getattr(p, 'aisle_dist', 0)
        # 짝수 행이 홀수 행보다 먼저
        parity = 0 if p.target_row % 2 == 0 else 1
        # dist 큰 것(창가) 먼저, 같으면 짝수열 먼저, 같으면 뒷행 먼저
        return (-dist + parity * 0.5, -p.target_row)  # type: ignore[return-value]

    return sorted(passengers, key=lambda p: (
        -(getattr(p, 'aisle_dist', 0)),
        0 if p.target_row % 2 == 0 else 1,
        -p.target_row,
    ))


# ── 전략 레지스트리 ───────────────────────────────────────────

STRATEGIES: dict[str, Callable] = {
    "Random":         random_boarding,
    "BackToFront":    back_to_front,
    "FrontToBack":    front_to_back,
    "BySection":      by_section,
    "BySeat":         by_seat,
    "Steffen":        steffen_method,
    "WeightedBySeat": weighted_by_seat,   # FlyingWing 전용
    "ReversePyramid": reverse_pyramid,    # TwinAisle 전용
}

# 전략별 우선순위 그룹 수 M (복잡도 계산에 사용)
# Steffen 은 승객 수 N 과 동일 → None 으로 표시
STRATEGY_M: dict[str, Optional[int]] = {
    "Random":         1,
    "BackToFront":    3,
    "FrontToBack":    3,
    "BySection":      3,
    "BySeat":         3,
    "Steffen":        None,   # M = N
    "WeightedBySeat": 3,      # BySeat와 동일 (창가/중간/통로 3그룹)
    "ReversePyramid": 24,     # 후방 21행 × 4단계 ≈ 24 distinct groups
}

# WeightedBySeat 전용: FlyingWing 채널별 주입 가중치
# outer(ch0,ch3)=75석 : inner(ch1,ch2)=84석 비율
STRATEGY_CHANNEL_WEIGHTS: dict[str, list[float]] = {
    "WeightedBySeat": [75.0, 84.0, 84.0, 75.0],
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