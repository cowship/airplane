# 비행기 탑승 시뮬레이션 — 알고리즘 요약, OUTSTANDING 논문 분석, 개선 계획

---

## 1. 현재 구현 알고리즘 요약

### 1.1 핵심 가정 (Assumptions)

| 가정 | 내용 | 비고 |
|------|------|------|
| 공간 모델 | 비행기 내부를 **격자(grid)** 로 표현. 각 셀은 하나의 좌석 또는 통로 1칸 | 1셀 = 1인 점유 가능 |
| 통로 폭 | 한 번에 1명만 통과 가능 | 실제 통로 폭 ~0.5m 기준 |
| 이동 방향 | 승객은 항상 자신의 좌석을 향해 전진. 역방향 이동 없음 | |
| 짐 적재 | 짐을 넣는 동안 통로가 완전히 차단됨 | |
| 좌석 간섭 | 창가 쪽 승객이 먼저 앉아 있으면, 통로 쪽 승객이 일어나 공간을 만들어 줌 | shuffle delay |
| 이동 속도 | 모든 승객의 통로 이동 속도는 균일하게 가정 | |
| 탑승 방법 | 탑승 방법(method)에 따라 승객 큐(queue)를 생성하고 순서대로 입장 | |
| 1틱 해석 | 현재 1틱이 실제 시간에 얼마나 대응하는지 **비현실적으로 설정되어 있음** | 개선 필요 |

### 1.2 현재 구현된 주요 규칙

**이동 규칙**
- 매 틱마다 각 승객의 상태(대기/이동/짐적재/착석완료)를 갱신
- 앞 셀이 비어 있으면 전진; 막혀 있으면 대기
- 자신의 행(row)에 도달하면 짐 적재 시퀀스 시작

**짐 적재 (Carry-on Baggage Delay)**
- 짐이 있는 승객은 일정 틱 동안 통로를 점유
- 현재는 고정 틱 수 사용 (확률 분포 미적용 가능성 있음)

**좌석 간섭 (Shuffle Delay)**
- 이미 착석한 승객이 통로 쪽을 막고 있을 때, 일어나고 다시 앉는 시간만큼 추가 지연
- 현재 단순한 고정 틱으로 처리

**탑승 방법 (Boarding Methods)**
- Random, By Section, By Seat (WMA) 등의 방식에 따라 큐 생성
- 비순응(disobedience) 처리 유무 불명확

**몬테카를로 시뮬레이션**
- 동일 조건으로 N회 반복 실행하여 평균 탑승 시간 분포를 추출
- 현재 결과가 로그(log) 형태로만 출력되어 시각화 미흡

### 1.3 현재 구현의 주요 한계

1. **틱-시간 대응 불명확**: 1틱이 실제 몇 초인지 근거 없이 설정됨
2. **비행기 구조 고정**: figure 1의 narrow-body만 지원, 다른 기종 선택 불가
3. **결과 시각화 없음**: Monte Carlo 결과가 라인바이라인 로그로만 출력
4. **확률 분포 부재**: 짐 적재 시간, 이동 속도 등이 상수로 고정
5. **하차 시뮬레이션 없음**: 탑승만 모델링, 하차 미구현
6. **그룹 승객 미지원**: 가족/단체 승객의 동시 탑승 미반영
7. **비순응 계수 미정의**: 지시를 따르지 않는 승객 비율 미처리

---

## 2. OUTSTANDING 논문 분석 (2022 IMMC)

### 2.1 2022019팀 — 핵심 기여

#### 틱-시간 대응 (실측 데이터 기반)
YouTube 영상 10개 분석(프레임 카운팅)을 통해 도출:
- **통로 1셀 이동 시간 = 1.05초**
- 이를 기준으로 모든 딜레이를 초 단위로 표현

#### 짐 적재 딜레이 — 수식 모델
```
T_bags(n_bags, n_bins, n_max):
  - n_bags = 0:  0초
  - n_bags = 1:  4 / (1 - 0.8 * n_bins/6)  초
  - n_bags = 2:  위 값 + 2.25 / (1 - (n_bins+1)/6)  초
```
핵심: **오버헤드 빈이 찰수록 적재 시간이 비선형적으로 증가**

#### 좌석 간섭(Shuffle) 딜레이 — 공식
```
T_shuffle(f, n_s) = t_up + t_s * (f + 1 + n_s)
  - t_up: 일어서는 데 걸리는 시간
  - t_s: 좌석 1칸 횡이동 시간
  - f: 가장 멀리 앉은 차단 승객 인덱스
  - n_s: 차단하는 착석 승객 수
```

#### 비순응 계수 (Disobedience Coefficient, ψ)
- ψ = 0.3 (논문 기준, 30% 승객이 지시 미준수)
- 그룹의 비순응: 그룹 전체를 하나의 단위로 취급 (ψ, not 1-(1-ψ)^n)

#### 그룹 승객
- 그룹 크기 1, 2, 3 — 가중 확률 (70, 20, 10) 할당
- 그룹은 창-중간-통로 순으로 큐에 정렬 (자체 최적화)
- 짐 가방 수: 0, 1, 2개 — 가중 확률 (20, 70, 10) 할당

#### 시뮬레이션 결과 (narrow-body, 10,000회 반복)
| 탑승 방법 | 평균 시간 | 5th~95th 퍼센타일 |
|-----------|-----------|------------------|
| Random | 689초 | 627 ~ 756초 |
| By Section (AMF) | 769초 | 697 ~ 846초 |
| By Seat (WMA) | 519초 | 479 ~ 564초 |
| Modified Steffen | 647초 | 595 ~ 697초 |
| **Modified WMA (그룹 허용)** | **651초** | **598 ~ 711초** |

---

### 2.2 2022031팀 — 핵심 기여

#### 틱-시간 대응 (연구문헌 기반)
- 좌석 피치: 74cm (29인치) → 평균 통로 속도 0.52 m/s
- **1 t.u.(time unit) = 1.42초** (= 0.74m / 0.52m/s)
- 좌석 횡이동 속도: 0.4 m/s → 1 t.u. = 1.1초 → 단순화하여 아이슬 속도와 동일 처리

#### 짐 적재 시간 — Weibull 분포 적용
- 실측값: 최소 1.9초, 최대 10.7초, **평균 7.0초, 표준편차 1.7초**
- Weibull 분포 파라미터: k = 5.153, λ = 7.774
- 시뮬레이션 시 각 승객마다 랜덤 샘플링 → 정수로 반올림

#### 탑승 방법 복잡도 (Complexity Factor)
```
C = ln(M) / ln(N)
  - M: 우선순위 그룹 수
  - N: 전체 승객 수
```
- 무작위 탑승: C = 0 (규칙 없음 → 새치기도 없음)
- Steffen 방식: C = 1 (모든 승객이 개별 그룹)
- 새치기 비율: R_J = R_J_max × C

#### 큐 새치기 — 이항분포 모델
```
QJ(i, j) = C(r, r/2 + i - j) / 2^r
  r = 12 (앞뒤 최대 6칸 이동)
```
복잡한 탑승 방식일수록 새치기 가능성 증가 → 단순 방식이 현실에서 더 강건

#### 민감도 분석 결과
- 짐 적재 시간 변화 → **탑승 시간에 큰 영향 없음**
- 새치기 비율 증가 → 복잡한 방식은 급격히 성능 저하, 단순 방식은 영향 없음

---

## 3. 우리 프로젝트에 적용 가능한 개선 아이디어

### 3.1 즉시 적용 (Phase 1 — 최우선)

#### [A] 1틱 = 0.5초 기준으로 모든 시간 파라미터 재보정

논문 데이터를 0.5초 기준 틱 수로 변환:

| 항목 | 실제 시간 | 0.5초 기준 틱 수 |
|------|-----------|-----------------|
| 통로 1셀 이동 | 1.05초 (2022019) / 1.42초 (2022031) | **2~3틱** |
| 좌석 1칸 횡이동 | 1.1초 | **2틱** |
| 짐 없음 | 0초 | **0틱** |
| 짐 1개 적재 (빈 칸) | 4.0초 | **8틱** |
| 짐 2개 적재 (빈 칸) | 6.25초 | **13틱** |
| 짐 1개 (꽉 찬 칸) | 12.0초 | **24틱** |
| 일어서기 (t_up) | ~2.0초 | **4틱** |
| 앉기 (t_down) | ~1.5초 | **3틱** |
| 짐 수거 (하차) | 평균 7.0초 (Weibull) | **14틱 평균** |

**짐 적재 시간은 Weibull 분포로 샘플링** (k=5.153, λ=7.774초):
```python
import numpy as np
def sample_bag_time_ticks(tick_duration=0.5):
    seconds = np.random.weibull(5.153) * 7.774
    seconds = max(1.9, min(10.7, seconds))  # 실측 범위 클리핑
    return round(seconds / tick_duration)
```

#### [B] 오버헤드 빈 포화도 반영 짐 적재 시간

```python
def bag_stow_ticks(n_bags, n_bins_used, n_max=6, tick_duration=0.5):
    C0, C1, C2 = 4.0, 0.8, 2.25
    if n_bags == 0:
        return 0
    fill_ratio = n_bins_used / n_max
    t = C0 / (1 - C1 * fill_ratio)
    if n_bags == 2:
        t += C2 / (1 - (n_bins_used + 1) / n_max)
    return round(t / tick_duration)
```

#### [C] 좌석 간섭(Shuffle) 수식 적용

```python
def shuffle_ticks(f, n_s, t_up=4, t_s=2):
    # f: 가장 먼 차단 승객의 좌석 인덱스 (1=aisle, 3=window)
    # n_s: 일어나야 하는 착석 승객 수
    return t_up + t_s * (f + 1 + n_s)
```

---

### 3.2 단기 개선 (Phase 2)

#### [D] 비순응 계수 (Disobedience Coefficient)

```python
PSI = 0.3  # 기본값: 30% 승객이 지시 불이행
# 그룹은 그룹 단위로 하나의 PSI 적용
def is_disobedient(psi=PSI):
    return random.random() < psi
```

#### [E] 탑승 방법 복잡도 → 큐 새치기 모델

```python
import math
def complexity(M, N):
    if M <= 1: return 0.0
    return math.log(M) / math.log(N)

def queue_jump(sequence, R_J_max=0.3, r=12):
    N = len(sequence)
    C = complexity(len(set(p.priority for p in sequence)), N)
    R_J = R_J_max * C
    # R_J 비율의 승객을 이항분포 기반으로 최대 r/2칸 이동
    ...
```

#### [F] 그룹 승객 모델

- 그룹 크기: 1 (70%), 2 (20%), 3 (10%)
- 그룹 내 탑승 순서: 창가→중간→통로 (자기 최적화)
- 그룹 전체가 인접 행에 배치

#### [G] Monte Carlo 결과 시각화 + 파일 저장

```python
import matplotlib.pyplot as plt
import json

def save_results(results: dict, prefix="mc_result"):
    # JSON 저장
    with open(f"{prefix}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # 히스토그램 저장
    for method, times in results.items():
        plt.figure(figsize=(8,5))
        plt.hist(times, bins=50, density=True, alpha=0.7)
        plt.axvline(np.mean(times), color='r', linestyle='--', label=f'Mean: {np.mean(times):.1f}s')
        plt.title(f"{method} — Boarding Time Distribution")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Density")
        plt.legend()
        plt.savefig(f"{prefix}_{method}.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    # 비교 박스플롯
    plt.figure(figsize=(12,6))
    plt.boxplot(results.values(), labels=results.keys())
    plt.title("Boarding Methods Comparison")
    plt.ylabel("Boarding Time (seconds)")
    plt.xticks(rotation=20)
    plt.savefig(f"{prefix}_comparison.png", dpi=150, bbox_inches='tight')
    plt.close()
```

---

### 3.3 중기 개선 (Phase 3)

#### [H] 다중 비행기 구조 지원

세 가지 IMMC 기준 항공기를 격자로 모델링:

```python
AIRCRAFT_CONFIGS = {
    "narrow_body": {
        "rows": 33, "seats_per_row": 6,           # 3+3 배치
        "aisle_cols": [3],                          # 중앙 1통로
        "entrances": [(0, 3)],                      # 앞쪽 1개 입구
        "capacity": 198
    },
    "flying_wing": {
        "rows": 20, "seats_per_row": 16,            # 4+4+4+4 배치
        "aisle_cols": [4, 8, 12],                    # 3개 통로
        "entrances": [(0, 4), (0, 8), (0, 12)],     # 여러 입구
        "capacity": 320
    },
    "twin_aisle": {
        "rows": 30, "seats_per_row": 9,             # 3+3+3 배치
        "aisle_cols": [3, 6],                        # 2개 통로
        "entrances": [(0, 3), (0, 6), (15, 3)],     # 앞+중간 입구
        "capacity": 270
    }
}
```

실행 시 선택:
```python
python simulate.py --aircraft narrow_body --method wma --trials 1000
```

#### [I] 하차(Disembarking) 시뮬레이션

**하차 모델 (2022019 기반)**
- 각 승객에게 우선순위(priority) 값 부여
- 하차 방법별 우선순위 설정:
  - **Random**: 랜덤 우선순위
  - **Back-to-Front**: 뒷좌석 낮은 숫자 (먼저 이동)
  - **Front-to-Back**: 앞좌석 낮은 숫자
- 짐 수거 시간: Weibull 분포 (탑승 짐 적재와 동일)

**늦게 일어나는 승객 (Late-Disembarking, 2022031)**
- R_L 비율의 승객은 모든 다른 승객이 열을 벗어날 때까지 착석 유지

#### [J] 승객 수 변화 시나리오

- 만석(full), 부분(partial: 50%, 75%), 소셜 디스턴싱 패턴
- 탑승률 파라미터 `--occupancy 0.85` 처럼 CLI로 지정

---

### 3.4 장기 개선 (Phase 4)

#### [K] 승객 이질성 (Heterogeneous Passengers)

각 승객이 고유 속성 갖도록:
```python
@dataclass
class Passenger:
    id: int
    seat: tuple
    group_id: int
    n_bags: int                     # 0, 1, 2 (가중 확률)
    speed_factor: float             # 평균 1.0, std 0.15 (노약자: 0.6)
    is_elderly_or_mobility: bool
    bag_stow_time: int              # Weibull 샘플링
    priority: int                   # 탑승 우선순위
    disobedient: bool               # PSI 기반
```

#### [L] 감도 분석(Sensitivity Analysis) 자동화

각 파라미터를 독립적으로 변화시키면서 탑승 시간 영향 측정:
```
- ψ (비순응): 0.0 → 1.0 (간격 0.1)
- 짐 평균 개수: 0.5 → 1.5
- 그룹 비율: 0% → 50%
- 승객 이동 속도: ±30%
```

#### [M] 실제 시간 검증 (Validation)

- IMMC 2022019 결과와 우리 시뮬레이션 비교
- Random: 689초, WMA: 519초 → 우리 모델의 오차 10% 이내 목표

---

## 4. 프로젝트 개발 계획

### 4.1 마일스톤 개요

```
Phase 0 — 코드베이스 정리 (1~2일)
Phase 1 — 시간 파라미터 현실화 + 결과 시각화 (3~5일)  ← 최우선
Phase 2 — 행동 모델 강화 (5~7일)
Phase 3 — 다중 기종 + 하차 시뮬레이션 (7~10일)
Phase 4 — 분석 자동화 + 논문 수준 완성도 (10~14일)
```

---

### Phase 0: 코드 정리 및 구조화

**목표**: 향후 확장이 용이하도록 모듈 분리

```
airplane_sim/
├── main.py                 # CLI 진입점
├── config.py               # 파라미터 중앙 관리
├── aircraft/
│   ├── base.py             # Aircraft 추상 클래스
│   ├── narrow_body.py
│   ├── flying_wing.py
│   └── twin_aisle.py
├── passenger.py            # Passenger 데이터클래스
├── boarding/
│   ├── methods.py          # 탑승 방법별 큐 생성
│   └── queue_model.py      # 비순응/새치기 모델
├── simulation/
│   ├── engine.py           # 코어 시뮬레이션 루프
│   ├── boarding_sim.py
│   └── deplaning_sim.py    # 하차 (Phase 3)
├── analysis/
│   ├── monte_carlo.py      # MC 반복 + 통계
│   └── sensitivity.py      # 민감도 분석
└── visualization/
    ├── results.py           # 히스토그램/박스플롯
    └── realtime.py          # 실시간 격자 시각화
```

**작업 목록**
- [ ] 기존 코드를 위 구조로 리팩터링
- [ ] `config.py`에 모든 상수 이전 (하드코딩 제거)
- [ ] `Passenger` 데이터클래스 도입

---

### Phase 1: 시간 파라미터 현실화 + 결과 시각화 ⭐ 최우선

**목표**: 1틱 = 0.5초 기준으로 전 파라미터 재보정 + MC 결과를 그래프/파일로 저장

**작업 목록**
- [ ] `config.py`에 `TICK_DURATION = 0.5` 정의
- [ ] 통로 이동: `AISLE_MOVE_TICKS = 2` (=1.05초 ≈ 2×0.5초) 또는 `3` (=1.42초)
- [ ] 좌석 횡이동: `ROW_MOVE_TICKS = 2`
- [ ] 짐 적재: `bag_stow_ticks()` 함수 — 2022019 수식 적용 (빈 포화도 반영)
- [ ] 짐 적재: Weibull 샘플링 버전도 구현 (`USE_WEIBULL = True/False` 설정)
- [ ] Shuffle: `shuffle_ticks(f, n_s)` 공식 적용
- [ ] Monte Carlo 결과 → `results/` 폴더에 PNG + JSON 자동 저장
- [ ] Summary 표 출력: 방법별 평균/중앙값/5th-95th percentile
- [ ] 로그 출력 → 진행바(`tqdm`) 로 교체

**검증 기준**
- Random 탑승 평균 ≈ 680~720초 (2022019 결과: 689초)
- WMA 탑승 평균 ≈ 500~540초 (2022019 결과: 519초)

---

### Phase 2: 행동 모델 강화

**목표**: 그룹 승객, 비순응, 새치기, 짐 이질성 반영

**작업 목록**
- [ ] `Passenger` 클래스에 `group_id`, `n_bags`, `disobedient` 속성 추가
- [ ] 그룹 생성 로직: 크기 1/2/3, 가중 확률 70/20/10
- [ ] 그룹 내 탑승 순서: 창가→중간→통로 자동 정렬
- [ ] 비순응 계수 ψ = 0.3 기본값으로 적용 (설정 가능)
- [ ] 탑승 방법 복잡도 C = ln(M)/ln(N) 계산 함수
- [ ] 큐 새치기: 이항분포 기반, r=12 범위 내
- [ ] 늦게 도착 승객: 큐 끝으로 강제 이동
- [ ] 민감도 분석: ψ를 0→1 사이에서 변화시키며 탑승 시간 플롯

---

### Phase 3: 다중 기종 + 하차 시뮬레이션

**목표**: 3가지 항공기 구조 선택 + 하차 시뮬레이션 구현

**작업 목록 — 다중 기종**
- [ ] `Aircraft` 추상 클래스 정의 (격자 생성, 통로 위치, 입구 위치)
- [ ] `NarrowBody`, `FlyingWing`, `TwinAisle` 구현
- [ ] CLI: `--aircraft narrow_body|flying_wing|twin_aisle`
- [ ] 기종별 오버헤드 빈 용량 설정

**작업 목록 — 하차**
- [ ] `deplaning_sim.py` 구현
  - 우선순위 맵 생성 (탑승 방법별 다름)
  - 짐 수거 시간: Weibull 분포
  - 늦게 일어나는 승객 R_L 비율 반영
- [ ] 하차 방법: Random, Back-to-Front, Front-to-Back, Row-by-Row
- [ ] 최적 하차 방법 분석 (Back-to-Front 예상)

---

### Phase 4: 분석 완성도 + 논문 수준

**목표**: 결과의 수학적 신뢰도 확보, IMMC 논문 수준의 분석

**작업 목록**
- [ ] 탑승 + 하차 종합 시간(Total Turnaround Contribution) 계산
- [ ] 승객 수 변화 시나리오: 50%, 75%, 100% 탑승률
- [ ] 소셜 디스턴싱 시나리오 (격행 착석 패턴)
- [ ] 모든 분석 결과를 PDF 리포트로 자동 생성
- [ ] 실측값과 비교하여 모델 검증(Validation) 섹션 작성
- [ ] README.md 업데이트: 설치, 실행, 파라미터 설명

---

## 5. 즉시 실행할 수 있는 핵심 코드 스니펫

### 5.1 config.py 뼈대

```python
# config.py

# 시간 기반
TICK_DURATION = 0.5          # 1틱 = 0.5초
AISLE_MOVE_TICKS = 2         # 통로 1칸 이동 (= 1.0초)
ROW_MOVE_TICKS = 2           # 좌석 횡이동 1칸 (= 1.0초)
STAND_UP_TICKS = 4           # 일어서는 시간 (= 2.0초)
SIT_DOWN_TICKS = 3           # 앉는 시간 (= 1.5초)

# 짐 모델
USE_WEIBULL = True           # True: Weibull 샘플링, False: 수식 모델
WEIBULL_MEAN_SEC = 7.0
WEIBULL_STD_SEC = 1.7
BAG_PROB = [0.20, 0.70, 0.10]  # 0개, 1개, 2개 짐

# 승객 행동
PSI = 0.3                    # 비순응 계수
R_L = 0.05                   # 늦게 도착 비율
R_J_MAX = 0.3                # 최대 새치기 비율
QUEUE_JUMP_RANGE = 12        # 새치기 이항분포 범위

# 그룹
GROUP_PROB = [0.70, 0.20, 0.10]  # 크기 1, 2, 3

# 몬테카를로
MC_TRIALS = 1000
RANDOM_SEED = 42

# 출력
RESULTS_DIR = "results/"
SAVE_PLOTS = True
SAVE_JSON = True
```

### 5.2 Monte Carlo 결과 저장 + 시각화

```python
# analysis/monte_carlo.py
import numpy as np
import matplotlib.pyplot as plt
import json
import os
from tqdm import tqdm
from config import RESULTS_DIR

def run_monte_carlo(sim_func, method_name, n_trials=1000, **kwargs):
    times = []
    for _ in tqdm(range(n_trials), desc=f"MC [{method_name}]"):
        t = sim_func(method=method_name, **kwargs)
        times.append(t)
    return np.array(times)

def save_and_plot_results(all_results: dict, filename_prefix="mc"):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # 요약 출력
    print(f"\n{'Method':<20} {'Mean':>8} {'Median':>8} {'5th':>8} {'95th':>8} {'Std':>8}")
    print("-" * 60)
    for method, times in all_results.items():
        mean = np.mean(times)
        med = np.median(times)
        p5 = np.percentile(times, 5)
        p95 = np.percentile(times, 95)
        std = np.std(times)
        print(f"{method:<20} {mean:>8.1f} {med:>8.1f} {p5:>8.1f} {p95:>8.1f} {std:>8.1f}")
    
    # JSON 저장
    json_data = {k: v.tolist() for k, v in all_results.items()}
    with open(f"{RESULTS_DIR}{filename_prefix}_data.json", "w") as f:
        json.dump(json_data, f)
    
    # 비교 박스플롯
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.boxplot(all_results.values(), labels=all_results.keys(), showfliers=False)
    ax.set_ylabel("Boarding Time (seconds)")
    ax.set_title("Boarding Methods Comparison")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}{filename_prefix}_boxplot.png", dpi=150)
    plt.close()
    
    # 개별 히스토그램
    for method, times in all_results.items():
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(times, bins=40, density=True, alpha=0.7, color='steelblue')
        ax.axvline(np.mean(times), color='r', linestyle='--',
                   label=f'Mean: {np.mean(times):.0f}s')
        ax.axvline(np.percentile(times, 5), color='orange', linestyle=':',
                   label=f'5th: {np.percentile(times, 5):.0f}s')
        ax.axvline(np.percentile(times, 95), color='orange', linestyle=':',
                   label=f'95th: {np.percentile(times, 95):.0f}s')
        ax.set_xlabel("Boarding Time (seconds)")
        ax.set_ylabel("Density")
        ax.set_title(f"{method} — Distribution ({len(times)} trials)")
        ax.legend()
        plt.tight_layout()
        plt.savefig(f"{RESULTS_DIR}{filename_prefix}_{method}.png", dpi=150)
        plt.close()
    
    print(f"\n결과 저장 완료: {RESULTS_DIR}")
```

---

## 6. 참고 문헌 및 수치 근거 요약

| 항목 | 값 | 출처 |
|------|----|------|
| 통로 1셀 이동 시간 | 1.05초 | 2022019팀, YouTube 영상 10개 분석 |
| 통로 이동 속도 | 0.52 m/s | Qiang & Jia (2016) |
| 좌석 피치 | 74 cm (29 in) | 이코노미 클래스 평균 |
| 짐 적재 평균/표준편차 | 7.0초 / 1.7초 | Qiang & Jia (2016) |
| 짐 적재 분포 | Weibull (k=5.153, λ=7.774) | 2022031팀 |
| 비순응 승객 비율 | 30% | 온라인 항공사 데이터 |
| 짐 보유 비율 | 0개 20%, 1개 70%, 2개 10% | 2022019팀 추정 |
| 그룹 비율 | 크기1: 70%, 크기2: 20%, 크기3: 10% | 2022019팀 추정 |
| Steffen 방식 | 이론적 최적이나 실용성 낮음 | Steffen (2008) |

---

*문서 작성일: 2026-03-21*
*참고 논문: IMMC 2022 OUTSTANDING — Team 2022019, 2022031*
