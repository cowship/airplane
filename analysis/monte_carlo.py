# analysis/monte_carlo.py
"""
Monte Carlo 반복 실행 + 통계 출력 + PEI 분석.

사용 예:
    python analysis/monte_carlo.py
    python analysis/monte_carlo.py --trials 500 --strategies BySeat Steffen
    python analysis/monte_carlo.py --trials 200 --plot --save --pei
"""
from __future__ import annotations
from typing import Optional
import argparse
import math
import os
import random
import sys
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from main import run_simulation  # type: ignore[import]
from boarding.methods import STRATEGIES, boarding_complexity
from visualization.results import save_all


# ── 핵심 함수 ────────────────────────────────────────────────

def run_mc(
    strategy_name: str,
    n_trials: Optional[int]              = None,
    aircraft_name: str                   = "narrow_body",
    non_compliance_rate: Optional[float] = None,
    bag_weights: Optional[tuple]         = None,
    show_progress: bool                  = True,
) -> np.ndarray:
    """
    strategy_name 전략으로 n_trials 회 시뮬레이션.

    Returns
    -------
    np.ndarray  각 시뮬레이션의 틱 수 배열 (실패값 -1 제외)
    """
    n = n_trials or config.MC_TRIALS
    results = []

    for i in range(n):
        if show_progress and (i + 1) % max(1, n // 10) == 0:
            print(f"  [{strategy_name}] {i+1}/{n} 완료...", end="\r")

        ticks = run_simulation(
            strategy_name,
            aircraft_name       = aircraft_name,
            non_compliance_rate = non_compliance_rate,
            bag_weights         = bag_weights,
            verbose             = False,
        )
        if ticks != -1:
            results.append(ticks)

    if show_progress:
        print()

    return np.array(results)


def summarize(name: str, arr: np.ndarray) -> dict[str, object]:
    """통계 요약 딕셔너리 반환."""
    secs = arr * config.TICK_DURATION
    return {
        "method":   name,
        "n":        len(arr),
        "mean_s":   float(np.mean(secs)),
        "median_s": float(np.median(secs)),
        "p5_s":     float(np.percentile(secs, 5)),
        "p95_s":    float(np.percentile(secs, 95)),
        "std_s":    float(np.std(secs)),
        "ticks":    arr.tolist(),
    }


def print_table(summaries: list[dict[str, object]]) -> None:
    """결과를 보기 좋은 표로 출력."""
    header = f"\n{'전략':<18} {'평균(s)':>8} {'중앙(s)':>8} " \
             f"{'P5(s)':>8} {'P95(s)':>8} {'표준편차':>8}"
    print(header)
    print("-" * (len(header) - 1))
    for s in summaries:
        print(
            f"{str(s['method']):<18} "
            f"{float(s['mean_s']):>8.1f} "
            f"{float(s['median_s']):>8.1f} "
            f"{float(s['p5_s']):>8.1f} "
            f"{float(s['p95_s']):>8.1f} "
            f"{float(s['std_s']):>8.1f}"
        )
    print()


def save_json(summaries: list[dict[str, object]], path: str) -> None:
    import json
    serializable = []
    for s in summaries:
        entry = {}
        for k, v in s.items():
            entry[k] = v if not hasattr(v, 'tolist') else v  # type: ignore[union-attr]
        serializable.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"JSON 저장: {path}")


# ── PEI (Practical Efficiency Index) ─────────────────────────

def compute_pei(
    summaries: list[dict[str, object]],
    n_passengers: int,
) -> list[dict[str, object]]:
    """
    PEI = T_mean × (1 + C²)

    C = ln(M) / ln(N)  (boarding_complexity)
    낮을수록 시간도 짧고 복잡도도 낮은 실용적 방법.

    Returns list of dicts with keys:
        method, T_mean, C, PEI, rank
    """
    rows = []
    for s in summaries:
        name   = str(s["method"])
        T_mean = float(s["mean_s"])  # type: ignore[arg-type]
        C      = boarding_complexity(name, n_passengers)
        PEI    = T_mean * (1 + C ** 2)
        rows.append({"method": name, "T_mean": T_mean, "C": C, "PEI": PEI})

    rows.sort(key=lambda r: r["PEI"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def print_pei_table(pei_rows: list[dict[str, object]]) -> None:
    """PEI 결과 표 출력."""
    print("\n── Practical Efficiency Index (PEI = T × (1 + C²)) ──")
    print(f"  {'순위':>4}  {'방법':<16} {'T_mean(s)':>10} {'C':>6} {'PEI':>10}  비고")
    print("  " + "-" * 58)
    min_c      = min(float(x["C"])      for x in pei_rows)
    min_t      = min(float(x["T_mean"]) for x in pei_rows)
    for r in pei_rows:
        flag = ""
        if int(r["rank"]) == 1:
            flag = "  ◀ 실용적 최적"
        elif float(r["C"]) == min_c and int(r["rank"]) != 1:
            flag = "  (최저 복잡도)"
        elif float(r["T_mean"]) == min_t and int(r["rank"]) != 1:
            flag = "  (최단 시간)"
        print(
            f"  {int(r['rank']):>4}  {str(r['method']):<16} "
            f"{float(r['T_mean']):>10.1f} {float(r['C']):>6.3f} "
            f"{float(r['PEI']):>10.1f}{flag}"
        )
    print()


def plot_pei(
    pei_rows: list[dict[str, object]],
    all_ticks: dict[str, np.ndarray],
    aircraft_name: str,
    out_dir: str = config.RESULTS_DIR,
) -> list[str]:
    """
    PEI 분석 그래프 2종 저장.

    Fig 1 — 산점도: T_mean vs C, 버블 크기 = PEI
    Fig 2 — 막대그래프: T / PEI 나란히 비교 (정규화)
    """
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    ts    = datetime.now().strftime("%H%M%S")

    names  = [r["method"]  for r in pei_rows]
    T_vals = [r["T_mean"]  for r in pei_rows]
    C_vals = [r["C"]       for r in pei_rows]
    P_vals = [r["PEI"]     for r in pei_rows]

    # ── 색상 팔레트 ─────────────────────────────────────────────
    _COLORS = {
        "Random":      "#5B9BD5",
        "BackToFront": "#ED7D31",
        "FrontToBack": "#A5A5A5",
        "BySection":   "#FFC000",
        "BySeat":      "#70AD47",
        "Steffen":     "#9B2D9B",
    }
    colors = [_COLORS.get(n, "#4472C4") for n in names]

    # ────────────────────────────────────────────────────────────
    # Fig 1: T_mean vs C 산점도 (버블 = PEI)
    # ────────────────────────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(8, 5))

    P_arr  = np.array(P_vals)
    bubble = (P_arr / P_arr.min()) ** 2 * 300   # 상대 크기

    ax1.scatter(
        C_vals, T_vals,
        s=bubble, c=colors, alpha=0.80,
        edgecolors="white", linewidths=1.2, zorder=3,
    )

    # 레이블
    for i, name in enumerate(names):
        ax1.annotate(
            name,
            (C_vals[i], T_vals[i]),
            textcoords="offset points", xytext=(8, 4),
            fontsize=8, color="#333333",
        )

    # PEI 등고선 (T = PEI / (1 + C²))
    c_line = np.linspace(0, 1.05, 300)
    for pei_level, ls in [(min(P_vals)*1.1, "--"), (np.median(P_vals), ":")]:
        t_line = pei_level / (1 + c_line ** 2)
        ax1.plot(c_line, t_line, color="#AAAAAA", lw=1, linestyle=ls,
                 label=f"PEI = {pei_level:.0f}")

    ax1.set_xlabel("Complexity  C = ln(M) / ln(N)", fontsize=11)
    ax1.set_ylabel("Mean Boarding Time  T (s)", fontsize=11)
    ax1.set_title(
        f"T vs C — Bubble size ∝ PEI²\n({aircraft_name})",
        fontsize=12, fontweight="bold",
    )
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax1.set_xlim(-0.05, 1.10)
    ax1.legend(fontsize=8, title="Iso-PEI curves")
    ax1.grid(alpha=0.3)
    fig1.tight_layout()

    path1 = os.path.join(out_dir, f"pei_scatter_{aircraft_name}_{ts}.png")
    fig1.savefig(path1, dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print(f"  저장: {path1}")
    saved.append(path1)

    # ────────────────────────────────────────────────────────────
    # Fig 2: T vs PEI 막대 비교 (PEI 순으로 정렬)
    # ────────────────────────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(9, 5))

    x      = np.arange(len(names))
    width  = 0.35
    T_norm = np.array(T_vals) / max(T_vals)
    P_norm = np.array(P_vals) / max(P_vals)

    bars_T = ax2.bar(x - width/2, T_norm, width,
                     label="Boarding Time T (normalised)",
                     color=colors, alpha=0.55, edgecolor="white")
    bars_P = ax2.bar(x + width/2, P_norm, width,
                     label="PEI (normalised)",
                     color=colors, alpha=0.90, edgecolor="white",
                     hatch="//")

    # 실제값 레이블
    for bar, T in zip(bars_T, T_vals):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.01,
                 f"{T:.0f}s", ha="center", va="bottom", fontsize=7)
    for bar, P in zip(bars_P, P_vals):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.01,
                 f"{P:.0f}", ha="center", va="bottom", fontsize=7,
                 fontweight="bold")

    ax2.set_xticks(x)
    ax2.set_xticklabels(names, rotation=10, fontsize=9)
    ax2.set_ylabel("Normalised value", fontsize=11)
    ax2.set_title(
        f"Boarding Time vs PEI Comparison\n"
        f"PEI = T × (1 + C²)   —   {aircraft_name}",
        fontsize=12, fontweight="bold",
    )
    ax2.set_ylim(0, 1.18)
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.3)

    # 최적 표시
    best_idx = int(np.argmin(P_vals))
    ax2.annotate(
        "★ Practical\n  Optimum",
        xy=(best_idx + width/2, P_norm[best_idx]),
        xytext=(best_idx + width/2 + 0.5, P_norm[best_idx] + 0.12),
        fontsize=8, color="#C00000", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#C00000", lw=1.2),
    )

    fig2.tight_layout()
    path2 = os.path.join(out_dir, f"pei_bar_{aircraft_name}_{ts}.png")
    fig2.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  저장: {path2}")
    saved.append(path2)

    return saved


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo 탑승 분석")
    parser.add_argument("--trials",     "-n", type=int,  default=config.MC_TRIALS)
    parser.add_argument("--strategies", "-s", nargs="+", default=list(STRATEGIES.keys()))
    parser.add_argument("--aircraft",   "-a", type=str,  default="narrow_body")
    parser.add_argument("--seed",             type=int,  default=config.RANDOM_SEED)
    parser.add_argument("--save",   action="store_true", help="JSON 저장")
    parser.add_argument("--plot",   action="store_true", help="탑승 시간 그래프 저장")
    parser.add_argument("--pei",    action="store_true", help="PEI 분석 + 그래프 저장")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print(f"\n{'='*60}")
    print(f"  Monte Carlo  |  기종: {args.aircraft}  |  반복: {args.trials}")
    print(f"{'='*60}")

    summaries:  list[dict[str, object]] = []
    all_ticks:  dict[str, np.ndarray]  = {}

    for name in args.strategies:
        print(f"\n▶ {name} ({args.trials}회 실행 중)")
        arr = run_mc(name, n_trials=args.trials, aircraft_name=args.aircraft)
        s   = summarize(name, arr)
        summaries.append(s)
        all_ticks[name] = arr

    print_table(summaries)

    # ── PEI 분석 ────────────────────────────────────────────────
    if args.pei:
        from aircraft import get_aircraft
        n_pax    = len(get_aircraft(args.aircraft).passenger_slots())
        pei_rows = compute_pei(summaries, n_pax)
        print_pei_table(pei_rows)
        print("📊 PEI 그래프 저장 중...")
        plot_pei(pei_rows, all_ticks, args.aircraft)

    # ── 저장 ─────────────────────────────────────────────────────
    if args.save:
        os.makedirs(config.RESULTS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        save_json(summaries, os.path.join(config.RESULTS_DIR,
                                          f"mc_results_{ts}.json"))

    if args.plot:
        print("\n📊 그래프 저장 중...")
        save_all(all_ticks, out_dir=config.RESULTS_DIR)


if __name__ == "__main__":
    main()