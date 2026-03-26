# analysis/pandemic.py
"""
팬데믹 상황 탑승 분석 (문항 4번).

분석 항목:
  A. 탑승률 70% / 50% / 30% 별 전략 비교 (NarrowBody 기준)
  B. 3가지 기종 × 3가지 탑승률 최적 전략 도출
  C. 좌석 배치 패턴별 비교
       - random    : 무작위로 c% 선택
       - alternate : 격행 배치 (짝수/홀수 행 교대)
       - distanced : 행·열 모두 분산

결과 파일:
  results/pandemic_strategy_comparison.png
  results/pandemic_aircraft_comparison.png
  results/pandemic_heatmap.png
  results/pandemic_summary.json

사용 예:
    python analysis/pandemic.py
    python analysis/pandemic.py --mode strategy
    python analysis/pandemic.py --mode aircraft
    python analysis/pandemic.py --aircraft narrow_body --trials 100
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sys
from datetime import datetime
from typing import Optional

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
from passenger import Passenger
from simulation.pandemic import (
    run_pandemic_boarding,
    get_distance,
    DISTANCE_MAP,
)

# ── 상수 ──────────────────────────────────────────────────────

OCCUPANCY_RATES  = [0.70, 0.50, 0.30]
DEFAULT_TRIALS   = 50

_STRATEGY_COLORS = {
    "Random":      "#5B9BD5",
    "BackToFront": "#ED7D31",
    "FrontToBack": "#A5A5A5",
    "BySection":   "#FFC000",
    "BySeat":      "#70AD47",
    "Steffen":     "#9B2D9B",
}
_RATE_COLORS = {0.70: "#2ECC71", 0.50: "#F39C12", 0.30: "#E74C3C"}
_RATE_LABELS = {0.70: "70%", 0.50: "50%", 0.30: "30%"}


# ── 좌석 샘플링 패턴 ──────────────────────────────────────────

def sample_seats(
    airplane: AircraftBase,
    occupancy_rate: float,
    pattern: str = "random",
) -> list[tuple[int, str]]:
    """
    탑승률과 배치 패턴에 따라 유효 좌석 목록 반환.

    pattern:
      "random"    — 무작위로 c% 선택
      "alternate" — 격행 (홀수 행만 또는 짝수 행만)
      "distanced" — 행·열 모두 분산 (2행 간격 + 창가·통로 교대)
    """
    all_slots = airplane.passenger_slots()
    n_total   = len(all_slots)
    n_select  = round(n_total * occupancy_rate)

    if pattern == "random":
        return random.sample(all_slots, n_select)

    elif pattern == "alternate":
        filtered = [(r, c) for r, c in all_slots if r % 2 == 1]
        if len(filtered) < n_select:
            filtered = [(r, c) for r, c in all_slots if r % 2 == 0]
        return filtered[:n_select]

    elif pattern == "distanced":
        max_dist = max(airplane.aisle_distance(c) for _, c in all_slots)
        # 짝수 행 + 창가/통로 교대
        filtered = [
            (r, c) for r, c in all_slots
            if r % 2 == 1 and airplane.aisle_distance(c) >= max_dist - 1
        ]
        if len(filtered) < n_select:
            # 부족하면 홀수 행 + 전체 열로 보충
            extra = [(r, c) for r, c in all_slots if r % 2 == 1]
            filtered = list({*filtered, *extra})
        return random.sample(filtered, min(n_select, len(filtered)))

    return random.sample(all_slots, n_select)


# ── 단일 시뮬레이션 실행 ──────────────────────────────────────

def run_one(
    airplane: AircraftBase,
    strategy_name: str,
    occupied_slots: list[tuple[int, str]],
    occupied_set: set[tuple[int, str]],
    aisle_d: int,
) -> int:
    """
    occupied_slots 에 해당하는 승객만 생성해 시뮬레이션 실행.
    Returns 틱 수 (-1: 실패).
    """
    passengers: list[Passenger] = []
    for pid, (row, seat) in enumerate(occupied_slots, 1):
        age = "senior" if random.random() < config.SENIOR_PROB else "adult"
        p   = Passenger(pid, row, seat, age, airplane.bins_used(row))
        p.aisle_dist = airplane.aisle_distance(seat)
        passengers.append(p)

    assign_groups(passengers)
    q = QueueManager(passengers, get_strategy(strategy_name),
                     strategy_name=strategy_name)

    return run_pandemic_boarding(
        airplane, q, len(passengers),
        occupied_seats=occupied_set,
        aisle_distance=aisle_d,
    )


# ── A. 전략 × 탑승률 비교 (단일 기종) ────────────────────────

def run_strategy_comparison(
    aircraft_name: str,
    strategies: list[str],
    occupancy_rates: Optional[list[float]] = None,
    n_trials: int = DEFAULT_TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict:
    """
    NarrowBody 기준 전략 × 탑승률 비교.
    Returns { rate: { strategy: mean_sec } }
    """
    os.makedirs(out_dir, exist_ok=True)
    rates   = occupancy_rates or OCCUPANCY_RATES
    results = {r: {s: [] for s in strategies} for r in rates}

    print(f"\n  [{aircraft_name}] 팬데믹 전략 비교")

    for rate in rates:
        d = get_distance(rate)
        print(f"  탑승률 {rate*100:.0f}%  (거리 d={d})", end="  ", flush=True)
        for strategy in strategies:
            for _ in range(n_trials):
                airplane = get_aircraft(aircraft_name)
                slots    = sample_seats(airplane, rate)
                s_set    = set(slots)
                t = run_one(airplane, strategy, slots, s_set, d)
                if t != -1:
                    results[rate][strategy].append(t * config.TICK_DURATION)
            mean = np.mean(results[rate][strategy]) if results[rate][strategy] else float("nan")
            print(f"{strategy}:{mean:.0f}s", end="  ", flush=True)
        print()

    # ── 평균값으로 정리 ──────────────────────────────────────
    summary = {
        r: {s: float(np.mean(v)) if v else float("nan")
            for s, v in results[r].items()}
        for r in rates
    }

    _plot_strategy_comparison(summary, strategies, aircraft_name, out_dir)
    return summary


def _plot_strategy_comparison(
    summary: dict,
    strategies: list[str],
    aircraft_name: str,
    out_dir: str,
) -> None:
    rates  = list(summary.keys())
    x      = np.arange(len(strategies))
    width  = 0.25
    n_rates = len(rates)

    fig, ax = plt.subplots(figsize=(11, 6))

    for i, rate in enumerate(rates):
        vals   = [summary[rate].get(s, 0) for s in strategies]
        offset = (i - n_rates / 2 + 0.5) * width
        bars   = ax.bar(
            x + offset, vals, width,
            label=f"탑승률 {_RATE_LABELS[rate]}  (d={get_distance(rate)})",
            color=_RATE_COLORS[rate], alpha=0.82,
        )
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 4, f"{v:.0f}",
                    ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(strategies, rotation=12, fontsize=9)
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.set_title(
        f"[Pandemic] Boarding Strategy × Occupancy Rate\n{aircraft_name}",
        fontsize=13, fontweight="bold",
    )
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # 탑승률별 최적 전략 주석
    for i, rate in enumerate(rates):
        best_s = min(summary[rate], key=summary[rate].get)
        best_v = summary[rate][best_s]
        best_x = strategies.index(best_s)
        offset = (i - n_rates / 2 + 0.5) * width
        ax.annotate(
            "★",
            xy=(best_x + offset, best_v),
            xytext=(best_x + offset, best_v + 20),
            ha="center", fontsize=13,
            color=_RATE_COLORS[rate],
        )

    fig.tight_layout()
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"pandemic_strategy_{aircraft_name}_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")


# ── B. 3 기종 × 탑승률 최적 전략 ─────────────────────────────

def run_aircraft_comparison(
    aircraft_names: list[str],
    strategies: list[str],
    occupancy_rates: Optional[list[float]] = None,
    n_trials: int = DEFAULT_TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict:
    """
    기종 × 탑승률별 최적 전략과 소요 시간을 정리.
    Returns { aircraft: { rate: { strategy: mean_sec } } }
    """
    os.makedirs(out_dir, exist_ok=True)
    rates   = occupancy_rates or OCCUPANCY_RATES
    results = {}

    for ac_name in aircraft_names:
        results[ac_name] = {}
        print(f"\n  [{ac_name}] 기종 비교 중")
        for rate in rates:
            d = get_distance(rate)
            results[ac_name][rate] = {}
            for strategy in strategies:
                times = []
                for _ in range(n_trials):
                    airplane = get_aircraft(ac_name)
                    slots    = sample_seats(airplane, rate)
                    s_set    = set(slots)
                    t = run_one(airplane, strategy, slots, s_set, d)
                    if t != -1:
                        times.append(t * config.TICK_DURATION)
                results[ac_name][rate][strategy] = (
                    float(np.mean(times)) if times else float("nan")
                )
            best = min(results[ac_name][rate], key=results[ac_name][rate].get)
            print(
                f"    {rate*100:.0f}%: 최적={best}  "
                f"({results[ac_name][rate][best]:.0f}s)"
            )

    _plot_aircraft_heatmap(results, strategies, aircraft_names, rates, out_dir)
    _plot_aircraft_bar(results, strategies, aircraft_names, rates, out_dir)
    return results


def _plot_aircraft_heatmap(
    results: dict,
    strategies: list[str],
    aircraft_names: list[str],
    rates: list[float],
    out_dir: str,
) -> None:
    """기종 × 전략 × 탑승률 히트맵 (탑승률별 서브플롯)."""
    fig, axes = plt.subplots(
        1, len(rates),
        figsize=(5 * len(rates), 1 + len(aircraft_names) * 0.9),
        sharey=True,
    )
    if len(rates) == 1:
        axes = [axes]

    for ax, rate in zip(axes, rates):
        matrix = np.array([
            [results[ac][rate].get(s, float("nan")) for s in strategies]
            for ac in aircraft_names
        ])
        im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn_r")
        ax.set_xticks(range(len(strategies)))
        ax.set_xticklabels(strategies, rotation=30, ha="right", fontsize=8)
        ax.set_yticks(range(len(aircraft_names)))
        ax.set_yticklabels(aircraft_names, fontsize=9)
        ax.set_title(f"Boarding rate {_RATE_LABELS[rate]}  (d={get_distance(rate)})",
                     fontsize=10, fontweight="bold")

        for i in range(len(aircraft_names)):
            for j in range(len(strategies)):
                v = matrix[i, j]
                ax.text(j, i, f"{v:.0f}s" if not np.isnan(v) else "-",
                        ha="center", va="center", fontsize=7,
                        color="white" if v > np.nanmean(matrix) else "black")

    fig.suptitle("[Pandemic] Boarding Time Heatmap: Aircraft × Strategy",
                 fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"pandemic_heatmap_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")


def _plot_aircraft_bar(
    results: dict,
    strategies: list[str],
    aircraft_names: list[str],
    rates: list[float],
    out_dir: str,
) -> None:
    """기종별 최적 전략 소요 시간 막대 그래프."""
    fig, axes = plt.subplots(
        1, len(aircraft_names),
        figsize=(5 * len(aircraft_names), 5),
        sharey=False,
    )
    if len(aircraft_names) == 1:
        axes = [axes]

    for ax, ac_name in zip(axes, aircraft_names):
        for i, rate in enumerate(rates):
            vals   = [results[ac_name][rate].get(s, 0) for s in strategies]
            colors = [_STRATEGY_COLORS.get(s, "#888") for s in strategies]
            offset = (i - len(rates) / 2 + 0.5) * (0.8 / len(rates))
            x      = np.arange(len(strategies))
            ax.bar(x + offset, vals, 0.8 / len(rates),
                   color=colors,
                   alpha=0.5 + 0.15 * i,
                   label=f"{_RATE_LABELS[rate]}")

        ax.set_xticks(range(len(strategies)))
        ax.set_xticklabels(strategies, rotation=15, fontsize=8)
        ax.set_title(ac_name, fontsize=11, fontweight="bold")
        ax.set_ylabel("Mean Boarding Time (s)", fontsize=9)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
        ax.legend(fontsize=8, title="Boarding Rate")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("[Pandemic] Optimal Strategy per Aircraft × Occupancy",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"pandemic_aircraft_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")


# ── C. 좌석 배치 패턴 비교 ────────────────────────────────────

def run_pattern_comparison(
    aircraft_name: str,
    strategies: list[str],
    occupancy_rates: Optional[list[float]] = None,
    n_trials: int = DEFAULT_TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict:
    """
    random / alternate / distanced 패턴별 전략 비교.
    """
    os.makedirs(out_dir, exist_ok=True)
    rates    = occupancy_rates or [0.50]
    patterns = ["random", "alternate", "distanced"]
    results  = {
        rate: {pat: {s: [] for s in strategies} for pat in patterns}
        for rate in rates
    }

    print(f"\n  [{aircraft_name}] 좌석 배치 패턴 비교")

    for rate in rates:
        d = get_distance(rate)
        for pattern in patterns:
            print(f"  탑승률 {rate*100:.0f}%  패턴:{pattern}", end="  ", flush=True)
            for strategy in strategies:
                for _ in range(n_trials):
                    airplane = get_aircraft(aircraft_name)
                    slots    = sample_seats(airplane, rate, pattern=pattern)
                    s_set    = set(slots)
                    t = run_one(airplane, strategy, slots, s_set, d)
                    if t != -1:
                        results[rate][pattern][strategy].append(
                            t * config.TICK_DURATION
                        )
            print()

    summary = {
        rate: {
            pat: {
                s: float(np.mean(v)) if v else float("nan")
                for s, v in results[rate][pat].items()
            }
            for pat in patterns
        }
        for rate in rates
    }

    _plot_pattern_comparison(summary, strategies, aircraft_name, rates, out_dir)
    return summary


def _plot_pattern_comparison(
    summary: dict,
    strategies: list[str],
    aircraft_name: str,
    rates: list[float],
    out_dir: str,
) -> None:
    patterns      = ["random", "alternate", "distanced"]
    pattern_colors = {"random": "#7EC8E3", "alternate": "#FFB347", "distanced": "#90EE90"}
    x     = np.arange(len(strategies))
    width = 0.28

    for rate in rates:
        fig, ax = plt.subplots(figsize=(10, 5))
        for i, pat in enumerate(patterns):
            vals   = [summary[rate][pat].get(s, 0) for s in strategies]
            offset = (i - 1) * width
            bars = ax.bar(x + offset, vals, width,
                   label=pat.capitalize(),
                   color=pattern_colors[pat], alpha=0.85)
            for bar, v in zip(bars, vals):
                if v > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 3, f"{v:.0f}",
                            ha="center", va="bottom", fontsize=7)

        ax.set_xticks(x)
        ax.set_xticklabels(strategies, rotation=12, fontsize=9)
        ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
        ax.set_title(
            f"[Pandemic] Seating Pattern × Strategy  "
            f"(Boarding Rate {_RATE_LABELS[rate]}, d={get_distance(rate)})\n{aircraft_name}",
            fontsize=12, fontweight="bold",
        )
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        ts   = datetime.now().strftime("%H%M%S")
        rate_str = str(int(rate * 100))
        path = os.path.join(
            out_dir, f"pandemic_pattern_{aircraft_name}_{rate_str}pct_{ts}.png"
        )
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  저장: {path}")


# ── 요약 JSON 저장 ────────────────────────────────────────────

def save_summary(data: dict, label: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"pandemic_{label}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2,
                  default=lambda x: round(x, 2) if isinstance(x, float) else str(x))
    print(f"  JSON 저장: {path}")


# ── 결과 요약 출력 ────────────────────────────────────────────

def print_optimal_table(summary: dict, aircraft_name: str) -> None:
    """전략 비교 요약 테이블 출력."""
    print(f"\n  {'='*55}")
    print(f"  [{aircraft_name}] 팬데믹 최적 전략 요약")
    print(f"  {'탑승률':<10} {'d':>4}  {'최적 전략':<16} {'시간(s)':>8}")
    print(f"  {'-'*55}")
    for rate, strats in summary.items():
        d    = get_distance(float(rate))
        best = min(strats, key=strats.get)
        val  = strats[best]
        print(f"  {_RATE_LABELS.get(float(rate), str(rate)):<10} {d:>4}  {best:<16} {val:>8.1f}s")
    print(f"  {'='*55}\n")


# ── CLI ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="팬데믹 탑승 분석")
    parser.add_argument(
        "--mode",
        choices=["strategy", "aircraft", "pattern", "all"],
        default="all",
    )
    parser.add_argument(
        "--aircraft", "-a",
        choices=list(AIRCRAFT.keys()),
        default="narrow_body",
    )
    parser.add_argument(
        "--strategies", "-s",
        nargs="+",
        default=["Random", "BySeat", "BackToFront", "BySection", "Steffen"],
    )
    parser.add_argument(
        "--rates", "-r",
        nargs="+",
        type=float,
        default=OCCUPANCY_RATES,
    )
    parser.add_argument("--trials", "-n", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed",         type=int, default=config.RANDOM_SEED)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print(f"\n{'='*60}")
    print(f"  팬데믹 탑승 분석  |  기종: {args.aircraft}")
    print(f"  탑승률: {[f'{r*100:.0f}%' for r in args.rates]}")
    print(f"  반복: {args.trials}  |  seed: {args.seed}")
    print(f"{'='*60}")

    if args.mode in ("strategy", "all"):
        print("\n▶ A. 전략 × 탑승률 비교")
        summary = run_strategy_comparison(
            args.aircraft,
            args.strategies,
            occupancy_rates=args.rates,
            n_trials=args.trials,
        )
        print_optimal_table(summary, args.aircraft)
        save_summary(summary, f"strategy_{args.aircraft}", config.RESULTS_DIR)

    if args.mode in ("aircraft", "all"):
        print("\n▶ B. 기종 × 탑승률 비교")
        aircraft_list = (
            list(AIRCRAFT.keys()) if args.aircraft == "all"
            else [args.aircraft]
        )
        # all 모드일 때는 3 기종 모두 비교
        if args.mode == "all":
            aircraft_list = list(AIRCRAFT.keys())
        ac_result = run_aircraft_comparison(
            aircraft_list,
            args.strategies,
            occupancy_rates=args.rates,
            n_trials=args.trials,
        )
        save_summary(ac_result, "aircraft", config.RESULTS_DIR)

    if args.mode in ("pattern", "all"):
        print("\n▶ C. 좌석 배치 패턴 비교")
        pat_result = run_pattern_comparison(
            args.aircraft,
            args.strategies,
            occupancy_rates=args.rates,
            n_trials=args.trials,
        )
        save_summary(pat_result, f"pattern_{args.aircraft}", config.RESULTS_DIR)


if __name__ == "__main__":
    main()