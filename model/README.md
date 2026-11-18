# The DCS model as code (rebuilt 2026-11-13 from the paper draft of 2026-11-01)

`dcs_model.py` uses the Python standard library only. `python3 dcs_model.py` prints every table it recomputes (Eq. 24; Tables 13, 14, 14a, 15, 18, 20; the Monte-Carlo of Section 6.6) and checks 62 values printed in the draft. `python3 dcs_model.py --quick` runs the Monte-Carlo with 20,000 draws. `REPORT_2026-11-13.txt` is the full run (200,000 draws, about two seconds): 62 of 62 reproduce.

What it adds to the 2026-11-01 draft, each computed and none decided:
- Table 14a's two rows at the validated envelope (8 replicas; 20 peers): about 1e21 and 2.6e21 FLOP per 90 days in the moderate case.
- Where the moderate scenario sits in the Monte-Carlo's own distribution: R_eq at the 7th percentile, the crossover year at the 20th (the 2026-11-01 draft says "at the median").
- Three cases with the same sampler: the measured consumer-majority utilization (median 4.4 years, 90% interval 3.6 to 8.7); the current-generation chip ratio of 11 in place of 6 (4.5; 3.7 to 9.5); both (5.1; 4.1 to 13.0). The draft's 3-to-5-year band holds only inside its sampled ranges. Which inputs to sample is the author's decision.
- Table 14b: tokens of continued training that a capped run pays for (D = C / 6N).

Not in it: the loss projections (Tables 16, 17), the communication-efficiency surface (Table 22), the figures. The random stream is Python's, not the one behind the August figures; the statistics agree to two figures.

Intended as the first content of the public repository (code under a permissive licence, as with the author's earlier release).

## Added 2026-11-14
- `dcs_revision_tables.py` — the quantities the revision needed, computed from the same model: crossings on both comparators; the pool total in physical FLOPs; the replica-efficiency factor (the fitted law and the 2023 experiment's plateau) and single-run usable compute; continued training in tokens processed and their single-run equivalent; a measured-consumer column; the size of the double count; the single-node memory ceiling; communication efficiency by tokens per device between synchronizations; and the Monte-Carlo on both comparators. `python3 dcs_revision_tables.py` (14 checks; exit status 1 if one fails). Output: `REPORT_revision-tables_2026-11-14.txt`.
- `make_figures.py` — the paper's four figures. Needs matplotlib. `python make_figures.py [output_dir]`.
- `dcs_model.py` — unchanged in what it computes; a failed check now ends the run with status 1; `--quick` prints the Monte-Carlo values without checking them; three functions reject inputs outside their domains. `REPORT_2026-11-14.txt` is the full run (62 of 62).
