# SDRF Extraction Pipeline — Submission

**Competition:** [Harmonizing the Data of Your Data](https://www.kaggle.com/competitions/harmonizing-the-data-of-your-data)  
**Task:** Extract structured SDRF metadata from proteomics paper text for 15 datasets.  
**Metric:** Macro-averaged F1 over agglomerative-clustered values per (PXD, column) pair.

> **Generality note:** although built for proteomics SDRF, the pipeline is
> domain-agnostic. The field registry (`fields.py`), prompts (`prompts.py`),
> and Pydantic output model (`models.py`) are the only files that encode
> domain knowledge. Replacing those three files is sufficient to repurpose
> the pipeline for any structured metadata extraction task or any schema 
> where a mix of rule-extractable and LLM-inferable fields
> must be populated from free-text sources.

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


### Postprocessing

- **Ontology normalisation** (`make_submission.py`): plain-text values are
  mapped to controlled vocabulary terms via the sdrf-pipelines OLS lookup
  (e.g. `Trypsin` → `AC=MS:1001251;NT=Trypsin`).
  
### Aggregaiton


- **Multi-model ensemble** (consensus: outputs from different models
  are merged using per-column consensus strategies — majority vote for
  categorical fields, union with deduplication for factor values, highest
  value for numeric fields (replicates, tolerances).
  
- Consensus on all 10 LLMs  - public score 0.23
claude-sonnet-4-6
gemma-3-4b
gpt-5.4
qwen3-4b
deepseek-coder-v2-lite-instruct
medgemma-4b-it
nanbeige4.1-3b-q8
LocalAI-functioncall-llama3.2-3b-v0.5
gpt-o4-mini
bggpt-gemma-3-27bgpt-o4-min-fp8
  
 
- **Sequential Hole-Filling** (fill hole): outputs from different models
  are merged using per-column consensus strategies — majority vote for
  categorical fields, union with deduplication for factor values, highest
  value for numeric fields (replicates, tolerances).

We submitted the sequential aggregation of the following sets:

- all 10 LLMs - public score .287
claude-sonnet-4-6
gemma-3-4b
gpt-5.4
qwen3-4b
deepseek-coder-v2-lite-instruct
medgemma-4b-it
nanbeige4.1-3b-q8
LocalAI-functioncall-llama3.2-3b-v0.5
gpt-o4-mini
bggpt-gemma-3-27bgpt-o4-min-fp8

- 7 open models  - public score .23
gemma-3-4b
gpt-5.4
qwen3-4b
deepseek-coder-v2-lite-instruct
medgemma-4b-it
nanbeige4.1-3b-q8
LocalAI-functioncall-llama3.2-3b-v0.5

- 4 models selected via fill stability / gain  - public score 0.285

claude-sonnet-4-6
gemma-3-4b
qwen3-4b
deepseek-coder-v2-lite-instruct

---


## Files

| File | Description |
|---|---|
| `make_submission.py` | Combines per-PXD CSVs, aligns columns, applies OLS normalisation |
| `comparison.py` | Merges and reconciles outputs from multiple models via consensus |
| `compare_scores.py` | Local F1 scorer against training ground truth or another submission |
| `requirements.txt` | Dependencies (includes `kaggle_sdrfmess` as git dependency) |
| `submission.csv` | Final submission |

The extraction pipeline itself lives in
[`kaggle_sdrfmess`](https://github.com/vedina/modelmess/tree/main/sdrf_pipeline)
and is declared as a git dependency.

---

## Installation & Usage

We recommend using uv [instead](https://docs.astral.sh/uv/) and provide pyproject.toml

```bash
uv sync
```

```bash
pip install -r requirements.txt
```

```bash
# 1. Extract SDRF per paper (run from the pipeline repo)
uv run -m main_fill data/TestPubText/ --stage rules --rules-dir output/rules
uv run -m main_fill data/TestPubText/ --stage llm \
    --fill-from output/rules --llm-dir output/llm \
    --model gpt-4o --api-key $OPENAI_API_KEY
	
Works with any OpenAI compatible API  ( tested with LocalAI on Kaggle - notebooks provided)

# 2. Build submission
uv run make_submission.py output/llm \
    --sample-submission data/SampleSubmission.csv \
    -o submission.csv

# 3. (Optional) merge (two or more) model outputs
uv run comparison.py \
    --inputs output/llm_gpt4o/final.csv output/llm_claude/final.csv \
    --names gpt4o claude \
    --out_sdrf final_merged.sdrf.csv

# 4. Local scoring (compare two submissions)
uv run compare_scores.py \
    --ours submission.csv \
    --compare other_submission.csv
```

---

## References

- [sdrf-pipelines](https://github.com/bigbio/sdrf-pipelines) — OLS ontology normalisation

