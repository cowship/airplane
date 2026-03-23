# main.py
"""
비행기 탑승/하차 시뮬레이션 진입점.

사용 예:
    python main.py                                    # 기본 (NarrowBody, 탑승)
    python main.py --aircraft twin_aisle              # 기종 변경
    python main.py --mode deplaning                   # 하차 시뮬레이션
    python main.py --mode both                        # 탑승 + 하차
    python main.py --aircraft flying_wing --mode both
"""
from __future__ import annotations
from typing import Optional, Callable
import argparse
import random

import config
from passenger import Passenger
from aircraft import get_aircraft, AIRCRAFT
from aircraft.base import AircraftBase
from boarding.methods import get_strategy, STRATEGIES
from boarding.group_model import assign_groups
from boarding.queue_model import QueueManager
from deplaning.methods import get_deplane_method, DEPLANE_METHODS
from simulation.engine import run_boarding
from simulation.deplaning import run_deplaning


# ── 승객 생성 ────────────────────────────────────────────────

def generate_passengers(
    airplane: AircraftBase,
    bag_weights: Optional[tuple] = None,
) -> list[Passenger]:
    """항공기의 모든 유효 좌석에 대한 승객 객체 리스트 생성."""
    passengers: list[Passenger] = []
    pid = 1
    for (row, seat) in airplane.passenger_slots():
        age = "senior" if random.random() < config.SENIOR_PROB else "adult"
        p = Passenger(
            pass_id     = pid,
            target_row  = row,
            target_seat = seat,
            age_group   = age,
            n_bins_used = airplane.bins_used(row),
            bag_weights = bag_weights,
        )
        # 기종별 통로 거리 배정 (by_seat 전략에서 사용)
        p.aisle_dist = airplane.aisle_distance(seat)
        passengers.append(p)
        pid += 1
    return passengers


# ── 탑승 시뮬레이션 ──────────────────────────────────────────

def run_boarding_sim(
    strategy_name: str,
    airplane: AircraftBase,
    non_compliance_rate: Optional[float] = None,
    bag_weights: Optional[tuple]         = None,
    verbose: bool                        = True,
) -> int:
    from boarding.methods import STRATEGY_CHANNEL_WEIGHTS
    passengers = generate_passengers(airplane, bag_weights=bag_weights)
    assign_groups(passengers)

    strategy  = get_strategy(strategy_name)
    queue_mgr = QueueManager(
        passengers,
        strategy,
        strategy_name       = strategy_name,
        non_compliance_rate = non_compliance_rate,
    )

    # WeightedBySeat 전략은 채널별 가중치 주입 사용
    channel_weights = STRATEGY_CHANNEL_WEIGHTS.get(strategy_name)

    ticks = run_boarding(
        airplane,
        queue_mgr,
        total_passengers = len(passengers),
        channel_weights  = channel_weights,
    )

    if verbose:
        if ticks == -1:
            print(f"  [{strategy_name}] ⚠️  데드락")
        else:
            sec = ticks * config.TICK_DURATION
            print(
                f"  [탑승/{strategy_name:<14}] "
                f"{ticks:>6} ticks = {sec:>7.1f}s = {sec/60:.1f}분"
            )
    return ticks


# ── 하차 시뮬레이션 ──────────────────────────────────────────

def run_deplaning_sim(
    deplane_name: str,
    airplane: AircraftBase,
    passengers: list[Passenger],
    verbose: bool = True,
) -> int:
    method = get_deplane_method(deplane_name)
    ticks  = run_deplaning(airplane, passengers, method)  # type: ignore[arg-type]

    if verbose:
        if ticks == -1:
            print(f"  [{deplane_name}] ⚠️  데드락")
        else:
            sec = ticks * config.TICK_DURATION
            print(
                f"  [하차/{deplane_name:<14}] "
                f"{ticks:>6} ticks = {sec:>7.1f}s = {sec/60:.1f}분"
            )
    return ticks


# ── 편의 함수 (monte_carlo 등에서 사용) ─────────────────────

def run_simulation(
    strategy_name: str,
    aircraft_name: str                   = "narrow_body",
    num_rows: Optional[int]              = None,
    non_compliance_rate: Optional[float] = None,
    bag_weights: Optional[tuple]         = None,
    verbose: bool                        = True,
) -> int:
    airplane = get_aircraft(aircraft_name)
    # num_rows 오버라이드 (NarrowBody 전용 호환성)
    if num_rows is not None and hasattr(airplane, 'num_rows'):
        object.__setattr__(airplane, 'num_rows', num_rows)
    return run_boarding_sim(
        strategy_name,
        airplane,
        non_compliance_rate = non_compliance_rate,
        bag_weights         = bag_weights,
        verbose             = verbose,
    )


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="비행기 탑승/하차 시뮬레이션")
    parser.add_argument(
        "--aircraft", "-a",
        choices=list(AIRCRAFT.keys()),
        default="narrow_body",
        help="항공기 기종 (기본: narrow_body)",
    )
    parser.add_argument(
        "--strategy", "-s",
        choices=list(STRATEGIES.keys()) + ["all"],
        default="all",
        help="탑승 전략 (기본: all)",
    )
    parser.add_argument(
        "--deplane", "-d",
        choices=list(DEPLANE_METHODS.keys()) + ["all"],
        default="all",
        help="하차 방법 (기본: all)",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["boarding", "deplaning", "both"],
        default="boarding",
        help="시뮬레이션 모드 (기본: boarding)",
    )
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    args = parser.parse_args()

    random.seed(args.seed)

    airplane = get_aircraft(args.aircraft)
    print(f"\n{'='*60}")
    print(f"  기종: {airplane.name}  |  총 좌석: {airplane.total_seats}  |  seed: {args.seed}")
    print(f"{'='*60}")

    strategies = list(STRATEGIES.keys()) if args.strategy == "all" else [args.strategy]
    deplane_names = list(DEPLANE_METHODS.keys()) if args.deplane == "all" else [args.deplane]

    if args.mode in ("boarding", "both"):
        print("\n── 탑승 시뮬레이션 ──")
        for name in strategies:
            airplane.reset()
            run_boarding_sim(name, airplane)

    if args.mode in ("deplaning", "both"):
        print("\n── 하차 시뮬레이션 ──")
        # 하차 시뮬레이션: 탑승 완료 상태에서 시작
        for deplane_name in deplane_names:
            # 매번 새로 탑승시킨 뒤 하차
            airplane.reset()
            passengers = generate_passengers(airplane)
            assign_groups(passengers)
            strategy   = get_strategy(strategies[0])
            queue_mgr  = QueueManager(passengers, strategy, strategy_name=strategies[0])
            run_boarding(airplane, queue_mgr, total_passengers=len(passengers))
            run_deplaning_sim(deplane_name, airplane, passengers)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()