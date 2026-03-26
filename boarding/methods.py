# boarding/methods.py
"""
탑승 방법(Boarding Strategy)별 승객 큐 생성.

각 함수는 Passenger 리스트를 받아 정렬된 리스트를 반환한다.
그룹 승객이 있을 경우 group_model.sort_group_internally() 로
그룹 내부를 창가→중간→통로 순으로 후처리한다.

[M값 계산 원칙]
  M = 실제 '우선순위 그룹'의 수 (IBS에서 독립된 블록 개수)
  C = ln(M) / ln(N)

  | 전략             | M                                        |
  | Random         | 1                                        |
  | BySeat         | 3 (창가/중간/통로)                            |
  | WeightedBySeat | 3 (BySeat와 동일)                          |
  | BySection      | n_sections (기본 3, 호출 시 동적)               |
  | BackToFront    | 탑승 행(row)의 수 → 동적                       |
  | FrontToBack    | 탑승 행(row)의 수 → 동적                       |
  | Steffen        | N (승객 수)                                |
  | ReversePyramid | max(행 깊이) + max(좌석 깊이) → 섹션·기종별 동적    |
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional
import math
import random

if TYPE_CHECKING:
    from passenger import Passenger

# TwinAisle 후방 섹션 열 (direction = -1, 입구 = row_max)
_TWIN_AISLE_BACK_COLS: frozenset[str] = frozenset('HIJKLMN')


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
    """완전 무작위 탑승 — M=1, C=0."""
    result = list(passengers)
    random.shuffle(result)
    return _sort_groups(result) if _has_groups(result) else result


def back_to_front(passengers: list[Passenger]) -> list[Passenger]:
    """
    뒷열부터 탑승 — 각 행(row)이 독립 그룹 → M = 고유 행 수.

    TwinAisle 후방 섹션은 입구가 row_max이므로
    해당 섹션은 row 작을수록 더 깊다(= 먼저 탑승).
    """
    def _row_depth(p: Passenger) -> int:
        # 후방 섹션: 낮은 row = 깊음 → 오름차순(작을수록 먼저) → 음수 반환
        if p.target_seat in _TWIN_AISLE_BACK_COLS:
            return p.target_row          # ascending → 먼저 타야 할 것이 작음
        return -p.target_row             # descending → 큰 row 먼저

    result = sorted(passengers, key=_row_depth)
    return _sort_groups(result) if _has_groups(result) else result


def front_to_back(passengers: list[Passenger]) -> list[Passenger]:
    """
    앞열부터 탑승 — 각 행(row)이 독립 그룹 → M = 고유 행 수.
    back_to_front의 역순.
    """
    def _row_depth(p: Passenger) -> int:
        if p.target_seat in _TWIN_AISLE_BACK_COLS:
            return -p.target_row         # 내림차순 → 큰 row(입구 근처) 먼저
        return p.target_row              # 오름차순 → 작은 row 먼저

    result = sorted(passengers, key=_row_depth)
    return _sort_groups(result) if _has_groups(result) else result


def by_section(
    passengers: list[Passenger],
    n_sections: int = 3,
    aft_first: bool = True,
) -> list[Passenger]:
    """
    비행기를 n_sections 구역으로 나눠 탑승 — M = n_sections.
    aft_first=True → 뒤 구역부터 (항공사 일반 관행).
    TwinAisle 후방 섹션의 방향 반전도 반영.
    """
    # 전방/후방 섹션 분리
    front_pax = [p for p in passengers if p.target_seat not in _TWIN_AISLE_BACK_COLS]
    back_pax  = [p for p in passengers if p.target_seat in _TWIN_AISLE_BACK_COLS]

    def _section_front(p: Passenger) -> int:
        max_row = max((q.target_row for q in front_pax), default=1)
        sec = int((p.target_row - 1) / max_row * n_sections)
        return -sec if aft_first else sec

    def _section_back(p: Passenger) -> int:
        max_row = max((q.target_row for q in back_pax), default=1)
        # 후방 섹션: row 작을수록 더 깊음 → row를 반전해서 구역 계산
        depth = max_row - p.target_row  # 0 = 입구(row_max), max = 가장 깊음
        sec = int(depth / max_row * n_sections)
        return -sec if aft_first else sec

    sorted_front = sorted(front_pax, key=_section_front)
    sorted_back  = sorted(back_pax,  key=_section_back)

    # 두 섹션을 n_sections 구역 단위로 교대 삽입
    result: list[Passenger] = []
    fi = bi = 0
    for _ in range(n_sections):
        chunk_f = len(sorted_front) // n_sections
        chunk_b = len(sorted_back)  // n_sections
        if fi < len(sorted_front):
            result.extend(sorted_front[fi:fi + chunk_f]); fi += chunk_f
        if bi < len(sorted_back):
            result.extend(sorted_back[bi:bi + chunk_b]);  bi += chunk_b
    # 나머지 처리
    result.extend(sorted_front[fi:]); result.extend(sorted_back[bi:])

    return _sort_groups(result) if _has_groups(result) else result


def by_seat(passengers: list[Passenger]) -> list[Passenger]:
    """
    창가 → 중간 → 통로 순서로 탑승 — M=3.
    통로 거리는 Passenger.aisle_dist 속성을 사용 (기종별 사전 배정).
    같은 우선순위 그룹 내부는 완전 랜덤.
    """
    max_dist = max((getattr(p, 'aisle_dist', 0) for p in passengers), default=2)
    buckets: dict[int, list[Passenger]] = {d: [] for d in range(max_dist + 1)}
    for p in passengers:
        dist = getattr(p, 'aisle_dist', 0)
        buckets[dist].append(p)

    result: list[Passenger] = []
    for d in range(max_dist, -1, -1):
        grp = list(buckets[d])
        random.shuffle(grp)
        result.extend(grp)
    return result


def weighted_by_seat(passengers: list[Passenger]) -> list[Passenger]:
    """
    FlyingWing 전용: 가중치 채널 주입 BySeat 방식.
    BySeat와 동일하게 창가→중간→통로 순 정렬.
    채널별 75:84 가중치는 engine.run_boarding()에서 처리.
    M = 3 (BySeat와 동일).
    """
    return by_seat(passengers)


def reverse_pyramid(passengers: list[Passenger]) -> list[Passenger]:
    """
    TwinAisle 전용: 양방향 병렬 역피라미드(V자형 대각선) 탑승.

    M = max(전방_행깊이 + max_좌석깊이, 후방_행깊이 + max_좌석깊이)
      ≈ max_row_depth + max_aisle_dist

    그룹 키: (row_depth + seat_depth) — 값이 작을수록 먼저 탑승.
    """
    _FRONT = frozenset('ABCDEFG')
    _BACK  = frozenset('HIJKLMN')

    _SEAT_ORDER: dict[str, int] = {
        'A': 3, 'B': 2, 'C': 1, 'D': 0, 'E': 1, 'F': 2, 'G': 3,
        'H': 3, 'I': 2, 'J': 1, 'K': 0, 'L': 1, 'M': 2, 'N': 3,
    }
    _MAX_ORDER = 3

    front_pax = [p for p in passengers if p.target_seat in _FRONT]
    back_pax  = [p for p in passengers if p.target_seat in _BACK]

    def pyramid_key(p: Passenger, base_row: int, is_front_door: bool) -> tuple[int, int]:
        seat_order = _SEAT_ORDER.get(p.target_seat, 0)
        if is_front_door:
            row_depth = base_row - p.target_row  # 전방: 번호 큰 행 = 깊음
        else:
            row_depth = p.target_row - base_row  # 후방: 번호 작은 행 = 깊음
        seat_depth = _MAX_ORDER - seat_order
        group      = row_depth + seat_depth
        return (group, seat_depth)

    front_max = max((p.target_row for p in front_pax), default=1)
    back_min  = min((p.target_row for p in back_pax),  default=1)

    front_sorted = sorted(front_pax, key=lambda p: pyramid_key(p, front_max, True))
    back_sorted  = sorted(back_pax,  key=lambda p: pyramid_key(p, back_min, False))

    # 전방(95석)·후방(147석) 교대 삽입 — 2:3 비율
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
    Steffen (2008): 짝수열 창가 → 홀수열 창가 → ... — M = N.

    [TwinAisle 후방 섹션 수정]
    후방 섹션(H–N)은 입구가 row_max(21)이므로 row 1이 가장 깊다.
    기존 -target_row 정렬(큰 row 우선)은 방향이 반대 → +target_row 로 반전.

    정렬 키: (-aisle_dist, row_parity, row_depth)
      row_depth = 전방 섹션: -target_row,  후방 섹션: +target_row
    """
    def steffen_key(p: Passenger) -> tuple:
        dist   = getattr(p, 'aisle_dist', 0)
        parity = 0 if p.target_row % 2 == 0 else 1  # 짝수 행 먼저
        # 후방 섹션: row 작을수록 깊음 → 오름차순 (양수)
        # 전방 섹션: row 클수록 깊음  → 내림차순 (음수)
        if p.target_seat in _TWIN_AISLE_BACK_COLS:
            row_depth = p.target_row
        else:
            row_depth = -p.target_row
        return (-dist, parity, row_depth)

    return sorted(passengers, key=steffen_key)


# ── 전략 레지스트리 ───────────────────────────────────────────

STRATEGIES: dict[str, Callable] = {
    "Random":         random_boarding,
    "BackToFront":    back_to_front,
    "FrontToBack":    front_to_back,
    "BySection":      by_section,
    "BySeat":         by_seat,
    "Steffen":        steffen_method,
    "WeightedBySeat": weighted_by_seat,
    "ReversePyramid": reverse_pyramid,
}

# 채널별 주입 가중치 (FlyingWing WeightedBySeat 전용)
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


# ── M값 동적 계산 ─────────────────────────────────────────────

def compute_strategy_m(
    strategy_name: str,
    passengers: list[Passenger],
    n_sections: int = 3,
) -> int:
    """
    전략과 실제 탑승 승객 목록을 바탕으로 우선순위 그룹 수 M을 동적으로 계산.

    [계산 원칙]
      Random         : 1  (그룹 없음)
      BySeat         : 3  (창가 / 중간 / 통로)
      WeightedBySeat : 3  (BySeat와 동일)
      BySection      : n_sections
      BackToFront    : 고유 행(row) 수  ← 각 행이 독립 그룹
      FrontToBack    : 고유 행(row) 수
      Steffen        : N  (각 승객이 독립 그룹)
      ReversePyramid : max_row_depth + max_seat_depth (섹션별 동적)
    """
    n = len(passengers)
    if n == 0:
        return 1

    if strategy_name == "Random":
        return 1

    if strategy_name in ("BySeat", "WeightedBySeat"):
        return 3

    if strategy_name == "BySection":
        return n_sections

    if strategy_name in ("BackToFront", "FrontToBack"):
        # 전·후방 섹션을 구분하지 않고 고유 행 수만 센다
        return len(set(p.target_row for p in passengers))

    if strategy_name == "Steffen":
        return n

    if strategy_name == "ReversePyramid":
        # 전방 섹션과 후방 섹션 각각의 최대 그룹 수를 계산
        front_pax = [p for p in passengers if p.target_seat not in _TWIN_AISLE_BACK_COLS]
        back_pax  = [p for p in passengers if p.target_seat in _TWIN_AISLE_BACK_COLS]
        max_aisle_dist = max(
            (getattr(p, 'aisle_dist', 0) for p in passengers),
            default=2
        )

        def _section_m(pax: list[Passenger], is_back: bool) -> int:
            if not pax:
                return 0
            if is_back:
                min_row = min(p.target_row for p in pax)
                max_row = max(p.target_row for p in pax)
                # 후방: row 작을수록 깊음 → row_depth = row - min_row
                max_row_depth = max_row - min_row
            else:
                min_row = min(p.target_row for p in pax)
                max_row = max(p.target_row for p in pax)
                max_row_depth = max_row - min_row
            # 그룹 수 = (max_row_depth) + (max_seat_depth) + 1
            return max_row_depth + max_aisle_dist + 1

        front_m = _section_m(front_pax, is_back=False)
        back_m  = _section_m(back_pax,  is_back=True)
        # 두 섹션이 병렬로 진행되므로 더 많은 그룹 수가 전체 복잡도를 결정
        return max(front_m, back_m, 1)

    # 알 수 없는 전략: 보수적으로 N 반환
    return n


# ── 복잡도 계산 ───────────────────────────────────────────────

def boarding_complexity(
    strategy_name: str,
    n_passengers: int,
    passengers: Optional[list[Passenger]] = None,
    n_sections: int = 3,
) -> float:
    """
    2022031 논문 복잡도 공식.
        C = ln(M) / ln(N)
    M=1(Random) → C=0,  M=N(Steffen) → C=1

    Parameters
    ----------
    passengers : 실제 Passenger 목록이 있으면 M을 동적으로 계산.
                 없으면 n_passengers만으로 근사 계산(하위 호환).
    n_sections : BySection 전략에서 구역 수 (기본 3).
    """
    if passengers is not None:
        m = compute_strategy_m(strategy_name, passengers, n_sections)
    else:
        # 하위 호환: passengers 없을 때 전략별 근사값
        m = _static_m_fallback(strategy_name, n_passengers, n_sections)

    if m <= 1 or n_passengers <= 1:
        return 0.0
    m = min(m, n_passengers)   # M이 N을 초과하지 않도록 클리핑
    return math.log(m) / math.log(n_passengers)


def _static_m_fallback(
    strategy_name: str,
    n_passengers: int,
    n_sections: int,
) -> int:
    """
    Passenger 목록 없이 전략 이름만으로 M을 근사하는 폴백.
    동적 전략(BackToFront, FrontToBack, ReversePyramid)은
    일반적인 NarrowBody 33행을 기준으로 근사한다.

    NOTE: 정확한 값을 원하면 passengers를 전달해 compute_strategy_m() 사용.
    """
    _FALLBACK: dict[str, int] = {
        "Random":         1,
        "BySeat":         3,
        "WeightedBySeat": 3,
        "BySection":      n_sections,
        # BackToFront/FrontToBack: NarrowBody 33열 기준 근사
        "BackToFront":    33,
        "FrontToBack":    33,
        # Steffen: M = N
        "Steffen":        n_passengers,
        # ReversePyramid: TwinAisle 후방 섹션 기준 (21 rows + 3 seat depths)
        "ReversePyramid": 23,
    }
    return _FALLBACK.get(strategy_name, n_passengers)