# analysis/monte_carlo_deplane.py
"""
하차(Deplaning) 전용 Monte Carlo 반복 실행 + 통계 출력 + 그래프/JSON 저장.

사용 예:
    python analysis/monte_carlo_deplane.py
    python analysis/monte_carlo_deplane.py --trials 100 --strategies Random FrontToBack BackToFront AisleFirst
    python analysis/monte_carlo_deplane.py --trials 200 --plot --save
"""
from __future__ import annotations
import argparse
import os
import random
import sys
import json
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

# 프로젝트 루트 경로를 sys.path에 추가하여 다른 모듈들을 불러올 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from aircraft import get_aircraft
from main import generate_passengers
from deplaning.methods import DEPLANE_METHODS
from simulation.deplaning import run_deplaning

def run_mc_deplane(strategy_name: str, n_trials: int, aircraft_name: str) -> np.ndarray:
    """특정 하차 전략을 n_trials 만큼 반복하여 소요 시간(초) 배열을 반환합니다."""
    from typing import Callable, cast
    from main import Passenger
    deplane_method: Callable[[list[Passenger]], list[Passenger]] = cast(Callable[[list[Passenger]], list[Passenger]], DEPLANE_METHODS[strategy_name])
    results = []
    
    for _ in range(n_trials):
        airplane = get_aircraft(aircraft_name)
        airplane.reset()
        
        # 1. 승객 생성
        passengers = generate_passengers(airplane)
        
        # 2. 하차 시뮬레이션을 위해 승객들을 지정된 자리에 모두 '착석'시킴
        for p in passengers:
            p.deplane_state = "seated"
            if p.target_row in airplane.seats:
                airplane.seats[p.target_row][p.target_seat] = p
                
        # 3. 하차 시뮬레이션 실행
        ticks = run_deplaning(airplane, passengers, deplane_method)
        
        # 4. 결과 기록 (데드락 방지)
        if ticks > 0:
            results.append(ticks * config.TICK_DURATION)
        else:
            results.append(config.MAX_TICKS * config.TICK_DURATION)
            
    return np.array(results)

def summarize(name: str, arr: np.ndarray) -> dict:
    """통계 요약 딕셔너리 생성"""
    return {
        "method": name,
        "n": len(arr),
        "mean_s": float(np.mean(arr)),
        "median_s": float(np.median(arr)),
        "p5_s": float(np.percentile(arr, 5)),
        "p95_s": float(np.percentile(arr, 95)),
        "std_s": float(np.std(arr)),
        "ticks": arr.tolist()  # JSON 직렬화를 위해 list로 변환
    }

def print_table(summaries: list[dict]):
    """통계 결과 표 출력"""
    print(f"\n{'='*80}")
    print(f"{'Deplane Method':<18} | {'Mean (s)':<10} | {'Median':<10} | {'Std Dev':<10} | {'90% CI (p5~p95)':<20}")
    print(f"{'-'*80}")
    for s in summaries:
        ci = f"{s['p5_s']:.1f} ~ {s['p95_s']:.1f}"
        print(f"{s['method']:<18} | {s['mean_s']:<10.1f} | {s['median_s']:<10.1f} | {s['std_s']:<10.1f} | {ci:<20}")
    print(f"{'='*80}\n")

def plot_results(all_ticks: dict, aircraft_name: str, trials: int, timestamp: str):
    """박스플롯(Boxplot) 생성 및 저장"""
    plt.figure(figsize=(10, 6))
    
    labels = list(all_ticks.keys())
    data = [all_ticks[name] for name in labels]
    
    box = plt.boxplot(data, patch_artist=True, 
                      boxprops=dict(facecolor='lightblue', color='blue'),
                      medianprops=dict(color='red', linewidth=2))
    plt.xticks(range(1, len(labels) + 1), labels)
                      
    plt.title(f"Deplaning Time Monte Carlo Results\n({aircraft_name}, {trials} trials)", fontsize=14, fontweight='bold')
    plt.ylabel("Time (seconds)", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    os.makedirs("results", exist_ok=True)
    filepath = f"results/deplaning_mc_{aircraft_name}_{trials}trials_{timestamp}.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    print(f"📊 하차 시간 그래프가 성공적으로 저장되었습니다: {filepath}")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="하차(Deplaning) 전략 Monte Carlo 시뮬레이터")
    parser.add_argument("--aircraft", type=str, default="narrow_body", help="기종 이름 (기본: narrow_body)")
    parser.add_argument("--trials", type=int, default=200, help="반복 횟수 (기본: 200)")
    parser.add_argument("--strategies", nargs="+", default=list(DEPLANE_METHODS.keys()), 
                        help="실행할 하차 전략 리스트 (기본: 전체)")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED, help="난수 시드")
    parser.add_argument("--plot", action="store_true", help="하차 시간 그래프(Boxplot) 저장 여부")
    parser.add_argument("--save", action="store_true", help="결과 Raw Data를 JSON 형식으로 저장 여부")
    args = parser.parse_args()

    # 시드 고정
    random.seed(args.seed)
    np.random.seed(args.seed)

    # 실행 시점의 타임스탬프 생성 (예: 20260326_160430)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"  Deplaning Monte Carlo  |  기종: {args.aircraft}  |  반복: {args.trials}")
    print(f"{'='*60}")

    summaries = []
    all_ticks = {}

    for name in args.strategies:
        if name not in DEPLANE_METHODS:
            print(f"⚠️ 경고: '{name}' 은(는) 등록되지 않은 하차 전략입니다. 건너뜁니다.")
            continue
            
        print(f"▶ {name} 하차 시뮬레이션 중... ({args.trials}회)")
        arr = run_mc_deplane(name, n_trials=args.trials, aircraft_name=args.aircraft)
        summaries.append(summarize(name, arr))
        all_ticks[name] = arr

    # 통계 표 출력
    print_table(summaries)

    # 결과 폴더 생성 보장
    if args.plot or args.save:
        os.makedirs("results", exist_ok=True)

    # 그래프 저장
    if args.plot:
        plot_results(all_ticks, args.aircraft, args.trials, timestamp)

    # JSON 데이터 저장
    if args.save:
        json_data = {
            "metadata": {
                "simulation_type": "deplaning",
                "aircraft": args.aircraft,
                "trials": args.trials,
                "seed": args.seed,
                "timestamp": timestamp
            },
            "summaries": summaries
        }
        json_filepath = f"results/deplaning_mc_{args.aircraft}_{args.trials}trials_{timestamp}.json"
        
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        print(f"💾 Raw Data가 성공적으로 저장되었습니다: {json_filepath}")