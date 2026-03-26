# analysis/sensitivity.py
"""
감도 분석 (Sensitivity Analysis) — 문항 2(b), 2(c).

[문항 2(b) 요구사항]
  두 독립 변인을 각각, 그리고 결합하여 분석:
    ① 비순응 승객 비율 ψ (GROUP_DISOBEY_PROB)
    ② 항공편당 평균 수하물 개수 E[bags]  ← 연속 스윕

[문항 2(c) 요구사항]
  "평소보다 짐이 많고 모든 짐을 선반에 넣는 상황"
    → Heavy 시나리오 + 오버헤드빈 포화도 함께 분석

[E[bags] 스윕 원리]
  수하물 개수는 {0, 1, 2}의 이산값. 평균 μ ∈ [0, 2]에서
  가장 단순한 선형 보간으로 weights를 결정:

    μ ≤ 1 : (p0, p1, p2) = (1-μ, μ, 0)
    μ > 1 : (p0, p1, p2) = (0, 2-μ, μ-1)

  이렇게 하면 μ=0 → 짐 없는 승객만, μ=1 → 1개짜리만, μ=2 → 2개짜리만
  이 되어 직관적으로 해석 가능.

  현재 기본값 BAG_PROB=[0.20, 0.70, 0.10] 의 평균:
    E[bags] = 0×0.20 + 1×0.70 + 2×0.10 = 0.90

사용 예:
    python analysis/sensitivity.py --mode psi
    python analysis/sensitivity.py --mode bags
    python analysis/sensitivity.py --mode heavy
    python analysis/sensitivity.py --mode combined   ← 2(b) 결합 히트맵
    python analysis/sensitivity.py --mode all
"""
from __future__ import annotations
from typing import Optional
import argparse
import os
import sys
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from main import run_simulation  # type: ignore[import]
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
_TRIALS    = 40
_NUM_ROWS  = 33
_DEFAULT_STRATEGIES = all_strats = list(STRATEGIES.keys())


def _mean_sec(strategy: str, n_trials: int, **kwargs) -> float:
    """n_trials 회 평균 탑승 시간(초) 반환. 실패(-1) 제외."""
    times = [
        run_simulation(strategy, num_rows=_NUM_ROWS, verbose=False, **kwargs)
        for _ in range(n_trials)
    ]
    valid = [t for t in times if t != -1]
    return float(np.mean(valid)) * config.TICK_DURATION if valid else float("nan")


# ── E[bags] ↔ BAG_PROB 변환 ──────────────────────────────────

def mean_to_bag_weights(mu: float) -> tuple[float, float, float]:
    """
    평균 수하물 개수 μ ∈ [0, 2] → BAG_PROB = (p0, p1, p2).

    선형 보간:
      μ ≤ 1 : p0=1-μ, p1=μ,   p2=0
      μ > 1 : p0=0,   p1=2-μ, p2=μ-1

    검증:
      μ=0.0 → (1.0, 0.0, 0.0)  평균=0   짐 없는 승객만
      μ=0.9 → (0.1, 0.9, 0.0)  평균≈0.9  현재 기본값과 유사
      μ=1.0 → (0.0, 1.0, 0.0)  평균=1   1개짜리만
      μ=1.5 → (0.0, 0.5, 0.5)  평균=1.5
      μ=2.0 → (0.0, 0.0, 1.0)  평균=2   2개짜리만
    """
    mu = max(0.0, min(2.0, float(mu)))
    if mu <= 1.0:
        return (1.0 - mu, mu, 0.0)
    else:
        return (0.0, 2.0 - mu, mu - 1.0)


def bag_weights_to_mean(weights: tuple) -> float:
    """BAG_PROB → E[bags]."""
    p0, p1, p2 = weights
    return p1 + 2 * p2


# ── A. 비순응(ψ) 감도 ─────────────────────────────────────────

def run_psi_sensitivity(
    strategies: list[str],
    psi_values: Optional[list[float]] = None,
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[str, list[float]]:
    """
    GROUP_DISOBEY_PROB(ψ)를 변화시키며 전략별 평균 탑승 시간 측정.
    → 문항 2(b) 첫 번째 변인.
    """
    psi_vals = psi_values or [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    results: dict[str, list[float]] = {s: [] for s in strategies}
    orig_psi = config.GROUP_DISOBEY_PROB  # type: ignore[attr-defined]

    for psi in psi_vals:
        config.GROUP_DISOBEY_PROB = psi  # type: ignore[attr-defined]
        print(f"  ψ={psi:.1f}", end="  ", flush=True)
        for strategy in strategies:
            results[strategy].append(_mean_sec(strategy, n_trials))
        print()

    config.GROUP_DISOBEY_PROB = orig_psi  # type: ignore[attr-defined]

    # ── 그래프 ──────────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    for strategy in strategies:
        ax.plot(psi_vals, results[strategy], marker="o", linewidth=2,
                color=_COLORS.get(strategy, "#333"), label=strategy)

    ax.set_title("Sensitivity Analysis: Non-compliance (ψ) vs Boarding Time\n",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Disobedience Probability ψ", fontsize=11)
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"sensitivity_psi_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  저장: {path}")
    return results


# ── B. 평균 수하물 개수 E[bags] 감도 ─────────────────────────

def run_bags_sensitivity(
    strategies: list[str],
    mu_values: Optional[list[float]] = None,
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[str, list[float]]:
    """
    평균 수하물 개수 E[bags]를 0~2 사이에서 연속 스윕.
    → 문항 2(b) 두 번째 변인.

    mean_to_bag_weights()로 (p0, p1, p2)를 자동 계산해
    run_simulation()의 bag_weights 파라미터로 전달.
    """
    # 0.0부터 2.0까지 0.2 간격 (기본 11점)
    mu_list = mu_values or [round(x * 0.2, 1) for x in range(11)]
    results: dict[str, list[float]] = {s: [] for s in strategies}

    print("\n  E[bags] 스윕 (0.0 → 2.0)")
    for mu in mu_list:
        weights = mean_to_bag_weights(mu)
        print(f"  E[bags]={mu:.1f}  weights={tuple(round(w, 2) for w in weights)}",
              end="  ", flush=True)
        for strategy in strategies:
            results[strategy].append(
                _mean_sec(strategy, n_trials, bag_weights=weights)
            )
        print()

    # ── 그래프 ──────────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    for strategy in strategies:
        ax.plot(mu_list, results[strategy], marker="o", linewidth=2,
                color=_COLORS.get(strategy, "#333"), label=strategy)

    # 현재 기본값 E[bags]=0.90 에 수직선 표시
    current_mean = bag_weights_to_mean(tuple(config.BAG_PROB))  # type: ignore[arg-type]
    ax.axvline(current_mean, color="gray", linestyle="--", linewidth=1,
               label=f"E[bags]={current_mean:.2f}")

    ax.set_title("Sensitivity Analysis: E[bags] vs Boarding Time\n",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Average Bags per Passenger  E[bags]", fontsize=11)
    ax.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=9, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"sensitivity_bags_mean_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  저장: {path}")
    return results


# ── C. 결합 히트맵 (ψ × E[bags]) ──────────────────────────────

def run_combined_sensitivity(
    strategies: list[str],
    psi_values: Optional[list[float]] = None,
    mu_values:  Optional[list[float]] = None,
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[str, np.ndarray]:
    """
    문항 2(b) — ψ 와 E[bags] 두 변인을 동시에 변화.
    전략별로 (len(psi_vals) × len(mu_vals)) 히트맵 생성.

    Returns {strategy_name: 2D ndarray of mean_sec}
    """
    psi_list = psi_values or [0.0, 0.2, 0.4, 0.6, 0.8]
    mu_list  = mu_values  or [0.0, 0.5, 1.0, 1.5, 2.0]

    # {strategy: 2D array (psi × mu)}
    results: dict[str, np.ndarray] = {
        s: np.zeros((len(psi_list), len(mu_list)))
        for s in strategies
    }

    orig_psi = config.GROUP_DISOBEY_PROB  # type: ignore[attr-defined]

    total = len(psi_list) * len(mu_list)
    done  = 0
    print(f"\n  결합 히트맵 — 총 {total}개 조합")
    for i, psi in enumerate(psi_list):
        config.GROUP_DISOBEY_PROB = psi  # type: ignore[attr-defined]
        for j, mu in enumerate(mu_list):
            weights = mean_to_bag_weights(mu)
            for strategy in strategies:
                results[strategy][i, j] = _mean_sec(
                    strategy, n_trials, bag_weights=weights
                )
            done += 1
            print(f"  [{done}/{total}] ψ={psi:.1f}  E[bags]={mu:.1f}", end="\r")

    config.GROUP_DISOBEY_PROB = orig_psi  # type: ignore[attr-defined]
    print()

    # ── 전략별 히트맵 저장 ────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    n_strats = len(strategies)
    ncols    = min(n_strats, 3)
    nrows    = (n_strats + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                              figsize=(5 * ncols, 4 * nrows),
                              squeeze=False)

    for idx, strategy in enumerate(strategies):
        ax  = axes[idx // ncols][idx % ncols]
        mat = results[strategy]
        im  = ax.imshow(mat, aspect="auto", cmap="YlOrRd",
                        vmin=mat[np.isfinite(mat)].min(),
                        vmax=mat[np.isfinite(mat)].max())
        plt.colorbar(im, ax=ax, label="s")

        ax.set_xticks(range(len(mu_list)))
        ax.set_xticklabels([f"{m:.1f}" for m in mu_list], fontsize=9)
        ax.set_yticks(range(len(psi_list)))
        ax.set_yticklabels([f"{p:.1f}" for p in psi_list], fontsize=9)
        ax.set_xlabel("E[bags]", fontsize=10)
        ax.set_ylabel("ψ", fontsize=10)
        ax.set_title(strategy, fontsize=11, fontweight="bold")

        # 수치 주석
        for i in range(len(psi_list)):
            for j in range(len(mu_list)):
                v = mat[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                            fontsize=8,
                            color="white" if v > mat.mean() else "black")

    # 빈 서브플롯 숨김
    for idx in range(len(strategies), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.suptitle("Combined Sensitivity: ψ × E[bags] → Boarding Time (s)\n",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()

    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"sensitivity_combined_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")
    return results


# ── D. 수하물 과다 (Heavy) 시나리오 — 문항 2(c) ────────────────

_HEAVY_SCENARIOS: dict[str, tuple] = {
    "Normal\n(기본)":          (0.20, 0.70, 0.10),   # E[bags]=0.90
    "Above avg\n(E=1.2)":     mean_to_bag_weights(1.2),
    "Heavy\n(E=1.5)":         mean_to_bag_weights(1.5),
    "All overhead\n(E=2.0)":  mean_to_bag_weights(2.0),
}


def run_heavy_scenario(
    strategies: list[str],
    n_trials: int = _TRIALS,
    out_dir: str  = config.RESULTS_DIR,
) -> dict[str, dict[str, float]]:
    """
    문항 2(c): "평소보다 짐이 많고 모든 짐을 선반에 넣는 상황".

    Normal → All overhead 로 점진적으로 악화시켜
    각 전략이 얼마나 민감하게 반응하는지 비교.

    결과에 포함되는 추가 정보:
      - 증가율 (%) = (Heavy - Normal) / Normal × 100
      - 가장 안정적인 전략 = 증가율이 가장 작은 전략
    """
    results: dict[str, dict[str, float]] = {s: {} for s in strategies}
    labels = list(_HEAVY_SCENARIOS.keys())

    print("\n  수하물 과다 시나리오 (문항 2c)")
    for label, weights in _HEAVY_SCENARIOS.items():
        mu = bag_weights_to_mean(weights)
        print(f"  {label.replace(chr(10), ' '):<25} E[bags]={mu:.2f}",
              end="  ", flush=True)
        for strategy in strategies:
            results[strategy][label] = _mean_sec(
                strategy, n_trials, bag_weights=weights
            )
        print()

    # ── 그래프: 막대 + 증가율 표 ─────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    x      = np.arange(len(labels))
    width  = 0.8 / len(strategies)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 9),
                                    gridspec_kw={"height_ratios": [2, 1]})

    # 막대 그래프
    for i, strategy in enumerate(strategies):
        vals   = [results[strategy][lb] for lb in labels]
        offset = (i - len(strategies) / 2 + 0.5) * width
        ax1.bar(x + offset, vals, width,
                label=strategy,
                color=_COLORS.get(strategy, "#888"),
                alpha=0.85)

    ax1.set_xticks(x)
    ax1.set_xticklabels([lb.replace("\n", " ") for lb in labels], fontsize=9)
    ax1.set_ylabel("Mean Boarding Time (s)", fontsize=11)
    ax1.set_title("Heavy Baggage Scenario",
                  fontsize=12, fontweight="bold")
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax1.legend(fontsize=9, ncol=2)
    ax1.grid(axis="y", alpha=0.3)

    # 증가율 표 (Normal 대비 %)
    normal_label = labels[0]
    rate_data = []
    for strategy in strategies:
        base = results[strategy][normal_label]
        row  = [strategy]
        for lb in labels:
            v = results[strategy][lb]
            if base > 0:
                row.append(f"{(v - base) / base * 100:+.1f}%")
            else:
                row.append("—")
        rate_data.append(row)

    ax2.axis("off")
    col_labels = ["전략"] + [lb.replace("\n", " ") for lb in labels]
    tbl = ax2.table(
        cellText=rate_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.4)
    ax2.set_title("Normal 대비 시간 증가율 (%)", fontsize=10, pad=12)

    fig.tight_layout()
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"sensitivity_heavy_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  저장: {path}")
    return results


# ── E. 복잡도 출력 ────────────────────────────────────────────

def print_complexity_table(n_passengers: int = 198) -> None:
    print(f"\n  복잡도 계수 C = ln(M) / ln(N),  N={n_passengers}")
    print(f"  {'전략':<16} {'M':>6} {'C':>8}  해석")
    print("  " + "-" * 48)
    from boarding.methods import _static_m_fallback
    strategy_list = [
        ("Random", 1),
        ("BySeat", 3),
        ("WeightedBySeat", 3),
        ("BySection", 3),
        ("BackToFront", n_passengers // 33 * 33 if n_passengers >= 33 else n_passengers),
        ("FrontToBack", n_passengers // 33 * 33 if n_passengers >= 33 else n_passengers),
        ("Steffen", n_passengers),
        ("ReversePyramid", 23),
    ]
    for name, m in strategy_list:
        m_val = m
        if m_val <= 1 or n_passengers <= 1:
            c = 0.0
        else:
            c = round(
                __import__("math").log(min(m_val, n_passengers))
                / __import__("math").log(n_passengers),
                3,
            )
        note = (
            "새치기 없음" if c == 0.0 else
            "매우 높음" if c >= 0.9 else
            "높음" if c >= 0.5 else
            "낮음"
        )
        print(f"  {name:<16} {m_val:>6} {c:>8.3f}  {note}")
    print()


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="감도 분석 (문항 2b·2c)")
    parser.add_argument(
        "--mode",
        choices=["psi", "bags", "heavy", "combined", "complexity", "all"],
        default="all",
        help="분석 항목 선택",
    )
    parser.add_argument(
        "--strategies", "-s", nargs="+",
        default=_DEFAULT_STRATEGIES,
    )
    parser.add_argument("--trials", "-n", type=int, default=_TRIALS)
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  감도 분석  |  반복: {args.trials}")
    print(f"  2(b): ψ·E[bags] 변화  |  2(c): 수하물 과다")
    print(f"{'='*60}")

    if args.mode in ("complexity", "all"):
        print("\n▶ 복잡도 테이블")
        print_complexity_table()

    if args.mode in ("psi", "all"):
        print("\n▶ [2(b)-①] 비순응률(ψ) 감도")
        run_psi_sensitivity(args.strategies, n_trials=args.trials)

    if args.mode in ("bags", "all"):
        print("\n▶ [2(b)-②] 평균 수하물 개수 E[bags] 감도")
        run_bags_sensitivity(args.strategies, n_trials=args.trials)

    if args.mode in ("combined", "all"):
        print("\n▶ [2(b)-결합] ψ × E[bags] 히트맵")
        run_combined_sensitivity(args.strategies, n_trials=args.trials)

    if args.mode in ("heavy", "all"):
        print("\n▶ [2(c)] 수하물 과다 시나리오")
        run_heavy_scenario(args.strategies, n_trials=args.trials)


if __name__ == "__main__":
    main()