# airplane.py

class Aisle:
    """통로의 상태만 전문적으로 관리하는 클래스"""
    def __init__(self, num_rows):
        self.cells = [None] * (num_rows + 1)
        
    def is_clear(self, position):
        if position + 1 < len(self.cells):
            return self.cells[position + 1] is None
        return False
        
    def move_passenger(self, passenger, current_pos, next_pos):
        self.cells[current_pos] = None
        self.cells[next_pos] = passenger

class Airplane:
    """비행기 전체 격자 및 좌석을 관리하는 클래스"""
    def __init__(self, num_rows=33):
        self.num_rows = num_rows
        self.aisle = Aisle(num_rows) # 통로 객체 생성
        
        # 좌석 배열 (Dictionary 활용)
        self.seats = {row: {'A': None, 'B': None, 'C': None, 
                            'D': None, 'E': None, 'F': None} 
                      for row in range(1, num_rows + 1)}

    def calculate_interference(self, row, target_seat):
        """지나가야 하는 사람 수 * 10틱을 반환하는 함수"""
        """좌석 간섭(안쪽 사람 들어갈 때 걸리는 시간) 계산 함수"""
        penalty = 0
        row_seats = self.seats[row]
        
        # 왼쪽 좌석 (A: 창가, B: 중간, C: 통로)
        if target_seat == 'A':
            if row_seats['B'] is not None: penalty += 10
            if row_seats['C'] is not None: penalty += 10
        elif target_seat == 'B':
            if row_seats['C'] is not None: penalty += 10
            
        # 오른쪽 좌석 (D: 통로, E: 중간, F: 창가)
        elif target_seat == 'F':
            if row_seats['E'] is not None: penalty += 10
            if row_seats['D'] is not None: penalty += 10
        elif target_seat == 'E':
            if row_seats['D'] is not None: penalty += 10
            
        return penalty # 1명당 1틱 지연