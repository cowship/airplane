# main.py
import random
from passenger import Passenger
from airplane import Airplane
from boarding_system import BoardingStrategy, QueueManager

def generate_passengers(num_rows, bag_weights=(0.2, 0.6, 0.2)):  # 파라미터 추가
    passengers = []
    pid = 1
    seats = ['A', 'B', 'C', 'D', 'E', 'F']
    for row in range(1, num_rows + 1):
        for seat in seats:
            age = "senior" if random.random() < 0.1 else "adult"
            passengers.append(Passenger(pid, row, seat, age_group=age, bag_weights=bag_weights))  # bag_weights 전달
            pid += 1
    return passengers

def run_simulation(strategy_name, non_compliance_rate=0.1, bag_weights=(0.2, 0.6, 0.2)):
    plane = Airplane(num_rows=33)
    passengers = generate_passengers(33, bag_weights=bag_weights)  # 수하물 개수 분포 제어
    
    # 전략 선택
    strategy_map = {
        "Random":       BoardingStrategy.random_boarding,
        "BackToFront":  BoardingStrategy.back_to_front,
        "BySeat":       BoardingStrategy.by_seat,           # 추가한 경우
        "BySection_Aft": BoardingStrategy.by_section,       # 추가한 경우
        "Steffen":      BoardingStrategy.steffen_method,   # 추가한 경우
    }
        
    # 줄 세우기 (규칙 미준수자 10% 반영)
    if strategy_name not in strategy_map:
        raise ValueError(f"알 수 없는 전략: '{strategy_name}'. 가능한 전략: {list(strategy_map.keys())}")

    strategy = strategy_map[strategy_name]

    queue = QueueManager(passengers, strategy, non_compliance_rate=non_compliance_rate)
    
    time_ticks = 0
    total_passengers = len(passengers)
    seated_count = 0
    
    # 시뮬레이션 메인 루프 (모든 승객이 앉을 때까지)
    while seated_count < total_passengers:
        time_ticks += 1
        
        # 1. 통로에 있는 승객들 행동 업데이트 (뒤에서부터 역순으로 처리)
        for row in range(plane.num_rows, 0, -1):
            p = plane.aisle.cells[row]
            if p is not None:
                p.act(plane)
                # act() 수행 후 상태가 'seated'로 변했다면 카운트 증가
                if p.state == 'seated':
                    seated_count += 1
        
        # 2. 비행기 입구(1열)가 비어있으면 대기열에서 새 승객 입장
        if plane.aisle.cells[1] is None:
            next_p = queue.pop_next_passenger()
            if next_p:
                plane.aisle.cells[1] = next_p
                next_p.current_pos = 1
                next_p.state = 'walking'
                
        # 무한 루프 방지용 (10배 스케일 고려하여 넉넉히 50000틱으로 설정)
        if time_ticks > 50000:
            print(f"⚠️ [{strategy_name}] 시뮬레이션 시간 초과 (Deadlock 의심)")
            break

    # 결과 출력 (10 Ticks = 1초 로 환산)
    real_time_sec = time_ticks / 10
    print(f"[{strategy_name}] 탑승 완료! 총 소요 시간: {time_ticks} Ticks (약 {real_time_sec:.1f}초)")
    
    return time_ticks

if __name__ == "__main__":
    print("🚀 시뮬레이션을 시작합니다...\n")
    
    # 여러 전략을 연속으로 실행하여 비교
    run_simulation("Random")
    run_simulation("BackToFront")