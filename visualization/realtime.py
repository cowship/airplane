# visualization/realtime.py
"""
탑승 과정 격자 시각화.

- 좌석 셀 + 통로 셀 정확히 렌더링
- TwinAisle: 전방·후방 섹션을 세로로 이어붙여 표시 (2통로, 긴 평면)
- FlyingWing: 4통로 (채널 간 경계는 통로 아님)
- PNG 스냅샷 (2×3 그리드) / GIF 저장

사용 예:
    python visualization/realtime.py
    python visualization/realtime.py --aircraft twin_aisle
    python visualization/realtime.py --format gif --interval 15
"""
from __future__ import annotations
import argparse, os, sys, random
from datetime import datetime
from collections import deque

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.axes
import matplotlib.patches as mpatches
import matplotlib.animation as animation

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from aircraft import get_aircraft, AIRCRAFT
from aircraft.base import AircraftBase
from boarding.methods import get_strategy, STRATEGIES
from boarding.group_model import assign_groups
from boarding.queue_model import QueueManager
from main import generate_passengers  # type: ignore[import]


# ── 색상 ─────────────────────────────────────────────────────────
_SEAT: dict[str, str] = {
    "empty":   "#EFEFEF",
    "walking": "#F39C12",
    "stowing": "#E74C3C",
    "seating": "#F1C40F",
    "seated":  "#2ECC71",
}
_AISLE_EMPTY = "#B8C9D4"
_AISLE_BG    = "#D0DCE4"
_NO_SEAT_BG  = "#F8F8F8"   # 좌석 없는 영역 (FlyingWing 날개 끝 등)

Snapshot = dict[tuple[int, str], str]
# snap[(row, 'A')]   = seat state  ('', 'empty', 'walking', ...)
# snap[(row, 'ch0')] = ch0 aisle state at that row


# ── 레이아웃 정보 추출 ────────────────────────────────────────────
def _get_display_info(airplane: AircraftBase) -> dict:
    """
    기종별 display 설정 반환.
    반환값:
        display_cols  : 열 시퀀스 (예: ['A','B','AISLE','C','D','E','AISLE','F','G'])
        display_rows  : 표시할 행 번호 리스트 (예: [1,2,...,35])
        col_to_x      : 좌석 열 → x 인덱스
        aisle_to_x    : aisle_idx → x 인덱스
        seat_mapper   : (sim_row, sim_col) → (disp_row, disp_col)  None이면 표시 안함
        aisle_state   : (aisle_idx, disp_row, snap) → state 문자열
    """
    display_cols = list(getattr(airplane, 'DISPLAY_COLS',
                                list(airplane.seat_cols)))

    # x 좌표 계산
    col_to_x:   dict[str, int] = {}
    aisle_to_x: dict[int, int] = {}
    aisle_cnt = 0
    for x, item in enumerate(display_cols):
        if item == 'AISLE':
            aisle_to_x[aisle_cnt] = x
            aisle_cnt += 1
        else:
            col_to_x[item] = x

    # ── TwinAisle 전용 ────────────────────────────────────────────
    back_remap   = getattr(airplane, 'BACK_REMAP',    {})
    front_depth  = getattr(airplane, 'FRONT_DEPTH',   0)
    back_depth   = getattr(airplane, 'BACK_DEPTH',    0)
    aisle_split  = getattr(airplane, 'AISLE_SPLIT_MAP', None)
    aisle_simple = getattr(airplane, 'AISLE_CH_MAP',  None)

    if back_remap:
        # TwinAisle: display rows = 전방 1-14 + 후방 15-35
        display_rows = list(range(1, front_depth + back_depth + 1))

        def seat_mapper(sim_row: int, sim_col: str):
            if sim_col in back_remap:
                return (sim_row + front_depth, back_remap[sim_col])
            else:
                return (sim_row, sim_col)

        def aisle_state(aisle_idx: int, disp_row: int, snap: Snapshot) -> str:
            assert aisle_split is not None
            front_ch, back_ch = aisle_split[aisle_idx]
            if disp_row <= front_depth:
                return snap.get((disp_row, f'ch{front_ch}'), '')
            else:
                return snap.get((disp_row - front_depth, f'ch{back_ch}'), '')

    else:
        # NarrowBody / FlyingWing
        display_rows = sorted({r for r, _ in airplane.passenger_slots()})

        def seat_mapper(sim_row: int, sim_col: str):
            return (sim_row, sim_col)

        _ach = aisle_simple or {}
        def aisle_state(aisle_idx: int, disp_row: int, snap: Snapshot) -> str:
            ch_idx = _ach.get(aisle_idx, aisle_idx)
            return snap.get((disp_row, f'ch{ch_idx}'), '')

    return {
        'display_cols': display_cols,
        'display_rows': display_rows,
        'col_to_x':     col_to_x,
        'aisle_to_x':   aisle_to_x,
        'seat_mapper':  seat_mapper,
        'aisle_state':  aisle_state,
        'back_remap':   back_remap,
        'front_depth':  front_depth,
    }


# ── 스냅샷 기록 ──────────────────────────────────────────────────
class BoardingRecorder:
    def __init__(self, airplane: AircraftBase) -> None:
        self.airplane  = airplane
        self.snapshots: list[Snapshot] = []

    def capture(self) -> None:
        snap: Snapshot = {}
        # 좌석 상태
        for row, row_seats in self.airplane.seats.items():
            for col, p in row_seats.items():
                snap[(row, col)] = '' if p is None else p.state
        # 통로 상태 (채널별)
        for ch_idx, ch in enumerate(self.airplane.channels):
            key = f'ch{ch_idx}'
            for row in range(1, self.airplane.num_rows + 1):
                p = ch.aisle.cells[row] if row < len(ch.aisle.cells) else None
                snap[(row, key)] = '' if p is None else p.state
        self.snapshots.append(snap)


# ── 시뮬레이션 ───────────────────────────────────────────────────
def run_with_recording(
    airplane:      AircraftBase,
    strategy_name: str,
    capture_every: int = 20,
    seed:          int = config.RANDOM_SEED,
) -> BoardingRecorder:
    random.seed(seed)
    recorder  = BoardingRecorder(airplane)
    passengers = generate_passengers(airplane)
    assign_groups(passengers)
    queue_mgr = QueueManager(passengers, get_strategy(strategy_name),
                              strategy_name=strategy_name)

    channels  = airplane.channels
    ch_queues: list[deque] = [deque() for _ in channels]
    while True:
        p = queue_mgr.pop_next()
        if p is None:
            break
        for idx, ch in enumerate(channels):
            if p.target_seat in ch.seat_cols:
                ch_queues[idx].append(p)
                break

    seated, total, ticks = 0, len(passengers), 0
    recorder.capture()

    while seated < total:
        ticks += 1
        if ticks > config.MAX_TICKS:
            break
        for ch in channels:
            for pos in range(airplane.num_rows, 0, -1):
                p = ch.aisle.cells[pos]
                if p is None:
                    continue
                prev = p.state
                p.act(airplane)
                if prev != 'seated' and p.state == 'seated':
                    seated += 1
        for idx, ch in enumerate(channels):
            if ch.aisle.cells[ch.entrance_row] is None and ch_queues[idx]:
                nxt = ch_queues[idx].popleft()
                ch.aisle.cells[ch.entrance_row] = nxt
                nxt.current_pos = ch.entrance_row
                nxt.state       = 'walking'
        if ticks % capture_every == 0:
            recorder.capture()

    recorder.capture()
    return recorder


# ── 단일 프레임 렌더링 ────────────────────────────────────────────
def _render_frame(
    ax:          matplotlib.axes.Axes,
    snap:        Snapshot,
    airplane:    AircraftBase,
    info:        dict,
    tick:        int,
    show_legend: bool = True,
) -> None:
    ax.clear()

    display_rows = info['display_rows']
    col_to_x     = info['col_to_x']
    aisle_to_x   = info['aisle_to_x']
    seat_mapper  = info['seat_mapper']
    aisle_state  = info['aisle_state']
    back_remap   = info['back_remap']
    front_depth  = info['front_depth']
    n_disp_cols  = len(info['display_cols'])

    n_rows   = len(display_rows)
    row_to_y = {r: n_rows - 1 - i for i, r in enumerate(display_rows)}
    valid    = set(airplane.passenger_slots())

    # ── 통로 배경 띠 ──────────────────────────────────────────────
    for ax_x in aisle_to_x.values():
        ax.add_patch(mpatches.Rectangle(
            (ax_x - 0.5, -0.5), 1.0, n_rows,
            fc=_AISLE_BG, ec='none', zorder=0))

    # ── 좌석 셀 ──────────────────────────────────────────────────
    for (sim_row, sim_col), state in snap.items():
        # 채널 키 건너뜀 (ch0, ch1, ...)
        if not sim_col.isalpha():
            continue
        if (sim_row, sim_col) not in valid:
            continue
        disp_row, disp_col = seat_mapper(sim_row, sim_col)
        x = col_to_x.get(disp_col)
        y = row_to_y.get(disp_row)
        if x is None or y is None:
            continue
        color = _SEAT.get(state or 'empty', _SEAT['empty'])
        ax.add_patch(mpatches.FancyBboxPatch(
            (x - 0.43, y - 0.43), 0.86, 0.86,
            boxstyle='round,pad=0.04',
            fc=color, ec='#999999', lw=0.5, zorder=2))

    # ── 통로 셀 (행마다 개별) ─────────────────────────────────────
    for aisle_idx, ax_x in aisle_to_x.items():
        for disp_row in display_rows:
            y     = row_to_y[disp_row]
            state = aisle_state(aisle_idx, disp_row, snap)
            if state and state not in ('seated', ''):
                fc, ec, lw = _SEAT.get(state, _AISLE_EMPTY), '#555555', 1.0
            else:
                fc, ec, lw = _AISLE_EMPTY, '#AAAAAA', 0.3
            ax.add_patch(mpatches.FancyBboxPatch(
                (ax_x - 0.28, y - 0.43), 0.56, 0.86,
                boxstyle='round,pad=0.02',
                fc=fc, ec=ec, lw=lw, zorder=3))

    # ── TwinAisle: 전방/후방 경계선 ──────────────────────────────
    if back_remap and front_depth > 0 and front_depth in row_to_y:
        y_front = row_to_y[front_depth]
        y_back  = row_to_y.get(front_depth + 1, y_front - 1)
        y_sep   = (y_front + y_back) / 2
        ax.axhline(y_sep, color='#E53935', lw=1.5,
                   linestyle='--', alpha=0.85, zorder=6)
        ax.text(n_disp_cols / 2 - 0.5, y_sep + 0.15,
                'front ↑ | ↓ back',
                ha='center', va='bottom', fontsize=4.5,
                color='#E53935', fontweight='bold',
                bbox=dict(fc='white', alpha=0.7, pad=1, ec='none'))

    # ── 축 설정 ──────────────────────────────────────────────────
    ax.set_xlim(-0.55, n_disp_cols - 0.45)
    ax.set_ylim(-0.55, n_rows - 0.45)
    ax.set_aspect('equal')

    # x축: 좌석 열 레이블만
    seat_cols_ordered = [c for c in info['display_cols'] if c != 'AISLE']
    ax.set_xticks([col_to_x[c] for c in seat_cols_ordered])
    ax.set_xticklabels(seat_cols_ordered, fontsize=4.5)
    ax.tick_params(axis='x', pad=1, length=2)

    # y축: 행 번호 (적당한 간격)
    step = max(1, n_rows // 8)
    shown = display_rows[::step]
    ax.set_yticks([row_to_y[r] for r in shown])
    ax.set_yticklabels([str(r) for r in shown], fontsize=4.5)
    ax.tick_params(axis='y', pad=1, length=2)

    ax.set_title(f't = {tick}', fontsize=7, pad=2)

    # 통로 레이블
    for ax_x in aisle_to_x.values():
        ax.text(ax_x, n_rows - 0.45, 'aisle',
                ha='center', va='bottom', fontsize=4,
                color='#37474F', rotation=90, style='italic')

    # 범례
    if show_legend:
        items = [mpatches.Patch(fc=_SEAT[s], ec='#999', label=s)
                 for s in ['empty', 'walking', 'stowing', 'seating', 'seated']]
        items.append(mpatches.Patch(fc=_AISLE_EMPTY, ec='#AAA', label='aisle'))
        ax.legend(handles=items, loc='lower right', fontsize=4.5,
                  framealpha=0.9, ncol=1, handlelength=1.0,
                  handleheight=0.8, borderpad=0.5)


# ── PNG 저장 (2×3 그리드) ─────────────────────────────────────────
def save_snapshots(
    recorder:      BoardingRecorder,
    aircraft_name: str,
    strategy_name: str,
    capture_every: int,
    n_frames:      int = 6,
    out_dir:       str = config.RESULTS_DIR,
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    airplane  = recorder.airplane
    snapshots = recorder.snapshots
    info      = _get_display_info(airplane)

    n_disp_cols = len(info['display_cols'])
    n_disp_rows = len(info['display_rows'])
    indices     = np.linspace(0, len(snapshots) - 1, n_frames, dtype=int)

    # 셀 크기 자동 조정
    cell_in  = max(0.11, min(0.20, 3.5 / n_disp_cols))
    frame_w  = n_disp_cols * cell_in + 0.6
    frame_h  = n_disp_rows * cell_in + 0.7

    cols_sub = min(3, n_frames)
    rows_sub = (n_frames + cols_sub - 1) // cols_sub
    fig, axes = plt.subplots(
        rows_sub, cols_sub,
        figsize=(frame_w * cols_sub + 0.2, frame_h * rows_sub + 0.4),
        gridspec_kw={'wspace': 0.10, 'hspace': 0.30},
    )
    fig.suptitle(
        f'{aircraft_name}  —  {strategy_name}  (Boarding Progress)',
        fontsize=9, fontweight='bold', y=1.01,
    )

    flat: list[matplotlib.axes.Axes] = list(np.array(axes).flatten())
    for i, frame_idx in enumerate(indices):
        tick = int(frame_idx) * capture_every
        _render_frame(flat[i], snapshots[frame_idx], airplane,
                      info, tick, show_legend=(i == len(indices) - 1))
    for j in range(len(indices), len(flat)):
        flat[j].set_visible(False)

    ts   = datetime.now().strftime('%H%M%S')
    path = os.path.join(
        out_dir,
        f'boarding_snapshots_{aircraft_name}_{strategy_name}_{ts}.png',
    )
    fig.savefig(path, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print(f'  저장: {path}')
    return path


# ── GIF 저장 ─────────────────────────────────────────────────────
def save_gif(
    recorder:      BoardingRecorder,
    aircraft_name: str,
    strategy_name: str,
    capture_every: int,
    out_dir: str = config.RESULTS_DIR,
    fps:     int = 8,
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    airplane  = recorder.airplane
    snapshots = recorder.snapshots
    info      = _get_display_info(airplane)

    n_disp_cols = len(info['display_cols'])
    n_disp_rows = len(info['display_rows'])

    cell_in = max(0.14, min(0.22, 4.0 / n_disp_cols))
    fw = max(4, n_disp_cols * cell_in + 1.0)
    fh = max(5, n_disp_rows * cell_in + 1.2)

    fig, ax = plt.subplots(figsize=(fw, fh))
    fig.suptitle(f'{aircraft_name} — {strategy_name}', fontsize=9, fontweight='bold')

    def update(frame_idx: int) -> list[mpatches.Patch]:  # type: ignore[return]
        _render_frame(ax, snapshots[frame_idx], airplane,
                      info, frame_idx * capture_every, show_legend=True)
        return []

    ani = animation.FuncAnimation(fig, update, frames=len(snapshots),
                                   interval=1000 // fps, repeat=False)
    ts   = datetime.now().strftime('%H%M%S')
    path = os.path.join(out_dir,
                        f'boarding_{aircraft_name}_{strategy_name}_{ts}.gif')
    ani.save(path, writer='pillow', fps=fps)
    plt.close(fig)
    print(f'  저장: {path}')
    return path


# ── CLI ──────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description='탑승 격자 시각화')
    parser.add_argument('--aircraft', '-a', choices=list(AIRCRAFT.keys()),
                        default='narrow_body')
    parser.add_argument('--strategy', '-s', choices=list(STRATEGIES.keys()),
                        default='BySeat')
    parser.add_argument('--format',   choices=['gif', 'png'], default='png')
    parser.add_argument('--frames',   type=int, default=6)
    parser.add_argument('--interval', type=int, default=20)
    parser.add_argument('--seed',     type=int, default=config.RANDOM_SEED)
    args = parser.parse_args()

    print(f'\n  기종: {args.aircraft}  전략: {args.strategy}  형식: {args.format}')
    airplane = get_aircraft(args.aircraft)
    print('  시뮬레이션 실행 중...')
    recorder = run_with_recording(airplane, args.strategy,
                                   capture_every=args.interval, seed=args.seed)
    print(f'  스냅샷 {len(recorder.snapshots)}개 수집 완료')

    if args.format == 'gif':
        save_gif(recorder, args.aircraft, args.strategy, args.interval)
    else:
        save_snapshots(recorder, args.aircraft, args.strategy,
                       args.interval, n_frames=args.frames)


if __name__ == '__main__':
    main()