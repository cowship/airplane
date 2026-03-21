# ✈️ Airplane Boarding Simulation

IMMC 2022 문제 기반 항공기 탑승/하차 시뮬레이션 프레임워크.  
확률적 셀룰러 오토마타 모델로 다양한 탑승 전략을 비교 분석한다.

---

## 📁 프로젝트 구조

```
airplane_sim/
├── config.py                  # 모든 파라미터 중앙 관리
├── passenger.py               # Passenger 상태 머신
├── main.py                    # CLI 진입점
│
├── aircraft/                  # 항공기 기종
│   ├── base.py                # AircraftBase 추상 클래스
│   ├── narrow_body.py         # NarrowBody  (198석, 통로 1개)
│   ├── twin_aisle.py          # TwinAisle   (242석, 통로 2개, 입구 2개)
│   └── flying_wing.py         # FlyingWing  (318석, 통로 4개, 비직사각형)
│
├── boarding/                  # 탑승 모델
│   ├── methods.py             # 6가지 탑승 전략
│   ├── queue_model.py         # 복잡도 기반 새치기 + 지각 처리
│   └── group_model.py         # 그룹 승객 배정
│
├── deplaning/
│   └── methods.py             # 4가지 하차 방법
│
├── simulation/
│   ├── engine.py              # 다중 채널 탑승 시뮬레이션 루프
│   └── deplaning.py           # 하차 시뮬레이션 루프
│
├── analysis/
│   ├── monte_carlo.py         # Monte Carlo 반복 실행 + 통계
│   ├── sensitivity.py         # 감도 분석 (ψ, 수하물)
│   └── turnaround.py          # Phase 4: 종합 시간, 탑승률, 소셜 디스턴싱
│
└── visualization/
    ├── results.py             # 히스토그램 + 박스플롯
    └── realtime.py            # 탑승 과정 격자 시각화 (PNG / GIF)
```

---

## ⚙️ 설치

### 요구 사항
- Python 3.10 이상
- 의존 패키지:

```bash
pip install numpy matplotlib pillow
```

---

## 🚀 실행 방법

### 1. 단일 시뮬레이션

```bash
# 기본 (NarrowBody, 전략 6종 비교)
python main.py

# 기종 지정
python main.py --aircraft twin_aisle
python main.py --aircraft flying_wing

# 탑승 + 하차 동시
python main.py --mode both --aircraft narrow_body

# 특정 전략만
python main.py --strategy BySeat --aircraft narrow_body

# 탑승률 지정 + 특정 하차 방법
python main.py --mode both --strategy BySeat --deplane BackToFront
```

| `--aircraft` | 선택지 | 기본값 |
|---|---|---|
| 기종 | `narrow_body` / `twin_aisle` / `flying_wing` | `narrow_body` |

| `--mode` | 선택지 | 기본값 |
|---|---|---|
| 모드 | `boarding` / `deplaning` / `both` | `boarding` |

| `--strategy` | 선택지 | 기본값 |
|---|---|---|
| 탑승 전략 | `Random` `BackToFront` `FrontToBack` `BySection` `BySeat` `Steffen` `all` | `all` |

| `--deplane` | 선택지 | 기본값 |
|---|---|---|
| 하차 방법 | `Random` `FrontToBack` `BackToFront` `RowByRow` `all` | `all` |

---

### 2. Monte Carlo 분석

```bash
# 기본 (200회, 전략 6종, narrow_body)
python analysis/monte_carlo.py

# 옵션
python analysis/monte_carlo.py \
  --aircraft twin_aisle \
  --strategies Random BySeat Steffen \
  --trials 500 \
  --plot \    # PNG 저장
  --save      # JSON 저장
```

---

### 3. 감도 분석

```bash
# 비순응(ψ) 감도
python analysis/sensitivity.py --mode psi

# 수하물 감도
python analysis/sensitivity.py --mode bags

# 복잡도 테이블 출력
python analysis/sensitivity.py --mode complexity

# 전체
python analysis/sensitivity.py --mode all --trials 40
```

---

### 4. Phase 4 — 종합 분석

```bash
# 탑승 + 하차 종합 시간 비교 (Turnaround)
python analysis/turnaround.py --mode turnaround

# 탑승률 시나리오 (30% / 50% / 75% / 100%)
python analysis/turnaround.py --mode occupancy

# 소셜 디스턴싱 (격행 / 창가만 / 체커보드)
python analysis/turnaround.py --mode distancing

# 전체 (기종 + 전략 지정 가능)
python analysis/turnaround.py \
  --mode all \
  --aircraft narrow_body twin_aisle flying_wing \
  --strategies Random BySeat BackToFront Steffen \
  --trials 50
```

---

### 5. 격자 시각화

```bash
# PNG 스냅샷 그리드 (기본)
python visualization/realtime.py --aircraft narrow_body --strategy BySeat

# GIF 애니메이션
python visualization/realtime.py \
  --aircraft narrow_body \
  --strategy Steffen \
  --format gif \
  --interval 15   # 캡처 간격 (틱)

# 기종별 시각화
python visualization/realtime.py --aircraft twin_aisle  --strategy BySeat
python visualization/realtime.py --aircraft flying_wing --strategy Random
```

생성 파일: `results/boarding_snapshots_{aircraft}_{strategy}.png`

---

## 🛫 항공기 기종

| 기종 | 좌석 | 통로 | 입구 | 특징 |
|------|------|------|------|------|
| `narrow_body` | 198석 | 1개 | 1개 | 33행 × 6열 (A-F) |
| `twin_aisle` | 242석 | 2개 | 2개 | 전방 95석 + 후방 147석, 7열 |
| `flying_wing` | 318석 | 4개 | 1개 | 14행 × 24열, 비직사각형 날개 |

---

## 🎯 탑승 전략

| 전략 | 복잡도 C | 설명 |
|------|----------|------|
| `Random` | 0.000 | 완전 무작위 |
| `BackToFront` | 0.208 | 뒷열 → 앞열 3구역 |
| `FrontToBack` | 0.208 | 앞열 → 뒷열 |
| `BySection` | 0.208 | 3구역 분할 (뒤부터) |
| `BySeat` | 0.208 | 창가 → 중간 → 통로 |
| `Steffen` | 1.000 | 이론적 최적 (2008) |

복잡도 C = ln(M) / ln(N), M = 우선순위 그룹 수, N = 전체 승객 수.

---

## 📊 주요 파라미터 (`config.py`)

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `TICK_DURATION` | 0.5s | 1틱 = 0.5초 |
| `ADULT_WALK_SPEED` | 2 tick/칸 | 성인 보행 속도 (≈1.0s/칸) |
| `SENIOR_WALK_SPEED` | 4 tick/칸 | 노약자 보행 속도 |
| `WEIBULL_K` | 5.153 | 짐 적재 시간 Weibull 형태 파라미터 |
| `WEIBULL_LAMBDA` | 7.774s | 짐 적재 시간 Weibull 척도 파라미터 |
| `GROUP_DISOBEY_PROB` | 0.30 | 그룹 단위 비순응 확률 |
| `R_J_MAX` | 0.50 | 최대 새치기 비율 |
| `LATE_ARRIVAL_RATE` | 0.05 | 지각 승객 비율 |
| `MC_TRIALS` | 200 | Monte Carlo 기본 반복 횟수 |

---

## 📌 참고 문헌

- Steffen, J.H. (2008). Optimal boarding method for airline passengers. *Journal of Air Transport Management*, 14(3).
- Qiang, S., Jia, B. and Huang, Q. (2017). Evaluation of airplane boarding/deboarding strategies. *Symmetry*, 9(10).
- Baek, Y., Ha, M. and Jeong, H. (2013). Impact of sequential disorder on the scaling behavior of airplane boarding time. *Physical Review E*, 87(5).
- IMMC 2022 Problem Statement & Outstanding Solutions (Teams 2022019, 2022031, 2022038).
