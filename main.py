# main.py
"""
단일 시뮬레이션 실행 진입점.

사용 예:
    python main.py                        # 기본 전략 비교
    python main.py --strategy BySeat      # 특정 전략만
    python main.py --trials 500 --strategy Steffen
"""
import argparse
import random
import sys

import config
from passenger import Passenger
from airplane import Airplane
from boarding.methods import get_strategy, STRATEGIES
from boarding.queue_model import QueueManager
from simulation.engine import run_boarding


# ── 승객 생성 ────────────────────────────────────────────────

def generate_passengers(
    airplane: Airplane,
    bag_weights: tuple = None,
) -> list[Passenger]:
    """비행기의 모든 좌석에 대한 승객 객체 리스트 생성."""
    passengers = []
    pid = 1
    for row in range(1, airplane.num_rows + 1):
        for seat in airplane.SEAT_COLS:
            age = "senior" if random.random() < config.SENIOR_PROB else "adult"
            p = Passenger(
                pass_id     = pid,
                target_row  = row,
                target_seat = seat,
                age_group   = age,
                n_bins_used = airplane.bins_used(row),
                bag_weights = bag_weights,
            )
            passengers.append(p)
            pid += 1
    return passengers


# ── 단일 실행 ────────────────────────────────────────────────

def run_simulation(
    strategy_name: str,
    num_rows: int               = 33,
    non_compliance_rate: float  = None,
    bag_weights: tuple          = None,
    verbose: bool               = True,
) -> int:
    """
    시뮬레이션을 한 번 실행하고 소요 틱 수를 반환.

    Returns
    -------
    int  소요 틱 수 (-1이면 데드락)
    """
    airplane    = Airplane(num_rows=num_rows)
    passengers  = generate_passengers(airplane, bag_weights=bag_weights)
    strategy    = get_strategy(strategy_name)

    queue_mgr = QueueManager(
        passengers,
        strategy,
        non_compliance_rate=non_compliance_rate,
    )

    ticks = run_boarding(airplane, queue_mgr, total_passengers=len(passengers))

    if ticks == -1:
        if verbose:
            print(f"[{strategy_name}] ⚠️  데드락 감지 (MAX_TICKS 초과)")
        return -1

    real_sec = ticks * config.TICK_DURATION
    if verbose:
        print(
            f"[{strategy_name:<14}] "
            f"완료: {ticks:>6} ticks "
            f"= {real_sec:>7.1f}s "
            f"= {real_sec/60:.1f}분"
        )
    return ticks


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="비행기 탑승 시뮬레이션")
    parser.add_argument(
        "--strategy", "-s",
        choices=list(STRATEGIES.keys()) + ["all"],
        default="all",
        help="실행할 탑승 전략 (기본: all)",
    )
    parser.add_argument("--rows",   type=int,   default=33)
    parser.add_argument("--seed",   type=int,   default=config.RANDOM_SEED)
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"\n{'='*55}")
    print(f"  비행기 탑승 시뮬레이션  |  행: {args.rows}  |  seed: {args.seed}")
    print(f"{'='*55}")

    targets = list(STRATEGIES.keys()) if args.strategy == "all" else [args.strategy]
    for name in targets:
        run_simulation(name, num_rows=args.rows)

    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()