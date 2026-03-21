# boarding/queue_model.py
"""
승객 큐(Queue) 후처리:
  1. 늦게 도착한 승객(Late Arrival) → 큐 끝으로 이동
  2. 비순응 승객(Non-compliance)    → 인접 위치로 랜덤 스왑
"""
from __future__ import annotations
from typing import Callable, Optional, TYPE_CHECKING
import random
import config

if TYPE_CHECKING:
    from passenger import Passenger


class QueueManager:
    """
    탑승 전략 적용 → 비순응/지각 처리 → 순서대로 승객 반환.
    """

    def __init__(
        self,
        passengers: list,
        strategy_func: Callable,
        non_compliance_rate: Optional[float] = None,
        late_arrival_rate: Optional[float]   = None,
    ):
        ncr = non_compliance_rate if non_compliance_rate is not None \
              else config.NON_COMPLIANCE_RATE
        lar = late_arrival_rate if late_arrival_rate is not None \
              else config.LATE_ARRIVAL_RATE

        # 1) 전략에 따라 정렬
        self.queue: list = strategy_func(passengers)

        # 2) 지각 승객 처리 (큐 끝으로)
        self._apply_late_arrivals(lar)

        # 3) 비순응 처리 (인접 위치 스왑)
        self._apply_non_compliance(ncr)

    # ── 공개 ────────────────────────────────────────────────

    def pop_next(self) -> Optional[Passenger]:
        """다음 탑승 승객 반환. 큐가 비면 None."""
        return self.queue.pop(0) if self.queue else None

    def __len__(self) -> int:
        return len(self.queue)

    # ── 내부 ────────────────────────────────────────────────

    def _apply_late_arrivals(self, rate: float) -> None:
        n_late = round(len(self.queue) * rate)
        if n_late == 0:
            return
        indices = random.sample(range(len(self.queue)), n_late)
        indices_set = set(indices)
        late = [self.queue[i] for i in indices_set]
        rest = [p for i, p in enumerate(self.queue) if i not in indices_set]
        self.queue = rest + late

    def _apply_non_compliance(self, rate: float) -> None:
        """
        비순응 승객은 이항분포 기반으로 ±QUEUE_JUMP_RANGE/2 범위 내에서
        위치가 섞인다. (2022031 수식 근사)
        """
        n = len(self.queue)
        n_jumpers = round(n * rate)
        if n_jumpers == 0:
            return

        half_r = config.QUEUE_JUMP_RANGE // 2
        indices = random.sample(range(n), n_jumpers)

        for idx in indices:
            # 이항분포로 이동 거리 결정: 평균 0, 범위 ±half_r
            shift = random.randint(-half_r, half_r)
            new_idx = max(0, min(n - 1, idx + shift))
            if new_idx != idx:
                self.queue[idx], self.queue[new_idx] = \
                    self.queue[new_idx], self.queue[idx]