# Multi-Model Consensus Submission

We assemble a consensus SDRF submission from multiple language model
runs using `comparison.py`. Each model produces a full submission independently;
the consensus script merges them into a single output using per-column strategies
that resolve disagreements and fill gaps.

---

## Models compared


models	path	type
claude-sonnet-4-6	data\claude-sonnet-4-6\submission_claude_sonnet-4.6.R1.R2.csv	closed
gemma-3-4b	data\hdd2026\submission_gemma-3-4b-it_T0_R3_normalized\submission.csv	open
gpt-5.4	data\gpt-5.4\submission_gpt-5.4_R1.csv	closed
qwen3-4b	data\hdd2026\submission_qwen3-4b\submission_qwen3-4b_T0_R3_normalized.csv	open
deepseek-coder-v2-lite-instruct	data\hdd2026\submission_deepseek-coder-v2-lite-instruct_T0_R3_normalized\submission.csv	open
medgemma-4b-it	data\hdd2026\submission_medgemma-4b-it_T0_R3_normalized\submission.csv	open
nanbeige4.1-3b-q8	data\hdd2026\submission_nanbeige4.1-3b-q8_T0_R2_normalized\submission.csv	open
LocalAI-functioncall-llama3.2-3b-v0.5	data\hdd2026\submission_LocalAI-functioncall-llama3.2-3b-v0.5_T0_R3_normalized\submission.csv	open
gpt-o4-mini	data\gpt-o4-mini\submission_gpt-o4-mini.csv	closed
bggpt-gemma-3-27bgpt-o4-min-fp8	data\bggpt-gemma-3-27b-fp8\submission_bggpt-gemma-3-27b-fp8_R1.csv	open


---

## What `comparison.py` does

The script merges N submission CSVs into one, resolving disagreements
column by column using a strategy chosen by column type:

| Column pattern | Strategy | Rationale |
|---|---|---|
| `number_of_*`, `*_tolerance` | **Numeric consensus** — majority vote; tie → highest value | Tolerances and replicate counts should be the largest defensible value |
| `FactorValue[*]`, `factors` | **Union** — all unique values joined with `;` | Factor values from different models capture different aspects; none should be dropped |
| `Characteristics[*]` | **Majority vote** — most common non-NA value wins | Categorical metadata: agree with the majority |
| `Comment[Instrument]`, `Comment[Software]` | **Trust first** — first input takes priority | Instrument names vary in specificity; prefer the most detailed source |
| Everything else | **Majority vote** | Safe default |

Fields that are `Not Applicable` in all inputs fall back to hard-coded
proteomics defaults where applicable:

- `Characteristics[AlkylationReagent]` → `IAA`
- `Characteristics[ReductionReagent]` → `DTT`
- `Characteristics[Enzyme]` → `NT=Trypsin;AC=MS:1001251`

Each model's fill rate and top values per column are logged to the
comparison matrix CSV for inspection.

---

## Ensemble runs (`comparenmerge.bat`)

Three merge passes are run in sequence:

```bat
:: 1. Remote models only
uv run comparison.py
    --inputs gpt-5.4 gemma3-27b o4-mini claude-sonnet-4-6
    --out_sdrf submission.remote.csv
    --out_matrix comparison_matrix.remote.csv

:: 2. Local models only
uv run comparison.py
    --inputs deepseek-coder-v2-lite-instruct gemma-3-4b-it LocalAI-llama3.2-3b
    --out_sdrf submission.local.csv
    --out_matrix comparison_matrix.local.csv

:: 3. All models combined
uv run comparison.py
    --inputs [all 7 models above]
    --out_sdrf submission.all.csv
    --out_matrix comparison_matrix.all.csv
```

The three output submissions are then evaluated separately to determine which
ensemble performs best before selecting the final Kaggle upload.

---

## Usage

```bat
:: Run all three ensemble passes
comparenmerge.bat

:: Or run a custom merge
uv run comparison.py ^
    --inputs data\gpt-5.4\submission_gpt-5.4_R1.csv ^
             data\claude-sonnet-4-6\submission_claude_sonnet-4.6.R1.R2.csv ^
    --names gpt5.4 claude-sonnet ^
    --out_sdrf my_submission.csv ^
    --out_matrix my_matrix.csv
```

Output files:

| File | Description |
|---|---|
| `submission.remote.csv` | Consensus of 4 commercial-API models |
| `submission.local.csv` | Consensus of 3 local models |
| `submission.all.csv` | Consensus of all 7 models |
| `comparison_matrix.remote.csv` | Per-column fill rates and top values (remote) |
| `comparison_matrix.local.csv` | Per-column fill rates and top values (local) |
| `comparison_matrix.all.csv` | Per-column fill rates and top values (all) |

---

## Rationale for the ensemble approach

Individual models make different errors and have different strengths — commercial
large models tend to produce better ontology-formatted values; local small models
are faster to iterate but noisier. The consensus strategy is designed so that:

- A value present in a majority of models wins over any single outlier.
- Factor values are unioned rather than voted on, since different models may
  correctly identify different experimental variables.
- Numeric fields bias toward the highest plausible value, which is safer for
  replicate counts and tolerances than rounding down.
- Hard defaults for mandatory proteomics fields (trypsin, DTT, IAA) ensure
  the submission is never blank on fields that are almost universal.
