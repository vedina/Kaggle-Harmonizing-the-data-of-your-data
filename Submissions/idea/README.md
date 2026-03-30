# SDRF Extraction Pipeline — Submission

**Competition:** [Harmonizing the Data of Your Data](https://www.kaggle.com/competitions/harmonizing-the-data-of-your-data)  
**Task:** Extract structured SDRF metadata from proteomics paper text for 15 datasets.  
**Metric:** Macro-averaged F1 over agglomerative-clustered values per (PXD, column) pair.

---

## Method

A two-stage hybrid pipeline combining deterministic rule extraction with
LLM gap-fill, followed by ontology normalisation.

### Stage 1 — Rule-based extraction

A regex and keyword pass over the paper's title, abstract, and methods section
deterministically fills fields that can be resolved without ambiguity:
organism, tissue, isobaric label type and channel count (TMT/iTRAQ/SILAC),
instrument model, cleavage agent, fragmentation and acquisition method, LC
parameters, search tolerances, and sample preparation reagents. One row is
produced per raw data file; TMT/iTRAQ experiments produce one row per channel.
Rule output is written to a separate folder and never modified by later stages.

### Stage 2 — LLM gap-fill

Only fields still `Not Applicable` after the rule pass are sent to the LLM.
The fill uses a two-turn conversation per unique N/A pattern (deduplicated
across rows): pass 1 produces a free-text inventory from the paper; pass 2
converts it into a JSON patch restricted to exactly the N/A attribute set.
Rule-derived values cannot be overwritten. Paper text is trimmed to a
configurable context budget with a 5% safety margin.

Models used: `gpt-4o`, `gpt-4o-mini`, `claude-sonnet`.

### Post-processing

- **Column alignment**: per-PXD CSVs are concatenated and columns are aligned
  to the sample submission schema.
- **Ontology normalisation** (`make_submission.py`): plain-text values are
  mapped to controlled vocabulary terms via the sdrf-pipelines OLS lookup
  (e.g. `Trypsin` → `AC=MS:1001251;NT=Trypsin`).
- **Multi-model ensemble** (`comparison.py`): outputs from different models
  are merged using per-column consensus strategies — majority vote for
  categorical fields, union with deduplication for factor values, highest
  value for numeric fields (replicates, tolerances).

---

## Results

| Configuration | Kaggle F1 |
|---|---|
| Public notebook baseline | 0.270 |
| Rules only | ~0.22 |
| Rules + `gpt-4o-mini` | 0.260 |
| Rules + `gpt-4o` | ~0.26 |

Scores reflect the public leaderboard (approximately half of test columns).
The full evaluation includes all SDRF columns; ontology normalisation is
expected to improve scores on `Characteristics[CleavageAgent]`,
`Characteristics[Label]`, `Characteristics[Modification]`, and
`Comment[Instrument]`.

---

## Files

| File | Description |
|---|---|
| `make_submission.py` | Combines per-PXD CSVs, aligns columns, applies OLS normalisation |
| `comparison.py` | Merges and reconciles outputs from multiple models |
| `compare_scores.py` | Local F1 scorer against training ground truth or another submission |
| `requirements.txt` | Dependencies (includes `kaggle_sdrfmess` as git dependency) |
| `submission.csv` | Final submission |

The extraction pipeline itself lives in
[`kaggle_sdrfmess`](https://github.com/vedina/modelmess/tree/main/sdrf_pipeline)
and is declared as a git dependency.

---

## Installation & Usage

```bash
pip install -r requirements.txt
```

```bash
# 1. Extract SDRF per paper (run from the pipeline repo)
python -m main_fill data/TestPubText/ --stage rules --rules-dir output/rules
python -m main_fill data/TestPubText/ --stage llm \
    --fill-from output/rules --llm-dir output/llm \
    --model gpt-4o --api-key $OPENAI_API_KEY

# 2. Build submission
python make_submission.py output/llm \
    --sample-submission data/SampleSubmission.csv \
    -o submission.csv

# 3. (Optional) merge two model outputs
python comparison.py \
    --inputs output/llm_gpt4o/final.csv output/llm_claude/final.csv \
    --names gpt4o claude \
    --out_sdrf final_merged.sdrf.csv

# 4. Local scoring (compare two submissions)
python compare_scores.py \
    --ours submission.csv \
    --compare other_submission.csv
```

---

## References

- Deutsch EW et al. *A proteomics sample metadata representation for multiomics
  integration and big data analysis.* Nature Communications, 2020.
- [SDRF-Proteomics specification](https://github.com/bigbio/proteomics-sample-metadata)
- [sdrf-pipelines](https://github.com/bigbio/sdrf-pipelines) — OLS ontology normalisation
- [Competition metric](https://www.kaggle.com/code/iansitarik/sdrf-f1) — agglomerative clustering F1

---

## Checklist

- [x] Code runs without errors
- [x] Dependencies listed in `requirements.txt`
- [x] README documents the approach
- [x] Submission file is properly formatted
