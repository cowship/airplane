# airplane.py
import config


class Aisle:
    """통로 셀 상태 관리."""

    def __init__(self, num_rows: int):
        # 인덱스 0은 미사용, 1 ~ num_rows 사용
        self.cells = [None] * (num_rows + 2)

    def is_clear(self, pos: int) -> bool:
        """pos+1 칸이 비어 있는지 확인."""
        next_pos = pos + 1
        if next_pos < len(self.cells):
            return self.cells[next_pos] is None
        return False

    def move_passenger(self, passenger, from_pos: int, to_pos: int) -> None:
        self.cells[from_pos] = None
        self.cells[to_pos]   = passenger


class Airplane:
    """
    좁은 동체(Narrow-body) 비행기 모델.
    좌석: A B C | D E F (3+3), 행: 1 ~ num_rows
    통로: 중앙 1개
    """

    SEAT_COLS = ('A', 'B', 'C', 'D', 'E', 'F')

    def __init__(self, num_rows: int = 33):
        self.num_rows = num_rows
        self.aisle    = Aisle(num_rows)
        self.seats    = {
            row: {col: None for col in self.SEAT_COLS}
            for row in range(1, num_rows + 1)
        }
        # 오버헤드 빈 사용량 추적 (행별)
        self._bins_used: dict[int, int] = {row: 0 for row in range(1, num_rows + 1)}

    def use_bin(self, row: int, n_bags: int) -> int:
        """짐을 실을 때 사용 빈 수 업데이트. 실기 전 사용량을 반환."""
        used = self._bins_used[row]
        self._bins_used[row] = min(used + n_bags, config.OVERHEAD_BIN_MAX)
        return used

    def bins_used(self, row: int) -> int:
        return self._bins_used[row]

    def calculate_interference(self, row: int, target_seat: str) -> int:
        """
        창가/중간 좌석 승객이 앉을 때 이미 착석한 승객이 일어나야 하는
        추가 지연 틱 수 계산.
        """
        row_seats = self.seats[row]
        delay = 0

        # 왼쪽 (A=창가, B=중간, C=통로)
        if target_seat == 'A':
            if row_seats['C'] is not None:
                delay += config.STAND_UP_TICKS
            if row_seats['B'] is not None:
                delay += config.STAND_UP_TICKS
        elif target_seat == 'B':
            if row_seats['C'] is not None:
                delay += config.STAND_UP_TICKS

        # 오른쪽 (D=통로, E=중간, F=창가)
        elif target_seat == 'F':
            if row_seats['D'] is not None:
                delay += config.STAND_UP_TICKS
            if row_seats['E'] is not None:
                delay += config.STAND_UP_TICKS
        elif target_seat == 'E':
            if row_seats['D'] is not None:
                delay += config.STAND_UP_TICKS

        return delay

    def is_full(self) -> bool:
        """모든 좌석이 착석 완료인지 확인."""
        return all(
            p is not None and p.state == "seated"
            for row in self.seats.values()
            for p in row.values()
        )

    def seated_count(self) -> int:
        return sum(
            1
            for row in self.seats.values()
            for p in row.values()
            if p is not None and p.state == "seated"
        )

    def reset(self) -> None:
        """시뮬레이션 재실행을 위해 초기화."""
        self.aisle    = Aisle(self.num_rows)
        self.seats    = {
            row: {col: None for col in self.SEAT_COLS}
            for row in range(1, self.num_rows + 1)
        }
        self._bins_used = {row: 0 for row in range(1, self.num_rows + 1)}