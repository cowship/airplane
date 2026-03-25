# analysis/monte_carlo.py
"""
Monte Carlo 반복 실행 + 통계 출력.

사용 예:
    python analysis/monte_carlo.py
    python analysis/monte_carlo.py --trials 500 --strategies BySeat Steffen
"""
from __future__ import annotations
from typing import Optional
import argparse
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from main import run_simulation  # type: ignore[import]
from boarding.methods import STRATEGIES
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
    np.ndarray  각 시뮬레이션의 틱 수 배열 (실패값 -1 제외).
                모든 시도가 실패하면 빈 배열(np.array([])) 반환.
    """
    n = n_trials or config.MC_TRIALS
    results = []
    n_failed = 0

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
        else:
            n_failed += 1

    if show_progress:
        print()  # 줄바꿈
        if n_failed > 0:
            pct = n_failed / n * 100
            print(f"  [{strategy_name}] ⚠️  {n_failed}/{n} ({pct:.1f}%) 시뮬레이션 실패 (데드락/타임아웃)")
        if not results:
            print(f"  [{strategy_name}] ❌ 유효한 결과 없음 — MAX_TICKS({config.MAX_TICKS}) 증가를 고려하세요.")

    return np.array(results, dtype=float)


def summarize(name: str, arr: np.ndarray) -> dict[str, object]:
    """
    통계 요약 딕셔너리 반환.
    arr 이 빈 배열이면 nan 값으로 채운 딕셔너리를 반환하고 경고를 포함한다.
    """
    if len(arr) == 0:
        return {
            "method":   name,
            "n":        0,
            "mean_s":   float("nan"),
            "median_s": float("nan"),
            "p5_s":     float("nan"),
            "p95_s":    float("nan"),
            "std_s":    float("nan"),
            "ticks":    [],
            "warning":  "모든 시뮬레이션이 데드락/타임아웃으로 실패했습니다.",
        }

    secs = arr * config.TICK_DURATION
    return {
        "method":   name,
        "n":        int(len(arr)),
        "mean_s":   float(np.mean(secs)),
        "median_s": float(np.median(secs)),
        "p5_s":     float(np.percentile(secs, 5)),
        "p95_s":    float(np.percentile(secs, 95)),
        "std_s":    float(np.std(secs)),
        "ticks":    arr.tolist(),
    }


def print_table(summaries: list[dict[str, object]]) -> None:
    """결과를 보기 좋은 표로 출력. nan 값도 안전하게 처리."""
    header = (
        f"\n{'전략':<18} {'n':>6} {'평균(s)':>8} {'중앙(s)':>8} "
        f"{'P5(s)':>8} {'P95(s)':>8} {'표준편차':>8}"
    )
    print(header)
    print("-" * len(header))

    for s in summaries:
        n_val   = s.get("n", 0)
        mean_s  = s.get("mean_s")
        warning = s.get("warning", "")

        if n_val == 0 or (isinstance(mean_s, float) and np.isnan(mean_s)):
            print(f"{s['method']:<18} {'0':>6}  ⚠️  {warning}")
        else:
            print(
                f"{s['method']:<18} {n_val:>6} "
                f"{s['mean_s']:>8.1f} "
                f"{s['median_s']:>8.1f} "
                f"{s['p5_s']:>8.1f} "
                f"{s['p95_s']:>8.1f} "
                f"{s['std_s']:>8.1f}"
            )
    print()


def save_json(summaries: list[dict[str, object]], path: str) -> None:
    import json
    # ticks 리스트 제외하고 저장 (용량 절약)
    slim = [{k: v for k, v in s.items() if k != "ticks"} for s in summaries]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    print(f"JSON 저장: {path}")


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo 탑승 분석")
    parser.add_argument("--trials",    "-n", type=int,   default=config.MC_TRIALS)
    parser.add_argument("--strategies","-s", nargs="+",  default=list(STRATEGIES.keys()))
    parser.add_argument("--aircraft",  "-a", type=str,   default="narrow_body")
    parser.add_argument("--seed",            type=int,   default=config.RANDOM_SEED)
    parser.add_argument("--save",            action="store_true", help="JSON 저장")
    parser.add_argument("--plot",            action="store_true", help="그래프 PNG 저장")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print(f"\n{'='*60}")
    print(f"  Monte Carlo  |  기종: {args.aircraft}  |  반복: {args.trials}")
    print(f"{'='*60}")

    summaries: list[dict[str, object]]      = []
    all_ticks: dict[str, np.ndarray]        = {}
    valid_ticks: dict[str, np.ndarray]      = {}   # plot용 (비어있지 않은 것만)

    for name in args.strategies:
        print(f"\n▶ {name} ({args.trials}회 실행 중)")
        arr = run_mc(name, n_trials=args.trials, aircraft_name=args.aircraft)
        s   = summarize(name, arr)
        summaries.append(s)
        all_ticks[name] = arr
        if len(arr) > 0:
            valid_ticks[name] = arr

    print_table(summaries)

    if args.save:
        os.makedirs(config.RESULTS_DIR, exist_ok=True)
        save_json(summaries, os.path.join(config.RESULTS_DIR, "mc_results.json"))

    if args.plot:
        if not valid_ticks:
            print("\n⚠️  유효한 결과가 없어 그래프를 생성할 수 없습니다.")
        else:
            print("\n📊 그래프 저장 중...")
            save_all(valid_ticks, out_dir=config.RESULTS_DIR)
            skipped = set(all_ticks) - set(valid_ticks)
            if skipped:
                print(f"  ⚠️  그래프 생략된 전략 (결과 없음): {', '.join(skipped)}")


if __name__ == "__main__":
    main()