#!/usr/bin/env python3
"""Distributed Compute Sufficiency -- the tables re-issued for the revision of 2026-11-14.

Computes, from the same model as dcs_model.py, the quantities the revision needs:
  A. the fixed-cluster and fixed-budget crossings two ways (era-normalized, as the draft
     prints them; and physical, where the pool's hardware improves and the target does not)
  B. Table 15's pool rows in physical FLOPs
  C. single-run usable compute with a replica-efficiency factor in place of a replica cap
  D. Table 14b in tokens processed and in single-run-equivalent tokens; from-scratch lines
  E. a measured-consumer column (local utilization 0.186-0.242; current-generation chip ratio)
  F. the size of the double count of communication in the local-utilization anchor
  G. the single-node memory ceiling at 128 GB and 512 GB
  H. communication efficiency by tokens processed per device between synchronizations
  I. the Monte-Carlo of Section 6.6 on both comparators (same draws; --quick uses 20,000)
Nothing here changes dcs_model.py or its 62 checks. Pure standard library.

Usage:  python3 dcs_revision_tables.py
"""
import math, sys
from dcs_model import (SCEN, e_member, r_eq, members, t_reach, T90, TF, N_REF, ETA_LOCAL,
                       ETA_DC, P_H100, M0, RAMP, G_M)
from dcs_model import monte_carlo, pct, src

HW = 1.35                          # per-year improvement of hardware throughput (Section 5.3, [11])
BETA_OVER_ALPHA = 0.0116 / 0.05    # exponent of the replica law pushed through the compute map (Section 3.3.2)
NAMES = ("conservative", "moderate", "optimistic")
out, CHECKS = [], []
w = out.append

def check(label, got, want, tol):
    CHECKS.append((label, got, want, abs(got - want) <= tol * abs(want)))

def t_phys(target_members, M5):
    """First year at which members(t) * HW**t reaches target_members (the pool's hardware
    improves at HW per year; the target is a fixed physical quantity)."""
    if target_members <= M0:
        return 0.0
    t1 = math.log(target_members / M0) / (math.log(M5 / M0) / RAMP + math.log(HW))
    if t1 <= RAMP:
        return t1
    return RAMP + math.log(target_members / (M5 * HW ** RAMP)) / math.log(G_M * HW)

def q_law(m):
    """Replica-efficiency factor from the draft's own law: q = m ** -(beta/alpha)."""
    return m ** -BETA_OVER_ALPHA

# single-model compute multiples reached in the one experiment that went to 64 replicas
# (ref [3], Table 3, 150M model, H = 500; i.i.d. / non-i.i.d.), by interpolation between the
# single-model points 1x -> 16.23 and 8x -> 14.72 perplexity (ref [3], Table 2)
PPL1, PPL8 = 16.23, 14.72
EXP = {4: (15.23, 15.18), 8: (15.08, 15.02), 16: (15.02, 14.91), 64: (14.95, 14.96)}
A_LOCAL = math.log(math.log(PPL1) / math.log(PPL8)) / math.log(8)
def c_eq(ppl):
    return (math.log(ppl) / math.log(PPL1)) ** (-1 / A_LOCAL)

def mc_two_comparators(n=200_000, seed=20260605, eta_local_range=(0.30, 0.40), r_scale=1.0):
    """The draws of Section 6.6, with the crossing year on both comparators for each draw."""
    rows, ts, reqs = monte_carlo(n=n, seed=seed, eta_local_range=eta_local_range, r_scale=r_scale)
    tp = [t_phys(Rq * N_REF, math.exp(row[0])) for row, Rq in zip(rows, reqs)]
    return rows, ts, tp, reqs

E = {k: e_member(v["delta"], v["P"], ETA_LOCAL, v["eta_coop"], v["q"]) for k, v in SCEN.items()}
E_NOQ = {k: E[k] / SCEN[k]["q"] for k in SCEN}          # per-member TFLOPS before any quality factor
R = {k: r_eq(E[k]) for k in SCEN}

def main():
    w("DISTRIBUTED COMPUTE SUFFICIENCY -- tables re-issued for the revision (2026-11-14)")

    # ---- A. crossings two ways ----------------------------------------------------------
    w("\nA. Crossing years, two comparators (conservative / moderate / optimistic)")
    w("   era-normalized = the target is restated on each year's hardware (as the draft prints it);")
    w("   physical       = the pool's hardware improves 1.35x per year, the target does not.")
    rows = [("10^25 FLOP in 90 days", "flop", 1e25), ("7.2e23 FLOP (Llama-3-8B-class budget)", "flop", 7.2e23),
            ("fixed 2,000 H100 cluster", "gpu", 2000), ("3.8e25 FLOP (Llama 3 405B budget)", "flop", 3.8e25),
            ("fixed 16,384 H100 cluster", "gpu", N_REF)]
    for label, kind, val in rows:
        need = [val / (E[k] * TF * T90) if kind == "flop" else R[k] * val for k in NAMES]
        era = [t_reach(n, SCEN[k]["M5"]) for n, k in zip(need, NAMES)]
        phy = [t_phys(n, SCEN[k]["M5"]) for n, k in zip(need, NAMES)]
        w(f"   {label:40s} members at year-0 hardware {need[0]/1e3:7.1f}K /{need[1]/1e3:7.1f}K /{need[2]/1e3:7.1f}K")
        w(f"   {'':40s} era-normalized  {era[0]:5.2f} / {era[1]:5.2f} / {era[2]:5.2f}    physical  {phy[0]:5.2f} / {phy[1]:5.2f} / {phy[2]:5.2f}")
        if kind == "gpu" and val == N_REF:
            for got, want in zip(phy, (4.19, 2.69, 2.20)):
                check("physical crossing, 16,384 H100", got, want, 0.005)
            for got, want in zip(era, (9.49, 3.45, 2.73)):
                check("era-normalized crossing, 16,384 H100", got, want, 0.005)

    # ---- B. Table 15 in physical FLOPs ---------------------------------------------------
    w("\nB. Pool total, one 90-day period at year 5 (FLOP): era-normalized (draft) and physical (x 1.35^5 = %.3f)" % HW ** 5)
    for k in NAMES:
        c = SCEN[k]["M5"] * E[k] * TF * T90
        w(f"   {k:13s} {c:.2e}   physical {c * HW ** 5:.2e}   (physical / 3.8e25 = {c * HW ** 5 / 3.8e25:.1f}x)")

    # ---- C. single-run usable compute with the replica-efficiency factor -----------------
    w("\nC. Replica efficiency: what m replicas are worth in single-run replicas")
    w(f"   local exponent between the two single-model points of ref [3]: {A_LOCAL:.4f}")
    w("   replicas   law q=m^-0.23   effective (law)   experiment [3]: effective (iid / non-iid)   q (iid / non-iid)")
    for m in (2, 4, 8, 16, 20, 64, 100, 1000):
        ex = ""
        if m in EXP:
            a, b = (c_eq(p) for p in EXP[m])
            ex = f"{a:5.2f} / {b:5.2f}                         {a/m:5.3f} / {b/m:5.3f}"
        w(f"   {m:>6}     {q_law(m):6.3f}        {m * q_law(m):7.1f}           {ex}")
    check("experiment q at 64 replicas (iid)", c_eq(14.95) / 64, 0.089, 0.02)
    check("law q at 100 replicas", q_law(100), 0.34, 0.03)
    w("\n   Single-run usable compute, 90 days, FLOP (cons / mod / opt): no quality factor | with the law's q(m)")
    w("   replicas x devices   members   no factor                          with q(m)                          days to 7.2e23 | 1e25 (mod, with q)")
    for m, s in ((8, 1), (16, 1), (20, 1), (64, 1), (100, 1), (1000, 1), (100, 8), (1000, 8)):
        raw = [m * s * E_NOQ[k] * TF * T90 for k in NAMES]
        eff = [x * q_law(m) for x in raw]
        rate = eff[1] / 90.0
        w(f"   {m:>5} x {s}          {m*s:>6}    {raw[0]:.1e} / {raw[1]:.1e} / {raw[2]:.1e}      {eff[0]:.1e} / {eff[1]:.1e} / {eff[2]:.1e}      {7.2e23/rate:>10,.0f} | {1e25/rate:>12,.0f}")
    w("   With the experiment's plateau (about 5.7 effective replicas at 16-64, 150M model), moderate, single devices:")
    plateau = 5.7 * E_NOQ["moderate"] * TF * T90
    w(f"     any m from 16 to 64: about {plateau:.1e} FLOP per 90 days")

    # ---- D. Table 14b ---------------------------------------------------------------------
    w("\nD. Continued training in one 90-day run (moderate): tokens processed, and their single-run equivalent with q(m)")
    for m in (8, 20, 64, 100, 1000):
        raw = m * E_NOQ["moderate"] * TF * T90
        w(f"   {m:>5} x 1   3B model: {raw/(6*3e9):.3g} processed, {raw*q_law(m)/(6*3e9):.3g} equivalent   5B model: {raw/(6*5e9):.3g} processed, {raw*q_law(m)/(6*5e9):.3g} equivalent")
    check("tokens processed, 20 x 1, 3B", 20 * E_NOQ["moderate"] * TF * T90 / (6 * 3e9), 1.53e11, 0.01)
    w("   From-scratch budgets: 20 tokens per parameter -> 3B: %.3g FLOP; 5B: %.3g FLOP.  The draft's 15-30T-token target -> 3B on 15T: %.2g; 5B on 30T: %.2g" %
      (6 * 3e9 * 20 * 3e9, 6 * 5e9 * 20 * 5e9, 6 * 3e9 * 15e12, 6 * 5e9 * 30e12))
    check("3B from scratch at 20 tokens/parameter", 6 * 3e9 * 20 * 3e9, 1.08e21, 0.001)
    check("5B from scratch at 20 tokens/parameter", 6 * 5e9 * 20 * 5e9, 3.0e21, 0.001)

    # ---- E. measured-consumer column -------------------------------------------------------
    ratio_now = (2250 / 209.5) / (989 / 165.2)      # B200 / RTX 5090 against H100 / RTX 4090 (Table 3)
    w("\nE. Measured consumer utilization (0.242 and 0.186, ref [61]) in place of 0.38; and the current-generation chip ratio (x %.3f)" % ratio_now)
    w("   scenario        eta_local   e_member (TFLOPS)   R_eq    members = 16,384 H100   members for 1e25/90d   era yr  physical yr   | R_eq at current chips")
    for eta in (ETA_LOCAL, 0.242, 0.186):
        for k in NAMES:
            v = SCEN[k]; e = e_member(v["delta"], v["P"], eta, v["eta_coop"], v["q"]); r = r_eq(e)
            w(f"   {k:13s}   {eta:5.3f}      {e:6.2f}            {r:6.1f}     {r*N_REF/1e3:8.0f}K           {1e25/(e*TF*T90)/1e3:7.0f}K         {t_reach(r*N_REF, v['M5']):5.2f}    {t_phys(r*N_REF, v['M5']):5.2f}         | {r*ratio_now:6.1f}")

    # ---- F. the double count ----------------------------------------------------------------
    w("\nF. Communication counted twice (ref [31], Table 2: 43.3% with no communication; 41.4 / 37.1 / 36.0% with it)")
    for k in NAMES:
        v = SCEN[k]
        a = e_member(v["delta"], v["P"], 0.433, v["eta_coop"], v["q"])          # communication-free local value, eta_coop kept
        b = v["delta"] * v["P"] * ETA_LOCAL * v["q"]                              # 0.38 read as end-to-end, eta_coop dropped
        w(f"   {k:13s} as printed {E[k]:5.2f}   local 0.433 x eta_coop {a:5.2f} (x{a/E[k]:.3f})   0.38 end-to-end, no eta_coop {b:5.2f} (x{b/E[k]:.3f})")

    # ---- G. memory ceiling --------------------------------------------------------------------
    w("\nG. Single-node model size at 10-12 bytes per parameter (8-bit optimizers, Section 3.5)")
    for gb in (24, 32, 128, 512):
        w(f"   {gb:>4} GB: {gb/12:5.1f}B - {gb/10:5.1f}B parameters")

    # ---- H. communication efficiency by tokens per device per round ----------------------------
    w("\nH. eta_coop for one device at effective throughput (165 x 0.38 TFLOPS), 1B parameters, FP16, 58 Mbit/s upload")
    F = 165e12 * 0.38; W = 1e9; B = 58e6 / 8
    def eta(b, H, c=1.0):
        tc = 6 * W * b / F; tm = 2 * 2.0 * W / B / c
        return tc / (tc + tm / H)
    for b in (524288, 131072, 65536, 16384):
        w(f"   batch {b:>7} tokens: H=500 {eta(b,500):.3f}   H=30 {eta(b,30):.3f}   | with 50x compression: H=500 {eta(b,500,50):.3f}   H=30 {eta(b,30,50):.3f}")
    for target in (0.90, 0.93):
        n = (target / (1 - target)) * (2 * 2.0 * F) / (6 * B)
        w(f"   tokens per device between synchronizations needed for eta >= {target}: {n:.3g}")
    check("eta_coop, 16,384-token batch, H=500", eta(16384, 500), 0.587, 0.005)
    check("eta_coop, 16,384-token batch, H=30", eta(16384, 30), 0.079, 0.02)

    # ---- I. Monte-Carlo on both comparators ---------------------------------------------
    n = 20_000 if "--quick" in sys.argv else 200_000
    w(f"\nI. Monte-Carlo, {n:,} draws: crossing year against a 16,384-H100 cluster, refreshed (as Section 6.6) and physically fixed")
    w("   case                               refreshed: median  [5th, 95th]  after ramp | physical: median  [5th, 95th]  mean  after ramp")
    for label, kw in (("as sampled in Section 6.6", {}), ("eta_local ~ U(0.186, 0.242)", dict(eta_local_range=(0.186, 0.242))),
                      ("chip ratio 11 in place of 6", dict(r_scale=11 / 6)), ("both", dict(eta_local_range=(0.186, 0.242), r_scale=11 / 6))):
        rows, ts, tp, reqs = mc_two_comparators(n=n, **kw)
        w(f"   {label:34s} {pct(ts,0.5):5.2f}  [{pct(ts,0.05):.2f}, {pct(ts,0.95):.2f}]  {sum(t > RAMP for t in ts)/len(ts)*100:4.1f}%   |  {pct(tp,0.5):5.2f}  [{pct(tp,0.05):.2f}, {pct(tp,0.95):.2f}]  {sum(tp)/len(tp):.2f}  {sum(t > RAMP for t in tp)/len(tp)*100:4.1f}%")
        if not kw:
            beta, r2 = src(rows, tp); sq = [b * b for b in beta]
            w(f"     physical comparator: R^2 of the linear fit {r2:.3f}; membership share of explained variance {sq[0]/sum(sq)*100:.0f}%")
            if n == 200_000:
                check("MC refreshed median (Section 6.6)", pct(ts, 0.5), 3.9, 0.02)

    w("\nCHECK")
    bad = 0
    for label, got, want, ok in CHECKS:
        bad += not ok
        w(f"  {'OK  ' if ok else 'DIFF'} {label:45s} script {got:.4g}   expected {want:.4g}")
    w(f"\n{len(CHECKS) - bad} of {len(CHECKS)} checks pass; {bad} differ.")
    print("\n".join(out))
    if bad:
        sys.exit(1)

if __name__ == "__main__":
    main()
