# monte_carlo.py
import numpy as np
from main import run_simulation  # run_simulation이 ticks를 반환하도록 유지

def run_monte_carlo(strategy_name, n_runs=200, non_compliance_rate=0.1, bag_weights=(0.2, 0.6, 0.2)):
    """
    n_runs번 시뮬레이션 실행 → 분포 통계 반환
    bag_weights: [0개, 1개, 2개] 비율 (sensitivity analysis용)
    """
    results = []
    for _ in range(n_runs):
        ticks = run_simulation(
            strategy_name,
            non_compliance_rate=non_compliance_rate,
            bag_weights=bag_weights
        )
        results.append(ticks)
    
    arr = np.array(results)
    return {
        'mean':   arr.mean(),
        'p5':     np.percentile(arr, 5),   # 실질적 최솟값
        'p95':    np.percentile(arr, 95),  # 실질적 최댓값
        'std':    arr.std(),
        'all':    arr
    }

def sensitivity_analysis():
    strategies = ["Random", "BackToFront", "BySeat", "BySection_Aft", "Steffen"]
    
    # 1. 비준수율 민감도 (0% ~ 50%)
    compliance_rates = [0.0, 0.1, 0.2, 0.3, 0.5]
    print("=== 비준수율 민감도 분석 ===")
    for strategy in strategies:
        print(f"\n[{strategy}]")
        for rate in compliance_rates:
            stats = run_monte_carlo(strategy, n_runs=100,
                                    non_compliance_rate=rate)
            print(f"  비준수율 {rate*100:.0f}%: "
                  f"평균={stats['mean']/10:.1f}s, "
                  f"P5={stats['p5']/10:.1f}s, "
                  f"P95={stats['p95']/10:.1f}s")
    
    # 2. 수하물 개수 민감도
    bag_scenarios = {
        "normal":  (0.2, 0.6, 0.2),   # 정상 상황
        "heavy":   (0.0, 0.2, 0.8),   # PDF 2c: 짐 많은 상황
        "light":   (0.6, 0.4, 0.0),   # 짐 적은 상황
    }
    print("\n=== 수하물 민감도 분석 ===")
    for strategy in strategies:
        print(f"\n[{strategy}]")
        for scenario, weights in bag_scenarios.items():
            stats = run_monte_carlo(strategy, n_runs=100,
                                    bag_weights=weights)
            print(f"  {scenario}: 평균={stats['mean']/10:.1f}s, "
                  f"P5={stats['p5']/10:.1f}s, "
                  f"P95={stats['p95']/10:.1f}s")

if __name__ == "__main__":
    # 기본 비교표 (논문 Table 용)
    print("=== 전략별 Monte Carlo 결과 (n=200) ===")
    for strategy in ["Random", "BackToFront", "BySeat", "BySection_Aft", "Steffen"]:
        stats = run_monte_carlo(strategy, n_runs=200)
        print(f"{strategy:20s} | 평균: {stats['mean']/10:6.1f}s | "
              f"P5: {stats['p5']/10:6.1f}s | P95: {stats['p95']/10:6.1f}s")
    
    sensitivity_analysis()