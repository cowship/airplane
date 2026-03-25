# visualization/results.py
"""
Monte Carlo 결과 시각화.

생성 파일:
  results/{prefix}_histogram_{method}.png  — 전략별 분포
  results/{prefix}_boxplot.png             — 전략 비교 박스플롯
"""
from __future__ import annotations
from typing import Optional
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

try:
    plt.rcParams["font.family"] = "DejaVu Sans"
except Exception:
    pass

# 전략별 고정 색상
_COLORS = {
    "Random":      "#5B9BD5",
    "BackToFront": "#ED7D31",
    "FrontToBack": "#A5A5A5",
    "BySection":   "#FFC000",
    "BySeat":      "#70AD47",
    "Steffen":     "#9B2D9B",
}
_DEFAULT_COLOR = "#4472C4"


def _color(name: str) -> str:
    return _COLORS.get(name, _DEFAULT_COLOR)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── 히스토그램 ────────────────────────────────────────────────

def plot_histogram(
    ticks: np.ndarray,
    method_name: str,
    prefix: str = "mc",
    out_dir: Optional[str] = None,
) -> Optional[str]:
    """
    단일 전략의 소요 시간 분포 히스토그램 저장.
    ticks 가 비어있으면 None 반환.
    """
    if len(ticks) == 0:
        print(f"  ⚠️  [{method_name}] 데이터 없음 — 히스토그램 생략")
        return None

    out_dir = out_dir or config.RESULTS_DIR
    _ensure_dir(out_dir)

    secs  = ticks * config.TICK_DURATION
    mean  = float(np.mean(secs))
    p5    = float(np.percentile(secs, 5))
    p95   = float(np.percentile(secs, 95))
    color = _color(method_name)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(secs, bins=40, density=True, color=color, alpha=0.75, edgecolor="white")
    ax.axvline(mean, color="crimson",   lw=2, linestyle="--",
               label=f"Mean  {mean:.0f}s")
    ax.axvline(p5,   color="steelblue", lw=1.5, linestyle=":",
               label=f"P5    {p5:.0f}s")
    ax.axvline(p95,  color="steelblue", lw=1.5, linestyle=":",
               label=f"P95   {p95:.0f}s")

    ax.set_title(
        f"{method_name}  —  Boarding Time Distribution  (n={len(ticks)})",
        fontsize=13, fontweight="bold",
    )
    ax.set_xlabel("Boarding Time (s)", fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"{prefix}_hist_{method_name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ── 박스플롯 ────────────────────────────────────────────────

def plot_boxplot(
    all_results: dict[str, np.ndarray],
    prefix: str = "mc",
    out_dir: Optional[str] = None,
) -> Optional[str]:
    """
    여러 전략의 소요 시간 비교 박스플롯 저장.
    유효 데이터가 하나도 없으면 None 반환.
    """
    # 비어있는 배열은 제외
    valid = {k: v for k, v in all_results.items() if len(v) > 0}
    if not valid:
        print("  ⚠️  유효한 데이터가 없어 박스플롯을 생성할 수 없습니다.")
        return None

    out_dir = out_dir or config.RESULTS_DIR
    _ensure_dir(out_dir)

    names  = list(valid.keys())
    data   = [valid[n] * config.TICK_DURATION for n in names]
    colors = [_color(n) for n in names]

    fig, ax = plt.subplots(figsize=(max(8, len(names) * 1.6), 6))

    bp = ax.boxplot(
        data,
        tick_labels=names,
        patch_artist=True,
        showfliers=False,
        medianprops=dict(color="black", linewidth=2),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # 평균값 마커
    for i, d in enumerate(data, start=1):
        if len(d) > 0:
            ax.scatter(i, np.mean(d), marker="D", s=50,
                       color="crimson", zorder=5, label="Mean" if i == 1 else "")

    skipped = set(all_results) - set(valid)
    title_suffix = f"  (⚠️ 제외됨: {', '.join(skipped)})" if skipped else ""
    ax.set_title(f"Boarding Methods Comparison{title_suffix}",
                 fontsize=14, fontweight="bold")
    ax.set_ylabel("Boarding Time (s)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%ds"))
    ax.tick_params(axis="x", rotation=15)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"{prefix}_boxplot.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ── 통합 저장 ────────────────────────────────────────────────

def save_all(
    all_results: dict[str, np.ndarray],
    prefix: str = "mc",
    out_dir: Optional[str] = None,
) -> list[str]:
    """히스토그램(전략별) + 박스플롯을 한번에 저장."""
    saved = []
    for name, ticks in all_results.items():
        p = plot_histogram(ticks, name, prefix=prefix, out_dir=out_dir)
        if p:
            saved.append(p)
            print(f"  저장: {p}")

    p = plot_boxplot(all_results, prefix=prefix, out_dir=out_dir)
    if p:
        saved.append(p)
        print(f"  저장: {p}")

    return saved