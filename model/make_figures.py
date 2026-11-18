#!/usr/bin/env python3
"""Figures for the revision of 2026-11-14, drawn from the model (dcs_model.py, dcs_revision_tables.py).

Needs matplotlib. Usage:  python make_figures.py [output_dir]      (default: ../figures)
Writes:
  fig1_pool-budget_2026-11-14.png        pool budget against fixed targets, both comparators
  fig2_replica-efficiency_2026-11-14.png what m replicas are worth: law, 150M experiment, full count
  fig3_single-run_2026-11-14.png         single-run usable compute against task requirements
  fig4_mc-crossover_2026-11-14.png       Monte-Carlo crossing year on both comparators
Colours: three categorical slots in fixed order (blue, orange, aqua), checked for colour-vision
separation; identity is never carried by colour alone (line style, marker, direct label).
"""
import math, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dcs_model import SCEN, members, T90, TF, N_REF
from dcs_revision_tables import (E, E_NOQ, HW, q_law, c_eq, EXP, mc_two_comparators)

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "figures")
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID, REF = "#1d1b18", "#6b665e", "#e4e0d8", "#8d877c"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
                     "savefig.dpi": 200, "figure.dpi": 100, "font.family": "DejaVu Sans"})
NAMES = ("conservative", "moderate", "optimistic")
unit = E_NOQ["moderate"] * TF * T90                       # FLOP per fully counted device, 90 days, moderate

def save(fig, name):
    path = os.path.join(OUT, name); fig.savefig(path, bbox_inches="tight", facecolor="white"); plt.close(fig); print("wrote", path)

# ---- Figure 1: pool budget against fixed targets ------------------------------------------
def fig1():
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    ts = [i / 20 for i in range(0, 201)]
    for k, c in zip(NAMES, (BLUE, ORANGE, AQUA)):
        era = [members(t, SCEN[k]["M5"]) * E[k] * TF * T90 for t in ts]
        phy = [x * HW ** t for x, t in zip(era, ts)]
        ax.plot(ts, phy, color=c, lw=2, label=k.capitalize())
        ax.plot(ts, era, color=c, lw=1.4, ls=(0, (4, 3)))
        ax.annotate(k.capitalize(), (10, phy[-1]), xytext=(4, 0), textcoords="offset points", va="center", color=INK, fontsize=9)
    for y, lab in ((7.2e23, "Llama-3-8B-class budget"), (1e25, r"$10^{25}$ FLOP"), (3.8e25, "Llama 3 405B run")):
        ax.axhline(y, color=REF, lw=1, ls=":")
        ax.annotate(lab, (0.08, y), xytext=(0, 3), textcoords="offset points", color=MUTED, fontsize=8.5)
    ax.plot([], [], color=INK, lw=2, label="physical FLOPs")
    ax.plot([], [], color=INK, lw=1.4, ls=(0, (4, 3)), label="era-normalized")
    ax.set_yscale("log"); ax.set_xlim(0, 10); ax.set_ylim(2e23, 4e28)
    ax.set_xlabel("years from the 10,000-member starting point"); ax.set_ylabel("pool budget, FLOP per 90 days")
    ax.legend(loc="upper left", ncol=2, fontsize=8.5)
    save(fig, "fig1_pool-budget_2026-11-14.png")

# ---- Figure 2: replica efficiency ----------------------------------------------------------
def fig2():
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    ms = [10 ** (i / 40) for i in range(0, 121)]
    ax.axvspan(64, 1000, color="#f1eee8", lw=0)
    ax.annotate("beyond 64: not run", (250, 1.25), ha="center", color=MUTED, fontsize=8.5, style="italic")
    ax.plot(ms, ms, color=REF, lw=1.4, ls=(0, (4, 3)), label="every replica counted in full")
    ax.plot(ms, [m * q_law(m) for m in ms], color=BLUE, lw=2, label=r"law fitted on larger models at $m \leq 8$")
    ks = sorted(EXP); lo = [min(c_eq(p) for p in EXP[k]) for k in ks]; hi = [max(c_eq(p) for p in EXP[k]) for k in ks]
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    ax.errorbar(ks, mid, yerr=[[m - a for m, a in zip(mid, lo)], [b - m for m, b in zip(mid, hi)]], color=ORANGE, lw=2,
                marker="o", ms=7, mec="white", mew=1.2, capsize=3, label="150M experiment, 4 to 64 replicas")
    ax.plot([4, 8], [4 * 0.94, 8 * 0.80], color=AQUA, ls="none", marker="s", ms=7, mec="white", mew=1.2, zorder=5, label="2.4B model, 4 and 8 replicas")
    ax.annotate("about 201 at 1,000", (1000, 1000 * q_law(1000)), xytext=(-6, 9), textcoords="offset points", ha="right", color=INK, fontsize=9)
    ax.annotate("about 5.7 at 64", (64, mid[-1]), xytext=(8, -3), textcoords="offset points", color=INK, fontsize=9)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(1, 1000); ax.set_ylim(1, 1000)
    ax.set_xticks([1, 2, 4, 8, 16, 64, 100, 1000]); ax.set_xticklabels(["1", "2", "4", "8", "16", "64", "100", "1,000"])
    ax.set_yticks([1, 10, 100, 1000]); ax.set_yticklabels(["1", "10", "100", "1,000"])
    ax.set_xlabel("replicas synchronized in one run"); ax.set_ylabel("what they are worth, in single-run replicas")
    ax.legend(loc="upper left", fontsize=8.5)
    save(fig, "fig2_replica-efficiency_2026-11-14.png")

# ---- Figure 3: single-run usable compute against task requirements --------------------------
def fig3():
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ms = [10 ** (i / 40) for i in range(0, 121)]
    ax.axvspan(64, 1000, color="#f1eee8", lw=0)
    ax.plot(ms, [m * q_law(m) * unit for m in ms], color=BLUE, lw=2, label="law")
    ks = sorted(EXP); mid = [sum(c_eq(p) for p in EXP[k]) / 2 for k in ks]
    ax.plot(ks, [v * unit for v in mid], color=ORANGE, lw=2, marker="o", ms=7, mec="white", mew=1.2, label="plateau (150M experiment)")
    ax.plot([64, 1000], [mid[-1] * unit] * 2, color=ORANGE, lw=1.4, ls=(0, (4, 3)), label="plateau, if it persists")
    for y, lab in ((1.8e20, r"$10^{10}$ tokens of continued training, 3B model"), (1.08e21, "3B model from scratch"),
                   (1.8e21, r"$10^{11}$ tokens of continued training, 3B model"), (7.2e23, "Llama-3-8B-class budget"), (1e25, r"$10^{25}$ FLOP")):
        ax.axhline(y, color=REF, lw=1, ls=":")
        ax.annotate(lab, (1.06, y), xytext=(0, 3), textcoords="offset points", color=MUTED, fontsize=8.3)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(1, 1000); ax.set_ylim(8e19, 3e25)
    ax.set_xticks([1, 2, 4, 8, 16, 64, 100, 1000]); ax.set_xticklabels(["1", "2", "4", "8", "16", "64", "100", "1,000"])
    ax.set_xlabel("single-device replicas in one run (moderate scenario)"); ax.set_ylabel("single-run usable compute, FLOP per 90 days")
    ax.legend(loc="center right", fontsize=8.5, bbox_to_anchor=(1.0, 0.62))
    save(fig, "fig3_single-run_2026-11-14.png")

# ---- Figure 4: Monte-Carlo crossing year on both comparators --------------------------------
def fig4(n=200_000):
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    def cdf(xs):
        xs = sorted(xs); step = max(1, len(xs) // 400)
        return xs[::step], [i / len(xs) for i in range(0, len(xs), step)]
    _, te, tp, _ = mc_two_comparators(n=n)
    _, te2, tp2, _ = mc_two_comparators(n=n, eta_local_range=(0.186, 0.242), r_scale=11 / 6)
    for xs, c, ls, lw, lab in ((tp, BLUE, "-", 2, "physically fixed cluster, as sampled"), (tp2, BLUE, (0, (4, 3)), 1.6, "physically fixed, measured inputs"),
                               (te, ORANGE, "-", 2, "cluster refreshed each year, as sampled"), (te2, ORANGE, (0, (4, 3)), 1.6, "refreshed, measured inputs")):
        x, y = cdf(xs); ax.plot(x + [max(xs), 14.0], y + [1.0, 1.0], color=c, ls=ls, lw=lw, label=lab)
    ax.set_xlim(2, 14); ax.set_ylim(0, 1.0)
    ax.set_xlabel("year in which the pool budget matches a 16,384-H100 cluster"); ax.set_ylabel("share of draws that have crossed")
    ax.legend(loc="lower right", fontsize=8.5)
    save(fig, "fig4_mc-crossover_2026-11-14.png")

if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()
