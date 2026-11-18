#!/usr/bin/env python3
"""Distributed Compute Sufficiency -- the model as code.

Rebuilt on 2026-11-13 from the equations and tables of the paper draft of 2026-11-01
(paper_v2026-11-01_DRAFT.md): Table 12 (scenarios), Eq. 24, Eq. 28 / Table 13, Table 14,
Table 14a, Eq. 29 / Table 15, Eq. 30-32a / Table 18, Table 20, and the Monte-Carlo of
Section 6.6. Pure standard library; no dependencies. Every printed value of the draft that
this script recomputes is checked at the end and reported as OK or DIFF.

Usage:  python3 dcs_model.py            (prints the report)
        python3 dcs_model.py --quick    (Monte-Carlo with 20,000 draws instead of 200,000)
"""
import math, random, sys

# ---- constants of the draft ------------------------------------------------------------
T90 = 90 * 86400                 # seconds in a 90-day run (Section 5.3)
P_H100 = 989.0                   # TFLOPS, dense BF16 (Section 3.2)
P_4090 = 165.0                   # TFLOPS, dense BF16 (Section 3.2)
ETA_DC = 0.40                    # datacenter MFU (Section 3.1)
ETA_LOCAL = 0.38                 # local MFU, all scenarios (Section 5.1)
M0, RAMP, G_M = 10_000, 5.0, 1.15   # membership seed, ramp length, post-ramp growth (Section 5.1)
N_REF = 16_384                   # the reference cluster (Llama 3 405B)
TF = 1e12                        # one TFLOPS in FLOP/s

SCEN = {                         # Table 12
    "conservative": dict(M5=5e5, g_chips=2.5, eta_coop=0.90, q=0.90, delta=0.3, P=75.0),
    "moderate":     dict(M5=2e6, g_chips=2.0, eta_coop=0.93, q=0.95, delta=0.5, P=100.0),
    "optimistic":   dict(M5=5e6, g_chips=1.5, eta_coop=0.93, q=0.98, delta=0.5, P=125.0),
}

# ---- the model -------------------------------------------------------------------------
def e_member(delta, P, eta_local, eta_coop, q):
    """Eq. 28: effective TFLOPS contributed by one member."""
    if not (0 < delta <= 1 and P > 0 and 0 < eta_local <= 1 and 0 < eta_coop <= 1 and 0 < q <= 1):
        raise ValueError("e_member: delta, eta_local, eta_coop, q must lie in (0, 1] and P must be positive")
    return delta * P * eta_local * eta_coop * q

def r_eq(e, eta_dc=ETA_DC, p_chip=P_H100):
    """Members per H100-equivalent (Table 13)."""
    return p_chip * eta_dc / e

def members(t, M5):
    """Section 5.1: exponential ramp from M0 to M5 at t = RAMP, then G_M per year."""
    if t < 0 or M5 <= 0:
        raise ValueError("members: t must be non-negative and M5 positive")
    if t <= RAMP:
        return M0 * (M5 / M0) ** (t / RAMP)
    return M5 * G_M ** (t - RAMP)

def t_reach(target, M5):
    """Year at which membership first reaches a fixed target (Eq. 32a with g = 1, else Eq. 31)."""
    if target <= M0:
        return 0.0
    if target <= M5:
        return RAMP * math.log(target / M0) / math.log(M5 / M0)
    return RAMP + math.log(target / M5) / math.log(G_M)

def crossover_growing(M5, g, R, n0=N_REF, horizon=40.0, dt=0.001):
    """First year the cooperative reaches a cluster growing at g per year, and the year it
    falls behind again if it does (numerical scan of the full piecewise model, as Table 20).
    A first value of None means no crossover was found within `horizon` years; it does not
    show that none exists later."""
    if not (M5 > 0 and g > 0 and R > 0 and n0 > 0 and horizon > 0 and dt > 0):
        raise ValueError("crossover_growing: all arguments must be positive")
    first = None
    t = 0.0
    while t <= horizon:
        ahead = members(t, M5) >= R * n0 * g ** t
        if ahead and first is None:
            first = t
        if first is not None and not ahead:
            return first, t
        t += dt
    return first, None

# ---- Monte-Carlo (Section 6.6) ---------------------------------------------------------
def tri(rng, a, c, b):
    return rng.triangular(a, b, c)

def monte_carlo(n=200_000, seed=20260605, eta_local_range=(0.30, 0.40), r_scale=1.0):
    rng = random.Random(seed)
    rows, ts, reqs = [], [], []
    for _ in range(n):
        eta_dc = tri(rng, 0.30, 0.40, 0.50)
        delta = rng.uniform(0.30, 0.50)
        P = tri(rng, 75, 100, 125)
        eta_local = rng.uniform(*eta_local_range)
        eta_coop = rng.uniform(0.90, 0.95)
        q = tri(rng, 0.90, 0.95, 0.98)
        lnM5 = rng.uniform(math.log(5e5), math.log(5e6))
        R = r_scale * r_eq(e_member(delta, P, eta_local, eta_coop, q), eta_dc)
        t = t_reach(R * N_REF, math.exp(lnM5))
        rows.append((lnM5, delta, P, eta_dc, eta_local, q, eta_coop))
        ts.append(t); reqs.append(R)
    return rows, ts, reqs

def pct(xs, p):
    s = sorted(xs); k = (len(s) - 1) * p; f = math.floor(k); c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)

def src(rows, ys):
    """Standardized regression coefficients by ordinary least squares (normal equations)."""
    n, k = len(rows), len(rows[0])
    mx = [sum(r[j] for r in rows) / n for j in range(k)]
    sx = [math.sqrt(sum((r[j] - mx[j]) ** 2 for r in rows) / n) for j in range(k)]
    my = sum(ys) / n; sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    A = [[0.0] * k for _ in range(k)]; b = [0.0] * k
    for r, y in zip(rows, ys):
        z = [(r[j] - mx[j]) / sx[j] for j in range(k)]; zy = (y - my) / sy
        for i in range(k):
            b[i] += z[i] * zy
            zi = z[i]; Ai = A[i]
            for j in range(k):
                Ai[j] += zi * z[j]
    for i in range(k):                      # Gaussian elimination
        piv = A[i][i]
        for j in range(i, k): A[i][j] /= piv
        b[i] /= piv
        for r2 in range(k):
            if r2 != i and A[r2][i]:
                f = A[r2][i]
                for j in range(i, k): A[r2][j] -= f * A[i][j]
                b[r2] -= f * b[i]
    beta = b
    # R^2 of the linear model
    ss_res = 0.0
    for r, y in zip(rows, ys):
        z = [(r[j] - mx[j]) / sx[j] for j in range(k)]
        pred = sum(beta[j] * z[j] for j in range(k))
        ss_res += ((y - my) / sy - pred) ** 2
    r2 = 1 - ss_res / n
    return beta, r2

def parity_probability(n=200_000, seed=20260605):
    rng = random.Random(seed + 1)
    hit = sum(1 for _ in range(n) if tri(rng, 1.0, 1.3, 1.8) < rng.uniform(1.10, 1.30))
    return hit / n

# ---- the report ------------------------------------------------------------------------
CHECKS = []
def check(label, got, printed, tol):
    ok = abs(got - printed) <= tol * abs(printed)
    CHECKS.append((label, got, printed, ok))
    return got

def main():
    quick = "--quick" in sys.argv
    # with 20,000 draws the Monte-Carlo statistics carry sampling noise larger than the tolerances
    # set for the 200,000-draw values the draft prints, so --quick prints them without checking them
    mcheck = (lambda label, got, printed, tol: got) if quick else check
    out = []
    w = out.append
    w("DISTRIBUTED COMPUTE SUFFICIENCY -- model report (rebuilt from the 2026-11-01 draft)\n")

    # Eq. 24 example
    e4090 = e_member(0.5, P_4090, ETA_LOCAL, 0.93, 0.95)
    m234 = N_REF * P_H100 * ETA_DC / e4090
    m234_r6 = N_REF * 6 * ETA_DC / (0.5 * ETA_LOCAL * 0.93 * 0.95)
    w("Eq. 24 example (16,384 H100 against RTX-4090-class devices at half duty)")
    w(f"  with R_perf = 6 exactly, as printed: {m234_r6:,.0f} members    with 989/165: {m234:,.0f}")
    check("Eq. 24: 234,000 members", m234_r6, 234_000, 0.005)
    m368 = m234_r6 * ETA_LOCAL / 0.242
    w(f"  at the measured consumer utilization 0.242: {m368:,.0f}")
    check("368,000 at eta_local 0.242", m368, 368_000, 0.005)

    # Table 13
    w("\nTable 13 -- per-member effective compute")
    E, R = {}, {}
    printed13 = {"conservative": (6.9, 57.1), "moderate": (16.8, 23.6), "optimistic": (21.6, 18.3)}
    for k, s in SCEN.items():
        E[k] = e_member(s["delta"], s["P"], ETA_LOCAL, s["eta_coop"], s["q"])
        R[k] = r_eq(E[k])
        w(f"  {k:12s} e_member = {E[k]:.2f} TFLOPS   members per H100-equivalent = {R[k]:.1f}")
        check(f"Table 13 e_member {k}", E[k], printed13[k][0], 0.01)
        check(f"Table 13 R_eq {k}", R[k], printed13[k][1], 0.005)
    m387 = R["moderate"] * N_REF
    w(f"  moderate fleet against 16,384 H100: {m387:,.0f} members")
    check("387,000 at the moderate fleet", m387, 387_000, 0.005)
    check("26 million vs 1.1M H100-equivalents", 1.1e6 * R["moderate"], 26e6, 0.01)

    # Table 14
    w("\nTable 14 -- membership and H100-equivalents by year")
    for t in (1, 2, 3, 4, 5, 7, 10):
        w("  t=%2d  " % t + "   ".join(f"{k[:4]} M={members(t, s['M5']):>10,.0f} N_eq={members(t, s['M5'])/R[k]:>9,.0f}" for k, s in SCEN.items()))
    check("Table 14 moderate N_equiv at t=5", members(5, 2e6) / R["moderate"], 84_700, 0.005)
    check("Table 14 conservative M at t=1", members(1, 5e5), 22_000, 0.01)

    # Table 15
    w("\nTable 15 -- total FLOP of a 90-day run at t = 5 (aggregate)")
    printed15 = {"conservative": 2.7e25, "moderate": 2.6e26, "optimistic": 8.4e26}
    for k, s in SCEN.items():
        c = s["M5"] * E[k] * TF * T90
        w(f"  {k:12s} {c:.2e} FLOP")
        check(f"Table 15 {k}", c, printed15[k], 0.02)

    # Table 18
    w("\nTable 18 -- members required and the year reached")
    targets = [("practical sufficiency, 1e25 FLOP in 90 days", "flop", 1e25, (186e3, 77e3, 59e3), (3.73, 1.92, 1.43)),
               ("Llama-3-8B-class budget, 7.2e23 FLOP", "flop", 7.2e23, (13.4e3, 5.5e3, 4.3e3), None),
               ("fixed 2,000-GPU cluster", "gpu", 2000, (114e3, 47e3, 37e3), (3.11, 1.46, 1.04)),
               ("Llama 3 405B budget, 3.8e25 FLOP", "flop", 3.8e25, (706e3, 291e3, 226e3), (7.46, 3.18, 2.51)),
               ("fixed 16,384-GPU cluster", "gpu", N_REF, (936e3, 386e3, 299e3), (9.49, 3.45, 2.73))]
    for name, kind, val, pm, pt in targets:
        cells = []
        for i, (k, s) in enumerate(SCEN.items()):
            req = val / (E[k] * TF * T90) if kind == "flop" else R[k] * val
            t = t_reach(req, s["M5"])
            cells.append(f"{req:>9,.0f} at t*={t:.2f}")
            check(f"Table 18 members {name} {k}", req, pm[i], 0.015)
            if pt: check(f"Table 18 t* {name} {k}", t, pt[i], 0.006)
        w(f"  {name:45s} " + " | ".join(cells))

    # Table 14a, with the validated envelope added
    w("\nTable 14a -- what ONE 90-day run can use under a replica cap (FLOP; cons / mod / opt)")
    for label, n in (("8 x 1   (validated replica count) [added]", 8), ("20 x 1  (peers in the 72B run) [added]", 20),
                     ("100 x 1", 100), ("1,000 x 1", 1000), ("100 x 8", 800), ("1,000 x 8", 8000)):
        vals = [n * E[k] * TF * T90 for k in SCEN]
        days = 7.2e23 / (n * E["moderate"] * TF * 86400)
        w(f"  {label:44s} " + " / ".join(f"{v:.1e}" for v in vals) + f"   days to 7.2e23 (moderate): {days:,.0f}")
    check("Table 14a 100x1 moderate", 100 * E["moderate"] * TF * T90, 1.3e22, 0.02)
    check("Table 14a 1,000x8 optimistic", 8000 * E["optimistic"] * TF * T90, 1.3e24, 0.04)
    check("Table 14a days to 7.2e23 at 100x1", 7.2e23 / (100 * E["moderate"] * TF * 86400), 5000, 0.03)
    w(f"  members that ONE run would have to synchronize to match the 16,384-H100 cluster (moderate): {m387:,.0f}")
    w("  -> under any replica cap below that, the single-run crossover does not exist, whatever the membership.")

    # Table 20
    w("\nTable 20 -- crossover year against a 16,384-H100 cluster growing at g per year (R_eq moderate)")
    printed20 = {(1.00, 5e5): 4.7, (1.00, 2e6): 3.4, (1.10, 5e5): 9.9, (1.15, 1e6): 4.7, (1.50, 5e6): 4.4, (1.50, 1e7): 3.7}
    for g in (1.00, 1.05, 1.10, 1.15, 1.50, 2.00):
        cells = []
        for M5 in (5e5, 1e6, 2e6, 5e6, 1e7):
            a, b = crossover_growing(M5, g, R["moderate"])
            cells.append("   ---   " if a is None else (f"{a:4.1f}     " if b is None else f"{a:3.1f}-{b:4.1f} "))
            if (g, M5) in printed20 and a is not None:
                check(f"Table 20 g={g} M5={M5:.0e}", a, printed20[(g, M5)], 0.03)
        w(f"  g={g:.2f}  " + " ".join(cells))
    w("  (--- = no crossover within the 40-year scan; not a proof that none occurs later)")
    a, b = crossover_growing(5e6, 1.5, R["moderate"]); check("Table 20 reversion g=1.5 M5=5M", b, 7.0, 0.01)
    a, b = crossover_growing(1e7, 1.5, R["moderate"]); check("Table 20 reversion g=1.5 M5=10M", b, 9.6, 0.01)

    # Monte-Carlo
    n = 20_000 if quick else 200_000
    rows, ts, reqs = monte_carlo(n)
    beta, r2 = src(rows, ts)
    names = ["ln M5", "delta", "P_consumer", "eta_dc", "eta_local", "q", "eta_coop"]
    sq = [b * b for b in beta]; tot = sum(sq)
    w(f"\nMonte-Carlo, Section 6.6 as written ({n:,} draws; fixed seed; standard library RNG, so not the draft's stream)")
    w(f"  crossover year vs fixed 16,384 H100: median {pct(ts,0.5):.2f}  90% interval [{pct(ts,0.05):.2f}, {pct(ts,0.95):.2f}]  mean {sum(ts)/len(ts):.2f}")
    w(f"  R_eq 5th-95th percentile: [{pct(reqs,0.05):.1f}, {pct(reqs,0.95):.1f}]   moderate point value: {R['moderate']:.1f}")
    w(f"  linear-model R^2: {r2:.3f}")
    w("  share of explained variance: " + ", ".join(f"{nm} {100*s/tot:.0f}%" for nm, s in zip(names, sq)))
    w(f"  squared standardized coefficient of ln M5 (share of total variance): {sq[0]:.2f}")
    pp = parity_probability(n)
    w(f"  sustained parity, g_chips ~ Tri(1.0,1.3,1.8) vs g_M ~ U(1.10,1.30): {100*pp:.1f}% of draws")
    mcheck("MC median", pct(ts, 0.5), 3.9, 0.02); mcheck("MC 5th percentile", pct(ts, 0.05), 3.2, 0.02)
    mcheck("MC 95th percentile", pct(ts, 0.95), 5.2, 0.02); mcheck("MC mean", sum(ts) / len(ts), 4.1, 0.02)
    mcheck("MC R^2", r2, 0.84, 0.01); mcheck("MC membership share", sq[0] / tot, 0.81, 0.02)
    mcheck("MC parity probability", pp, 0.18, 0.04)
    mcheck("MC R_eq 5th", pct(reqs, 0.05), 23, 0.03); mcheck("MC R_eq 95th", pct(reqs, 0.95), 48, 0.03)

    # two cases the draft names but did not run (illustrations, not results of the paper)
    w("\nCases the draft names and did not run (same sampler; each changes ONE thing)")
    _, ts2, rq2 = monte_carlo(n, eta_local_range=(0.186, 0.242))
    w(f"  eta_local ~ U(0.186, 0.242), the range measured on a consumer-majority fleet: median {pct(ts2,0.5):.2f}  90% [{pct(ts2,0.05):.2f}, {pct(ts2,0.95):.2f}]  R_eq [{pct(rq2,0.05):.0f}, {pct(rq2,0.95):.0f}]")
    _, ts3, rq3 = monte_carlo(n, r_scale=11.0 / 6.0)
    w(f"  chip ratio 11 instead of 6 (current-generation datacenter chip vs consumer flagship): median {pct(ts3,0.5):.2f}  90% [{pct(ts3,0.05):.2f}, {pct(ts3,0.95):.2f}]  R_eq [{pct(rq3,0.05):.0f}, {pct(rq3,0.95):.0f}]")
    _, ts4, rq4 = monte_carlo(n, eta_local_range=(0.186, 0.242), r_scale=11.0 / 6.0)
    w(f"  both together: median {pct(ts4,0.5):.2f}  90% [{pct(ts4,0.05):.2f}, {pct(ts4,0.95):.2f}]  R_eq [{pct(rq4,0.05):.0f}, {pct(rq4,0.95):.0f}]")
    for nm, tt in (("as written", ts), ("measured utilization", ts2), ("chip ratio 11", ts3), ("both", ts4)):
        w(f"    share of draws crossing after the five-year ramp ({nm}): {100*sum(1 for t in tt if t > RAMP)/len(tt):.0f}%")

    # the adaptation table (C = 6ND, the draft's convention)
    w("\nWhat a capped run buys for continuing the training of an existing model (D = C / 6N; moderate; 90 days)")
    for label, m in (("8 x 1", 8), ("20 x 1", 20), ("100 x 1", 100), ("1,000 x 1", 1000)):
        C = m * E["moderate"] * TF * T90
        w(f"  {label:10s} usable {C:.2e} FLOP   3B model: {C/(6*3e9):.2e} tokens   5B model: {C/(6*5e9):.2e} tokens")
    w(f"  from-scratch budgets in the draft: 3B on 15T tokens = {6*3e9*15e12:.1e} FLOP; 5B on 30T tokens = {6*5e9*30e12:.1e} FLOP")

    w("\nCHECK against the draft's printed values")
    if quick:
        w("  (--quick: the nine Monte-Carlo values above are printed, not checked; run without --quick to check them)")
    bad = 0
    for label, got, printed, ok in CHECKS:
        if not ok: bad += 1
        w(f"  {'OK  ' if ok else 'DIFF'} {label:55s} script {got:.4g}   printed {printed:.4g}")
    w(f"\n{len(CHECKS) - bad} of {len(CHECKS)} printed values reproduced within tolerance; {bad} differ.")
    print("\n".join(out))
    if bad:
        sys.exit(1)        # a printed value that no longer reproduces fails the run

if __name__ == "__main__":
    main()
