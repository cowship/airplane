# boarding/queue_model.py
"""
승객 큐(Queue) 후처리:
  1. 늦게 도착한 승객 → 큐 끝으로 이동
  2. 복잡도 기반 새치기 (2022031): R_J = R_J_MAX × C
     - C는 실제 Passenger 목록으로 동적 계산
  3. 그룹 단위 비순응 (2022019): 그룹 전체가 함께 이동
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional
import random
import config

if TYPE_CHECKING:
    from passenger import Passenger
    StrategyFunc = Callable[[list[Passenger]], list[Passenger]]


class QueueManager:
    """
    탑승 전략 적용 → 지각/새치기 처리 → 순서대로 승객 반환.

    Parameters
    ----------
    strategy_name : 복잡도 계산에 사용 (None 이면 고정 비율 사용)
    n_sections    : BySection 전략에서 구역 수 (기본 3)
    """

    def __init__(
        self,
        passengers: list[Passenger],
        strategy_func: StrategyFunc,
        strategy_name: Optional[str]         = None,
        non_compliance_rate: Optional[float] = None,
        late_arrival_rate: Optional[float]   = None,
        n_sections: int                      = 3,
    ) -> None:
        n = len(passengers)

        # ── 새치기 비율 결정 ──────────────────────────────────────
        if strategy_name is not None:
            # 실제 passengers를 넘겨 M을 동적으로 계산
            from boarding.methods import boarding_complexity
            c  = boarding_complexity(
                strategy_name, n,
                passengers=passengers,
                n_sections=n_sections,
            )
            rj = config.R_J_MAX * c
        else:
            rj = (
                non_compliance_rate
                if non_compliance_rate is not None
                else config.NON_COMPLIANCE_RATE
            )

        lar = (
            late_arrival_rate
            if late_arrival_rate is not None
            else config.LATE_ARRIVAL_RATE
        )

        # 1) 전략에 따라 정렬
        self.queue: list[Passenger] = strategy_func(passengers)

        # 2) 지각 승객 처리
        self._apply_late_arrivals(lar)

        # 3) 새치기
        self._apply_queue_jumping(rj)

    # ── 공개 ────────────────────────────────────────────────

    def pop_next(self) -> Optional[Passenger]:
        """다음 탑승 승객 반환. 큐가 비면 None."""
        return self.queue.pop(0) if self.queue else None

    def __len__(self) -> int:
        return len(self.queue)

    # ── 내부 ────────────────────────────────────────────────

    def _apply_late_arrivals(self, rate: float) -> None:
        """지각 승객을 큐 끝으로 이동. 그룹이면 그룹 전체 이동."""
        n_late = round(len(self.queue) * rate)
        if n_late == 0:
            return

        gids = list({p.group_id for p in self.queue})
        random.shuffle(gids)

        late_gids: set[int] = set()
        late_count = 0
        for gid in gids:
            if late_count >= n_late:
                break
            late_gids.add(gid)
            late_count += sum(1 for p in self.queue if p.group_id == gid)

        late = [p for p in self.queue if p.group_id in late_gids]
        rest = [p for p in self.queue if p.group_id not in late_gids]
        self.queue = rest + late

    def _apply_queue_jumping(self, rate: float) -> None:
        """
        이항분포 기반 새치기 (2022031 수식 근사).
        disobedient 승객(또는 그룹)만 새치기.
        그룹이면 그룹 전체가 같은 방향으로 이동.
        """
        if rate <= 0:
            return

        half_r  = config.QUEUE_JUMP_RANGE // 2
        all_gids = list({p.group_id for p in self.queue if p.disobedient})
        n_jumpers = round(len(all_gids) * rate)
        if n_jumpers == 0:
            return

        jump_gids = set(random.sample(all_gids, min(n_jumpers, len(all_gids))))

        new_queue: list[Passenger] = list(self.queue)
        for gid in jump_gids:
            positions = [i for i, p in enumerate(new_queue) if p.group_id == gid]
            if not positions:
                continue
            first_pos = positions[0]
            members   = [new_queue[i] for i in positions]

            for i in sorted(positions, reverse=True):
                new_queue.pop(i)

            shift   = random.randint(-half_r, half_r)
            new_pos = max(0, min(len(new_queue), first_pos + shift))

            for k, member in enumerate(members):
                new_queue.insert(new_pos + k, member)

        self.queue = new_queue