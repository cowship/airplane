# config.py — 모든 상수를 한 곳에서 관리

# ── 시간 기반 ────────────────────────────────────────────────
TICK_DURATION        = 0.5   # 1틱 = 0.5초
# 2022019: 통로 1칸 = 1.05s → 2.1틱 → 반올림 2틱
# 2022031: 통로 1칸 = 1.42s → 2.84틱 → 반올림 3틱
# 두 논문 중간값인 2틱(1.0s) 사용
AISLE_MOVE_TICKS     = 2     # 통로 1칸 이동 (≈ 1.0초)
ROW_MOVE_TICKS       = 2     # 좌석 횡이동 1칸 (≈ 1.0초)
STAND_UP_TICKS       = 4     # 일어서는 시간 (≈ 2.0초)
SIT_DOWN_TICKS       = 3     # 앉는 시간 (≈ 1.5초)
CONFUSED_DELAY_TICKS = 20    # 좌석 착각 시 낭비 시간 (≈ 10초)

# ── 짐 모델 ────────────────────────────────────────────────
# Weibull 파라미터: 2022031 실측값 기반 (k=5.153, λ=7.774)
USE_WEIBULL          = True           # True: Weibull / False: 포화도 수식
WEIBULL_K            = 5.153          # Weibull 형태 파라미터
WEIBULL_LAMBDA       = 7.774          # Weibull 척도 파라미터 (초)
WEIBULL_MIN_SEC      = 1.9            # 실측 최솟값 클리핑
WEIBULL_MAX_SEC      = 10.7           # 실측 최댓값 클리핑
BAG_PROB             = [0.20, 0.70, 0.10]   # 0개, 1개, 2개 짐 확률

# 빈 오버헤드 기준 짐 적재 시간 (2022019 수식 — USE_WEIBULL=False 일 때 사용)
BAG_BASE_TIME_SEC    = 4.0    # 짐 1개, 빈 칸 기준
BAG_FILL_COEFF       = 0.8    # 포화도 계수
BAG_EXTRA_SEC        = 2.25   # 짐 2개일 때 추가 시간
OVERHEAD_BIN_MAX     = 6      # 오버헤드 빈 최대 용량 (행당)

# ── 승객 행동 ────────────────────────────────────────────────
NON_COMPLIANCE_RATE  = 0.10   # 비순응 승객 비율 (기본)
LATE_ARRIVAL_RATE    = 0.05   # 늦게 도착하는 승객 비율
QUEUE_JUMP_RANGE     = 12     # 새치기 이항분포 범위 (±6칸)
CONFUSED_PROB        = 0.05   # 좌석 착각 확률

# 나이 그룹
SENIOR_PROB          = 0.10   # 노약자 비율
# AISLE_MOVE_TICKS 를 기준으로 배속 설정
SENIOR_WALK_SPEED    = 4      # 노약자: 4틱/칸 (≈ 2.0초 — 성인의 2배)
ADULT_WALK_SPEED     = 2      # 성인: 2틱/칸 (≈ 1.0초) ← AISLE_MOVE_TICKS 와 동기화
SENIOR_STOW_MULT     = 1.5    # 노약자 짐 적재 시간 배율

# ── 그룹 승객 ────────────────────────────────────────────────
GROUP_PROB          = [0.70, 0.20, 0.10]   # 크기 1, 2, 3

# ── 몬테카를로 ────────────────────────────────────────────────
MC_TRIALS           = 200
RANDOM_SEED         = 42

# ── 출력 ────────────────────────────────────────────────────
RESULTS_DIR         = "results/"
SAVE_PLOTS          = True
SAVE_JSON           = True
MAX_TICKS           = 50_000        # 무한루프 방지 상한