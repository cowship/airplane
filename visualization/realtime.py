# visualization/realtime.py
"""
탑승 과정 실시간 격자 시각화.

PNG 스냅샷 시퀀스 저장 또는 matplotlib 애니메이션(.gif) 생성.

사용 예:
    python visualization/realtime.py                        # NarrowBody BySeat GIF
    python visualization/realtime.py --aircraft twin_aisle --strategy Random
    python visualization/realtime.py --format png --interval 50
"""
from __future__ import annotations
from typing import Optional
import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.axes
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import matplotlib.colors as mcolors

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
import random
from aircraft import get_aircraft, AIRCRAFT
from aircraft.base import AircraftBase
from boarding.methods import get_strategy, STRATEGIES
from boarding.group_model import assign_groups
from boarding.queue_model import QueueManager
from simulation.engine import run_boarding
from main import generate_passengers  # type: ignore[import]


# ── 상태별 색상 ────────────────────────────────────────────────
_STATE_COLOR = {
    "empty":    "#F0F0F0",   # 빈 좌석
    "waiting":  "#AED6F1",   # 대기
    "walking":  "#F39C12",   # 통로 이동 중
    "stowing":  "#E74C3C",   # 짐 적재 중
    "seating":  "#F1C40F",   # 착석 중
    "seated":   "#2ECC71",   # 착석 완료
    "aisle":    "#D5D8DC",   # 통로
}


# ── 격자 캡처 ────────────────────────────────────────────────

class BoardingRecorder:
    """
    시뮬레이션 진행 중 매 tick 마다 격자 상태를 기록한다.
    """

    def __init__(self, airplane: AircraftBase) -> None:
        self.airplane  = airplane
        self.snapshots: list[dict[tuple[int, str], str]] = []

    def capture(self) -> None:
        """현재 좌석 상태를 스냅샷으로 저장."""
        snap: dict[tuple[int, str], str] = {}
        for row, row_seats in self.airplane.seats.items():
            for col, p in row_seats.items():
                if p is None:
                    snap[(row, col)] = "empty"
                else:
                    snap[(row, col)] = p.state
        self.snapshots.append(snap)


def run_with_recording(
    airplane: AircraftBase,
    strategy_name: str,
    capture_every: int = 10,
    seed: int = config.RANDOM_SEED,
) -> BoardingRecorder:
    """탑승 시뮬레이션을 capture_every 틱마다 상태를 기록하며 실행."""
    random.seed(seed)
    recorder   = BoardingRecorder(airplane)
    passengers = generate_passengers(airplane)
    assign_groups(passengers)
    strategy   = get_strategy(strategy_name)
    queue_mgr  = QueueManager(passengers, strategy, strategy_name=strategy_name)

    seated = 0
    ticks  = 0
    total  = len(passengers)
    channels = airplane.channels

    # 채널별 큐 분리
    from collections import deque
    ch_queues: list[deque] = [deque() for _ in channels]
    while True:
        p = queue_mgr.pop_next()
        if p is None:
            break
        for idx, ch in enumerate(channels):
            if p.target_seat in ch.seat_cols:
                ch_queues[idx].append(p)
                break

    recorder.capture()   # tick=0 초기 상태

    while seated < total:
        ticks += 1
        if ticks > config.MAX_TICKS:
            break

        for ch in channels:
            aisle = ch.aisle
            for pos in range(airplane.num_rows, 0, -1):
                p = aisle.cells[pos]
                if p is None:
                    continue
                prev = p.state
                p.act(airplane)
                if prev != "seated" and p.state == "seated":
                    seated += 1

        for idx, ch in enumerate(channels):
            aisle = ch.aisle
            entry = ch.entrance_row
            if aisle.cells[entry] is None and ch_queues[idx]:
                next_p = ch_queues[idx].popleft()
                aisle.cells[entry] = next_p
                next_p.current_pos = entry
                next_p.state       = "walking"

        if ticks % capture_every == 0:
            recorder.capture()

    recorder.capture()   # 최종 상태
    return recorder


# ── 단일 프레임 렌더링 ─────────────────────────────────────────

def _render_frame(
    ax: matplotlib.axes.Axes,
    snapshot: dict[tuple[int, str], str],
    airplane: AircraftBase,
    tick: int,
) -> None:
    """주어진 스냅샷으로 ax를 업데이트."""
    ax.clear()
    slots    = airplane.passenger_slots()
    all_rows = sorted({r for r, _ in slots})
    all_cols = list(airplane.seat_cols)

    n_rows = len(all_rows)
    n_cols = len(all_cols)
    row_idx = {r: i for i, r in enumerate(all_rows)}
    col_idx = {c: j for j, c in enumerate(all_cols)}

    # 격자 그리기
    for (row, col), state in snapshot.items():
        if (row, col) not in {s for s in slots}:
            continue
        i = row_idx[row]
        j = col_idx[col]
        color = _STATE_COLOR.get(state, "#FFFFFF")
        rect  = mpatches.FancyBboxPatch(
            (j - 0.45, n_rows - i - 1 - 0.45), 0.9, 0.9,
            boxstyle="round,pad=0.05",
            facecolor=color,
            edgecolor="#AAAAAA",
            linewidth=0.5,
        )
        ax.add_patch(rect)

    # 통로 표시 (회색 세로선)
    aisle_cols_set = set()
    for ch in airplane.channels:
        aisle_cols_set |= ch.seat_cols
    # 채널 경계 사이에 통로선
    for idx in range(len(airplane.channels) - 1):
        ch0 = airplane.channels[idx]
        ch1 = airplane.channels[idx + 1]
        last_col  = sorted(ch0.seat_cols, key=lambda c: col_idx.get(c, 0))[-1]
        first_col = sorted(ch1.seat_cols, key=lambda c: col_idx.get(c, 0))[0]
        x_aisle   = (col_idx[last_col] + col_idx[first_col]) / 2
        ax.axvline(x_aisle, color="#999999", linewidth=1.5, zorder=0)

    ax.set_xlim(-0.6, n_cols - 0.4)
    ax.set_ylim(-0.6, n_rows - 0.4)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(all_cols, fontsize=7)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels([str(r) for r in reversed(all_rows)], fontsize=6)
    ax.set_title(f"Tick {tick}", fontsize=10)
    ax.set_aspect("equal")

    # 범례
    legend_elements = [
        mpatches.Patch(facecolor=_STATE_COLOR[s], edgecolor="#999", label=s)
        for s in ["empty", "walking", "stowing", "seating", "seated"]
    ]
    ax.legend(handles=legend_elements, loc="upper right",
              fontsize=6, framealpha=0.7, ncol=1)


# ── GIF 저장 ──────────────────────────────────────────────────

def save_gif(
    recorder: BoardingRecorder,
    aircraft_name: str,
    strategy_name: str,
    capture_every: int,
    out_dir: str = config.RESULTS_DIR,
    fps: int     = 8,
) -> str:
    """스냅샷 시퀀스를 GIF 애니메이션으로 저장."""
    os.makedirs(out_dir, exist_ok=True)
    airplane  = recorder.airplane
    snapshots = recorder.snapshots

    fig, ax = plt.subplots(figsize=(max(6, len(airplane.seat_cols) * 0.5),
                                    max(5, airplane.num_rows * 0.25)))
    fig.suptitle(f"{aircraft_name} — {strategy_name}", fontsize=11, fontweight="bold")

    def update(frame_idx: int) -> list[matplotlib.patches.Patch]:  # type: ignore[return]
        tick = frame_idx * capture_every
        _render_frame(ax, snapshots[frame_idx], airplane, tick)
        return []

    ani = animation.FuncAnimation(
        fig,
        update,
        frames=len(snapshots),
        interval=1000 // fps,
        repeat=False,
    )

    path = os.path.join(out_dir, f"boarding_{aircraft_name}_{strategy_name}.gif")
    ani.save(path, writer="pillow", fps=fps)
    plt.close(fig)
    print(f"  저장: {path}")
    return path


# ── PNG 스냅샷 저장 ────────────────────────────────────────────

def save_snapshots(
    recorder: BoardingRecorder,
    aircraft_name: str,
    strategy_name: str,
    capture_every: int,
    n_frames: int = 6,
    out_dir: str  = config.RESULTS_DIR,
) -> str:
    """대표 프레임 n_frames 개를 PNG 그리드로 저장."""
    os.makedirs(out_dir, exist_ok=True)
    airplane  = recorder.airplane
    snapshots = recorder.snapshots

    # 균등 간격 프레임 선택
    indices = np.linspace(0, len(snapshots) - 1, n_frames, dtype=int)

    cols = min(3, n_frames)
    rows = (n_frames + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols,
                             figsize=(cols * max(4, len(airplane.seat_cols) * 0.4),
                                      rows * max(3, airplane.num_rows * 0.22)))
    fig.suptitle(f"{aircraft_name} — {strategy_name} (Boarding Progress)",
                 fontsize=11, fontweight="bold")

    flat_axes: list[matplotlib.axes.Axes] = list(np.array(axes).flatten())
    for i, idx in enumerate(indices):
        tick = int(idx * capture_every)
        _render_frame(flat_axes[i], snapshots[idx], airplane, tick)

    # 남는 subplot 숨김
    for j in range(n_frames, len(flat_axes)):
        flat_axes[j].set_visible(False)

    fig.tight_layout()
    path = os.path.join(out_dir,
                        f"boarding_snapshots_{aircraft_name}_{strategy_name}.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path}")
    return path


# ── CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="탑승 격자 시각화")
    parser.add_argument("--aircraft", "-a",
                        choices=list(AIRCRAFT.keys()), default="narrow_body")
    parser.add_argument("--strategy", "-s",
                        choices=list(STRATEGIES.keys()), default="BySeat")
    parser.add_argument("--format",
                        choices=["gif", "png"], default="png",
                        help="출력 형식 (gif 또는 png 스냅샷 그리드)")
    parser.add_argument("--interval",  type=int, default=20,
                        help="캡처 간격 (틱 수, 기본 20)")
    parser.add_argument("--seed",      type=int, default=config.RANDOM_SEED)
    args = parser.parse_args()

    print(f"\n  기종: {args.aircraft}  전략: {args.strategy}  형식: {args.format}")
    airplane = get_aircraft(args.aircraft)

    print("  시뮬레이션 실행 중...")
    recorder = run_with_recording(
        airplane, args.strategy,
        capture_every=args.interval,
        seed=args.seed,
    )
    print(f"  스냅샷 {len(recorder.snapshots)}개 수집 완료")

    if args.format == "gif":
        save_gif(recorder, args.aircraft, args.strategy, args.interval)
    else:
        save_snapshots(recorder, args.aircraft, args.strategy, args.interval)


if __name__ == "__main__":
    main()