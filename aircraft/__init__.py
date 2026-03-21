# aircraft/__init__.py
from __future__ import annotations
from aircraft.base import AircraftBase, Aisle, BoardingChannel
from aircraft.narrow_body import NarrowBody
from aircraft.twin_aisle import TwinAisle
from aircraft.flying_wing import FlyingWing

AIRCRAFT: dict[str, type[AircraftBase]] = {
    "narrow_body": NarrowBody,
    "twin_aisle":  TwinAisle,
    "flying_wing": FlyingWing,
}


def get_aircraft(name: str) -> AircraftBase:
    """이름으로 항공기 인스턴스 생성."""
    if name not in AIRCRAFT:
        raise ValueError(
            f"알 수 없는 기종: '{name}'. "
            f"가능한 기종: {list(AIRCRAFT.keys())}"
        )
    return AIRCRAFT[name]()