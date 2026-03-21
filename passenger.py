# passenger.py
import random

class Passenger:
    def __init__(self, pass_id, target_row, target_seat, age_group="adult", bag_weights=(0.2, 0.6, 0.2)):
        self.id = pass_id
        self.target_row = target_row
        self.target_seat = target_seat
        self.state = 'waiting' # 상태
        self.current_pos = 0   # 현재 위치
        self.walk_timer = 0 # 걷기 속도 조절용 타이머 추가
        
        # 1. 나이에 따른 기본 속성 (txt 파일 아이디어 반영)
        self.age_group = age_group 
        if self.age_group == "senior":
            self.walk_speed = 20         # 노약자는 1칸 가는데 2틱 소요
            self.stow_multiplier = 1.5  # 짐 넣는 시간 1.5배 지연
        else:
            self.walk_speed = 10         # 성인은 1칸 가는데 1틱 소요
            self.stow_multiplier = 1.0
            
        # 2. 수하물 설정 (0~2개)
        self.num_bags = random.choices([0, 1, 2], weights=bag_weights)[0]
        self.stow_time = self._calculate_stow_time()
        
        # 3. 돌발 변수 및 시간 관리
        self.sit_time = 10 # 앉는 시간 (상수)
        self.delay_timer = 0
        self.is_confused = random.random() < 0.05 # 좌석 착각 확률
        
    def _calculate_stow_time(self):
        """수하물 개수와 나이 계수를 고려해 짐 넣는 시간 계산"""
        if self.num_bags == 0:
            return 0
        elif self.num_bags == 1:
            base_time = random.randint(2, 3)
        else:
            base_time = random.randint(3, 4)
        return int(base_time * self.stow_multiplier * 10) # 기본 시간에 나이 계수 적용 (10틱 단위로 변환)

    def act(self, airplane):
        """매 틱마다 승객의 상태에 따른 행동 수행"""
        # 이미 앉았으면 아무것도 안 함
        if self.state == 'seated':
            return
            
        # --- [1단계: 상태 전이 체크] ---
        # 짐 넣기가 끝났는지 확인 (stow_time이 0인 경우도 즉시 처리됨)
        if self.state == 'stowing' and self.delay_timer <= 0:
            self.state = 'seating'
            # (기본 앉는 시간) + (지나가야 하는 사람 수 * 1틱)
            interference = airplane.calculate_interference(self.target_row, self.target_seat)
            self.delay_timer = self.sit_time + interference
            
        # 자리에 들어가는 과정이 끝났는지 확인
        if self.state == 'seating' and self.delay_timer <= 0:
            self.state = 'seated'
            airplane.aisle.cells[self.current_pos] = None # 통로에서 비켜줌
            airplane.seats[self.target_row][self.target_seat] = self # 내 자리에 착석
            return # 착석 완료 시 행동 종료

        # --- [2단계: 시간(Tick) 소모 및 행동] ---
        # 짐을 넣거나(stowing) 자리에 들어가는(seating) 중이면 시간만 보냄
        if self.delay_timer > 0:
            self.delay_timer -= 1
            return 

        # 통로를 걷고(walking) 있는 경우의 로직
        if self.state == 'walking':
            # 1. 내 목표 열에 도착했는가?
            if self.current_pos == self.target_row:
                self.state = 'stowing'
                self.delay_timer = self.stow_time # 짐 넣는 시간 설정
                self.walk_timer = 0

            if self.is_confused and self.current_pos == self.target_row:
                # 5% 확률로 잘못된 열에 정지 → 10틱 낭비 후 이동 재개
                self.is_confused = False
                self.delay_timer = 10  # 착각으로 인한 지연
                return
            
            # 2. 목표 열이 아니라면 전진 시도
            else:
                # 앞 칸에 사람(짐 넣거나 걷는 중인 사람)이 없는지 확인
                if airplane.aisle.is_clear(self.current_pos):
                    self.walk_timer += 10
                    # 보행 속도(예: 10틱 또는 20틱)만큼 시간이 찼으면 실제 이동
                    if self.walk_timer >= self.walk_speed:
                        next_pos = self.current_pos + 1
                        airplane.aisle.move_passenger(self, self.current_pos, next_pos)
                        self.current_pos = next_pos
                        self.walk_timer = 0 # 이동 후 타이머 초기화
                else:
                    # 앞사람이 막고 있으면 타이머 초기화하고 대기
                    self.walk_timer = 0