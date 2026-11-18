# Distributed Compute Sufficiency

*Aggregate Abundance and Single-Run Scarcity in Volunteer AI Training*

A working paper by R. Insite (version 6.0, November 2026), with the model as code and an interactive explorer.

- **Explorer:** [aj-fyc.github.io/distributed-compute-sufficiency](https://aj-fyc.github.io/distributed-compute-sufficiency/): choose how many home machines and copies one training run uses, and see what it can train.
- **Paper:** [PDF](paper/distributed-compute-sufficiency-working-paper.pdf) · [Word](paper/distributed-compute-sufficiency-working-paper.docx) · [Markdown](paper/distributed-compute-sufficiency-working-paper.md)
- **Essay:** *A Frontier Lab Without Walls*, on [R. Insite's Substack](https://rinsite.substack.com/)

## The question

Can volunteers who pool consumer GPUs train AI models that matter?

## What the paper finds

The paper keeps three quantities apart: the compute a pool holds, the compute one training run can use, and parity with a datacenter.

- **The pool holds a lot.** About 234,000 RTX-4090-class GPUs at half duty match the effective compute of the 16,384-H100 cluster that trained Llama 3 (about 368,000 at the utilization measured on a consumer-majority fleet).
- **One run can use far less.** At the replica counts that have been run (8 to 64), a 90-day run on single devices uses about 10^21 FLOP: enough to continue training a small existing model, or to train a 3-billion-parameter model from scratch on about fifteen devices (about four months if the gain from added replicas plateaus).
- **Keeping pace with the largest labs is unlikely.** Parity with a growing frontier holds in 18% of Monte-Carlo draws and needs datacenter growth below about 15% a year.
- **The open question** is how much each added replica contributes. One 2023 experiment shows a plateau by 64 replicas; a law fitted on larger models does not; nothing has been measured beyond 64.

## Test this

Train a model of one to three billion parameters with DiLoCo-class synchronization at 16, 64 and 256 replicas, one consumer GPU each, and measure what each run is worth in single-run replicas. About 6 at 256 supports the plateau; about 70 supports the fitted law. If you run it, please open an issue with the numbers.

## Reproduce

```
cd model
python3 dcs_model.py              # the paper's tables and the Monte-Carlo; checks 62 printed values
python3 dcs_model.py --quick      # the same with 20,000 draws
python3 dcs_revision_tables.py    # single-run usable compute, both comparators; 14 checks
python3 make_figures.py ../paper/figures   # the four figures (needs matplotlib)
```

The model scripts use the Python standard library only. Last run, 18 November 2026: 62 of 62 printed values reproduce; 14 of 14 checks pass. Full outputs are in `model/REPORT_2026-11-16.txt` and `model/REPORT_revision-tables_2026-11-14.txt`.

To build the PDF and the Word file (needs pandoc and xelatex): `python3 paper/build_pdf.py paper/distributed-compute-sufficiency-working-paper.md --docx`

## Limits

This is a working paper. It has not been peer-reviewed; AI models have reviewed it, and no human expert has yet. Its central open quantity rests on one 2023 experiment and one fitted law. Data curation, Byzantine robustness, ownership and governance are outside the model.

## How it was made

The research question and the cooperative design are the author's. The paper, the model and this repository were developed with Claude, under the author's direction and review.

## Citing

See `CITATION.cff`. A DOI will be added here when the Zenodo record is published.

## Licences

Code (`model/`, `paper/build_pdf.py`, `index.html`): MIT, in `LICENSE`. The paper, the essay text and the figures: CC BY 4.0, in `LICENSE-docs.md`.
