# boarding_system.py
import random

class BoardingStrategy:
    """탑승 전략들을 모아둔 클래스 (Static Method 사용)"""
    @staticmethod
    def random_boarding(passengers):
        # 무작위 탑승 전략
        random.shuffle(passengers)
        return passengers
        
    @staticmethod
    def back_to_front(passengers):
        # 뒷열부터 탑승하는 전략 (열 번호 내림차순 정렬)
        return sorted(passengers, key=lambda p: p.target_row, reverse=True)
    
    @staticmethod
    def by_section(passengers, order='aft_first'):
        """구역별 탑승: aft(23-33), mid(12-22), bow(1-11)"""
        def section(row):
            if row >= 23: return 0   # aft
            elif row >= 12: return 1  # mid
            else: return 2            # bow
        reverse = (order == 'aft_first')
        return sorted(passengers, key=lambda p: section(p.target_row), reverse=reverse)

    @staticmethod
    def by_seat(passengers):
        """창가 → 중간 → 통로 순서"""
        priority = {'A': 0, 'F': 0, 'B': 1, 'E': 1, 'C': 2, 'D': 2}
        return sorted(passengers, key=lambda p: priority[p.target_seat])

    @staticmethod
    def steffen_method(passengers):
        """Steffen: 홀짝 행 + 창가→통로 조합 (추가 창의 전략)"""
        priority = {'A': 0, 'F': 0, 'B': 1, 'E': 1, 'C': 2, 'D': 2}
        return sorted(passengers, key=lambda p: (
            priority[p.target_seat],
            p.target_row % 2,   # 홀수행 먼저
            -p.target_row        # 뒤에서 앞
        ))

class QueueManager:
    """승객들을 줄 세우고 비행기에 밀어넣는 클래스"""
    def __init__(self, passengers, strategy_func, non_compliance_rate=0.1):
        # 1. 전략에 따라 1차 줄 세우기
        self.queue = strategy_func(passengers)
        # 2. 지시를 따르지 않는 승객 반영 (줄 섞기)
        self._apply_non_compliance(non_compliance_rate)
        
    def _apply_non_compliance(self, rate):
        """일정 비율의 승객이 자기 순서를 지키지 않음"""
        num_rule_breakers = int(len(self.queue) * rate)
        for _ in range(num_rule_breakers):
            # 무작위 두 명의 순서를 바꿈(Swap)
            idx1, idx2 = random.sample(range(len(self.queue)), 2)
            self.queue[idx1], self.queue[idx2] = self.queue[idx2], self.queue[idx1]

    def pop_next_passenger(self):
        """줄 맨 앞의 승객을 한 명씩 뽑아서 반환"""
        if self.queue:
            return self.queue.pop(0)
        return None