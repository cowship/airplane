# analysis/turnaround.py
"""
Phase 4 분석 모듈.

A. Total Turnaround Contribution — 기종/전략별 탑승+하차 합산 시간
B. 탑승률 시나리오 — 100% / 75% / 50% / 30%
C. 소셜 디스턴싱 — 격행 착석 패턴 (논문 4번 문항)

사용 예:
    python analysis/turnaround.py --mode turnaround
    python analysis/turnaround.py --mode occupancy
    python analysis/turnaround.py --mode distancing
    python analysis/turnaround.py --mode all
"""
from __future__ import annotations
from typing import Optional, Callable
import argparse
import os
import random
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from aircraft import get_aircraft, AIRCRAFT
from aircraft.base import AircraftBase
from boarding.methods import get_strategy, STRATEGIES
from boarding.group_model import assign_groups
from boarding.queue_model import QueueManager
from deplaning.methods import get_deplane_method, DEPLANE_METHODS
from simulation.engine import run_boarding
from simulation.deplaning import run_deplaning
from main import generate_passengers, run_boarding_sim, run_deplaning_sim  # type: ignore[import]


# ── 공통 ──────────────────────────────────────────────────────

_TRIALS = 30   # 분석용 반복 횟수

_COLORS = {
    "Random":      "#5B9BD5",
    "BackToFront": "#ED7D31",
    "FrontToBack": "#A5A5A5",
    "BySection":   "#FFC000",
    "BySeat":      "#70AD47",
    "Steffen":     "#9B2D9B",
}

_DEPLANE_DEFAULT = "Random"


def _ensure(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── A. Turnaround ─────────────────────────────────────────────

def run_turnaround(
    aircraft_names: list[str],
    strategies: list[str],
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[str, dict[str, float]]:
    """
    기종 × 전략별 (탑승+하차) 평균 시간 계산.
    Returns {aircraft: {strategy: mean_total_sec}}
    """
    _ensure(out_dir)
    results: dict[str, dict[str, float]] = {}

    for ac_name in aircraft_names:
        results[ac_name] = {}
        print(f"\n  [{ac_name}]")
        for strategy in strategies:
            totals = []
            for _ in range(n_trials):
                airplane = get_aircraft(ac_name)
                bt = run_boarding_sim(strategy, airplane, verbose=False)
                if bt == -1:
                    continue
                passengers = [
                    airplane.seats[r][c]
                    for r, c in airplane.passenger_slots()
                    if airplane.seats[r][c] is not None
                ]
                dm = get_deplane_method(_DEPLANE_DEFAULT)
                dt = run_deplaning(airplane, passengers, dm)  # type: ignore[arg-type]
                if dt == -1:
                    continue
                totals.append((bt + dt) * config.TICK_DURATION)

            mean = float(np.mean(totals)) if totals else float("nan")
            results[ac_name][strategy] = mean
            print(f"    {strategy:<14} {mean:>7.1f}s")

    # ── 그래프 ────────────────────────────────────────────────
    fig, axes = plt.subplots(1, len(aircraft_names),
                             figsize=(5 * len(aircraft_names), 5),
                             sharey=False)
    if len(aircraft_names) == 1:
        axes = [axes]  # type: ignore[list-item]

    for ax, ac_name in zip(axes, aircraft_names):
        vals   = [results[ac_name].get(s, 0) for s in strategies]
        colors = [_COLORS.get(s, "#888") for s in strategies]
        bars   = ax.bar(strategies, vals, color=colors, alpha=0.85)
        ax.set_title(ac_name, fontsize=11, fontweight="bold")
        ax.set_ylabel("Total Time (s)", fontsize=9)
        ax.tick_params(axis="x", rotation=20, labelsize=8)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 5, f"{val:.0f}",
                    ha="center", va="bottom", fontsize=7)

    fig.suptitle("Total Turnaround Contribution (Boarding + Deplaning)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    path = os.path.join(out_dir, "turnaround_comparison.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  저장: {path}")
    return results


# ── B. 탑승률 시나리오 ─────────────────────────────────────────

_OCCUPANCY_RATES = [1.0, 0.75, 0.50, 0.30]


def _subsample_slots(
    airplane: AircraftBase,
    rate: float,
) -> list[tuple[int, str]]:
    """전체 좌석 중 rate 비율만 무작위 선택."""
    all_slots = airplane.passenger_slots()
    k = max(1, round(len(all_slots) * rate))
    return random.sample(all_slots, k)


def run_occupancy(
    aircraft_name: str,
    strategies: list[str],
    occupancy_rates: Optional[list[float]] = None,
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[float, dict[str, float]]:
    """
    탑승률별 전략 비교.
    Returns {rate: {strategy: mean_boarding_sec}}
    """
    _ensure(out_dir)
    rates   = occupancy_rates or _OCCUPANCY_RATES
    results: dict[float, dict[str, float]] = {r: {} for r in rates}

    print(f"\n  [{aircraft_name}] 탑승률 시나리오")
    for rate in rates:
        print(f"  탑승률 {rate*100:.0f}%", end="  ", flush=True)
        for strategy in strategies:
            times = []
            for _ in range(n_trials):
                airplane = get_aircraft(aircraft_name)

                # 선택된 좌석만 승객 배정
                slots = _subsample_slots(airplane, rate)
                passengers = []
                for pid, (row, seat) in enumerate(slots, 1):
                    from passenger import Passenger
                    age = "senior" if random.random() < config.SENIOR_PROB else "adult"
                    p = Passenger(pid, row, seat, age,
                                  airplane.bins_used(row))
                    p.aisle_dist = airplane.aisle_distance(seat)
                    passengers.append(p)

                assign_groups(passengers)
                strategy_fn = get_strategy(strategy)
                q = QueueManager(passengers, strategy_fn,
                                  strategy_name=strategy)
                ticks = run_boarding(airplane, q, len(passengers))
                if ticks != -1:
                    times.append(ticks * config.TICK_DURATION)
            results[rate][strategy] = float(np.mean(times)) if times else float("nan")
        print()

    # ── 그래프: 선 그래프 ─────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    x = [r * 100 for r in rates]
    for strategy in strategies:
        y = [results[r][strategy] for r in rates]
        ax.plot(x, y, marker="o", linewidth=2,
                color=_COLORS.get(strategy, "#333"),
                label=strategy)

    ax.set_title(f"Occupancy Scenario — {aircraft_name}",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Occupancy Rate (%)", fontsize=11)
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"occupancy_{aircraft_name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")
    return results


# ── C. 소셜 디스턴싱 ────────────────────────────────────────────

def _social_distancing_slots(
    airplane: AircraftBase,
    pattern: str = "alternate_rows",
) -> list[tuple[int, str]]:
    """
    소셜 디스턴싱 패턴으로 유효 좌석 목록 반환.

    pattern:
      "alternate_rows"   — 짝수 행만 사용 (격행)
      "window_only"      — 창가 좌석만 (aisle_dist 최대)
      "checkerboard"     — 체커보드 패턴
    """
    all_slots = airplane.passenger_slots()
    max_dist   = max(airplane.aisle_distance(c) for _, c in all_slots)

    if pattern == "alternate_rows":
        return [(r, c) for r, c in all_slots if r % 2 == 0]
    elif pattern == "window_only":
        return [(r, c) for r, c in all_slots
                if airplane.aisle_distance(c) == max_dist]
    elif pattern == "checkerboard":
        return [(r, c) for r, c in all_slots
                if (r + ord(c)) % 2 == 0]
    return all_slots


_SD_PATTERNS = ["alternate_rows", "window_only", "checkerboard"]


def run_social_distancing(
    aircraft_name: str,
    strategies: list[str],
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[str, dict[str, float]]:
    """
    소셜 디스턴싱 패턴별 전략 비교.
    Returns {pattern: {strategy: mean_sec}}
    """
    _ensure(out_dir)
    results: dict[str, dict[str, float]] = {p: {} for p in _SD_PATTERNS}

    print(f"\n  [{aircraft_name}] 소셜 디스턴싱")
    for pattern in _SD_PATTERNS:
        pct = 0
        for strategy in strategies:
            times = []
            for _ in range(n_trials):
                airplane = get_aircraft(aircraft_name)
                slots = _social_distancing_slots(airplane, pattern)
                pct   = round(len(slots) / len(airplane.passenger_slots()) * 100)

                passengers = []
                for pid, (row, seat) in enumerate(slots, 1):
                    from passenger import Passenger
                    age = "senior" if random.random() < config.SENIOR_PROB else "adult"
                    p = Passenger(pid, row, seat, age, airplane.bins_used(row))
                    p.aisle_dist = airplane.aisle_distance(seat)
                    passengers.append(p)

                assign_groups(passengers)
                q = QueueManager(passengers, get_strategy(strategy),
                                  strategy_name=strategy)
                ticks = run_boarding(airplane, q, len(passengers))
                if ticks != -1:
                    times.append(ticks * config.TICK_DURATION)
            results[pattern][strategy] = float(np.mean(times)) if times else float("nan")
        print(f"  {pattern} (~{pct}% 탑승)  완료")

    # ── 그래프: 그룹 막대 ─────────────────────────────────────
    labels = _SD_PATTERNS
    x      = np.arange(len(labels))
    width  = 0.8 / len(strategies)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, strategy in enumerate(strategies):
        vals   = [results[p][strategy] for p in labels]
        offset = (i - len(strategies) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width,
               label=strategy,
               color=_COLORS.get(strategy, "#888"),
               alpha=0.85)

    ax.set_title(f"Social Distancing Scenarios — {aircraft_name}",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(["Alternate Rows", "Window Only", "Checkerboard"],
                       fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"social_distancing_{aircraft_name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")
    return results


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4 분석")
    parser.add_argument(
        "--mode", choices=["turnaround", "occupancy", "distancing", "all"],
        default="all",
    )
    parser.add_argument(
        "--aircraft", "-a", nargs="+",
        default=list(AIRCRAFT.keys()),
    )
    parser.add_argument(
        "--strategies", "-s", nargs="+",
        default=["Random", "BySeat", "BackToFront", "Steffen"],
    )
    parser.add_argument("--trials", "-n", type=int, default=_TRIALS)
    parser.add_argument("--seed",         type=int, default=config.RANDOM_SEED)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print(f"\n{'='*60}")
    print(f"  Phase 4 분석  |  반복: {args.trials}  |  기종: {args.aircraft}")
    print(f"{'='*60}")

    if args.mode in ("turnaround", "all"):
        print("\n▶ A. Turnaround 비교")
        run_turnaround(args.aircraft, args.strategies, args.trials)

    if args.mode in ("occupancy", "all"):
        print("\n▶ B. 탑승률 시나리오")
        for ac in args.aircraft:
            run_occupancy(ac, args.strategies, n_trials=args.trials)

    if args.mode in ("distancing", "all"):
        print("\n▶ C. 소셜 디스턴싱")
        for ac in args.aircraft:
            run_social_distancing(ac, args.strategies, n_trials=args.trials)


if __name__ == "__main__":
    main()