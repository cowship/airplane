# boarding/group_model.py
"""
그룹 승객 모델 (2022019 논문 기반).

핵심 행동:
  - 그룹은 큐에서 연속된 위치를 차지한다.
  - 그룹 내부는 창가 → 중간 → 통로 순으로 자동 정렬된다.
  - 비순응은 그룹 단위로 결정된다 (그룹 전체가 함께 이동).
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import random
import config

if TYPE_CHECKING:
    from passenger import Passenger

# 좌석별 탑승 우선순위 (낮을수록 먼저)
_SEAT_PRIORITY: dict[str, int] = {
    'A': 0, 'F': 0,   # 창가
    'B': 1, 'E': 1,   # 중간
    'C': 2, 'D': 2,   # 통로
}


def assign_groups(passengers: list[Passenger]) -> list[Passenger]:
    """
    승객 리스트에 group_id를 무작위 배정한다.

    - 그룹 크기: 1(70%), 2(20%), 3(10%)
    - 그룹 전체가 disobedient 여부를 동일하게 공유한다.
    """
    if not config.USE_GROUPS:
        return passengers

    pool = list(passengers)
    random.shuffle(pool)   # 좌석 위치와 무관하게 랜덤 그룹 형성

    group_id = 1
    i = 0
    while i < len(pool):
        size = min(
            random.choices([1, 2, 3], weights=config.GROUP_PROB)[0],
            len(pool) - i,
        )
        is_disobedient = random.random() < config.GROUP_DISOBEY_PROB
        for j in range(i, i + size):
            pool[j].group_id    = group_id
            pool[j].disobedient = is_disobedient
        group_id += 1
        i += size

    return pool


def sort_group_internally(queue: list[Passenger]) -> list[Passenger]:
    """
    큐에서 같은 group_id를 가진 연속 블록을 찾아
    그룹 내부를 창가 → 중간 → 통로 순으로 재정렬한다.
    """
    if not queue:
        return queue

    result: list[Passenger] = []
    i = 0
    while i < len(queue):
        gid = queue[i].group_id

        # group_id == 0 → 개인으로 취급
        if gid == 0:
            result.append(queue[i])
            i += 1
            continue

        # 연속된 같은 group_id 묶기
        j = i + 1
        while j < len(queue) and queue[j].group_id == gid:
            j += 1

        block = queue[i:j]
        # 창가 → 중간 → 통로 순 정렬
        block.sort(key=lambda p: _SEAT_PRIORITY.get(p.target_seat, 9))
        result.extend(block)
        i = j

    return result