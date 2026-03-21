# airplane.py
"""
[DEPRECATED] Phase 3에서 aircraft/ 패키지로 대체됨.

이 파일은 하위 호환성을 위해 유지합니다.
새 코드에서는 aircraft.get_aircraft() 를 사용하세요.

    from aircraft import get_aircraft
    airplane = get_aircraft("narrow_body")
"""
from aircraft.narrow_body import NarrowBody as Airplane
from aircraft.base import Aisle

__all__ = ["Airplane", "Aisle"]