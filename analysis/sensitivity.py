# analysis/sensitivity.py
"""
감도 분석 (Sensitivity Analysis) — Phase 2.

분석 항목:
  A. 비순응 계수 ψ (GROUP_DISOBEY_PROB) 변화 → 전략별 탑승 시간
  B. 수하물 개수 분포 변화 → 전략별 탑승 시간
  C. 전략별 복잡도 C 확인

사용 예:
    python analysis/sensitivity.py --mode psi
    python analysis/sensitivity.py --mode bags
    python analysis/sensitivity.py --mode all
"""
from __future__ import annotations
from typing import Optional
import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from main import run_simulation
from boarding.methods import STRATEGIES, boarding_complexity


# ── 공통 설정 ────────────────────────────────────────────────

_COLORS = {
    "Random":      "#5B9BD5",
    "BackToFront": "#ED7D31",
    "FrontToBack": "#A5A5A5",
    "BySection":   "#FFC000",
    "BySeat":      "#70AD47",
    "Steffen":     "#9B2D9B",
}
_TRIALS = 40          # 감도 분석용 반복 횟수 (속도 우선)
_NUM_ROWS = 33


def _mean_sec(strategy: str, n_trials: int, **kwargs) -> float:
    """n_trials 회 평균 탑승 시간(초) 반환."""
    times = [
        run_simulation(strategy, num_rows=_NUM_ROWS, verbose=False, **kwargs)
        for _ in range(n_trials)
    ]
    valid = [t for t in times if t != -1]
    return float(np.mean(valid)) * config.TICK_DURATION if valid else float("nan")


# ── A. 비순응(ψ) 감도 ─────────────────────────────────────────

def run_psi_sensitivity(
    strategies: list[str],
    psi_values: Optional[list[float]] = None,
    n_trials: int = _TRIALS,
    out_dir: str = config.RESULTS_DIR,
) -> dict[str, list[float]]:
    """
    GROUP_DISOBEY_PROB (ψ) 를 변화시키며 전략별 평균 탑승 시간 측정.
    Returns {strategy_name: [mean_sec, ...]} per psi value.
    """
    psi_vals = psi_values or [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    results: dict[str, list[float]] = {s: [] for s in strategies}

    orig_psi = config.GROUP_DISOBEY_PROB

    for psi in psi_vals:
        config.GROUP_DISOBEY_PROB = psi
        print(f"  ψ={psi:.1f}", end="  ", flush=True)
        for strategy in strategies:
            mean = _mean_sec(strategy, n_trials)
            results[strategy].append(mean)
        print()

    config.GROUP_DISOBEY_PROB = orig_psi  # 원복

    # ── 그래프 저장 ──────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))

    for strategy in strategies:
        ax.plot(
            psi_vals, results[strategy],
            marker="o", linewidth=2,
            color=_COLORS.get(strategy, "#333333"),
            label=strategy,
        )

    ax.set_title("Sensitivity: Non-compliance (ψ) vs Boarding Time",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Disobedience Probability ψ", fontsize=11)
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, "sensitivity_psi.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  저장: {path}")

    return results


# ── B. 수하물 감도 ────────────────────────────────────────────

_BAG_SCENARIOS: dict[str, tuple] = {
    "Light\n(60/40/0)":  (0.60, 0.40, 0.00),
    "Normal\n(20/70/10)": (0.20, 0.70, 0.10),
    "Heavy\n(0/20/80)":  (0.00, 0.20, 0.80),
}


def run_bag_sensitivity(
    strategies: list[str],
    n_trials: int = _TRIALS,
    out_dir: str = config.RESULTS_DIR,
) -> dict[str, dict[str, float]]:
    """
    수하물 분포 시나리오별 전략 비교.
    Returns {strategy: {scenario_label: mean_sec}}.
    """
    results: dict[str, dict[str, float]] = {s: {} for s in strategies}

    for label, weights in _BAG_SCENARIOS.items():
        print(f"  시나리오: {label.replace(chr(10), ' ')}", end="  ", flush=True)
        for strategy in strategies:
            mean = _mean_sec(strategy, n_trials, bag_weights=weights)
            results[strategy][label] = mean
        print()

    # ── 그래프: 그룹 막대 ────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    labels   = list(_BAG_SCENARIOS.keys())
    x        = np.arange(len(labels))
    width    = 0.8 / len(strategies)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, strategy in enumerate(strategies):
        vals = [results[strategy][lb] for lb in labels]
        offset = (i - len(strategies) / 2 + 0.5) * width
        ax.bar(
            x + offset, vals, width,
            label=strategy,
            color=_COLORS.get(strategy, "#333333"),
            alpha=0.85,
        )

    ax.set_title("Sensitivity: Baggage Distribution vs Boarding Time",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, "sensitivity_bags.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  저장: {path}")

    return results


# ── C. 복잡도 출력 ────────────────────────────────────────────

def print_complexity_table(n_passengers: int = 198) -> None:
    print(f"\n{'전략':<14} {'M':>6} {'C':>8}  {'해석'}")
    print("-" * 50)
    from boarding.methods import STRATEGY_M
    for name, m in STRATEGY_M.items():
        c  = boarding_complexity(name, n_passengers)
        mp = n_passengers if m is None else m
        note = "새치기 없음" if c == 0 else (
               "높은 복잡도" if c >= 0.8 else "중간 복잡도"
        )
        print(f"{name:<14} {mp:>6} {c:>8.3f}  {note}")
    print()


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="감도 분석")
    parser.add_argument(
        "--mode", choices=["psi", "bags", "complexity", "all"],
        default="all",
    )
    parser.add_argument(
        "--strategies", "-s", nargs="+",
        default=["Random", "BySeat", "BackToFront", "Steffen"],
    )
    parser.add_argument("--trials", "-n", type=int, default=_TRIALS)
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"  감도 분석  |  반복 횟수: {args.trials}")
    print(f"{'='*55}\n")

    if args.mode in ("complexity", "all"):
        print("▶ 복잡도 테이블")
        print_complexity_table()

    if args.mode in ("psi", "all"):
        print("▶ 비순응(ψ) 감도 분석")
        run_psi_sensitivity(args.strategies, n_trials=args.trials)

    if args.mode in ("bags", "all"):
        print("\n▶ 수하물 감도 분석")
        run_bag_sensitivity(args.strategies, n_trials=args.trials)


if __name__ == "__main__":
    main()