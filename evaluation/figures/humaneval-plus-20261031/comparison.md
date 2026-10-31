# RQ3 Cross-Model Comparison

Python-PurePy gaps per model, for runs with matched tasks and protocol. Positive values mean Python leads.

## Matched Protocol 981ab2ad2a2a5556

| Model | Size (B) | Stage | Python Tests | PurePy Tests | Valid PurePy | Test Gap (pp) | Validity Gap (pp) | Accepted | PurePy Pass On Accepted | Python Pass On Accepted | Gap On Accepted (pp) | Status |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| claude-opus-5-5 | None | initial | 155/163 | 148/163 | 132/163 | 4.3 | 14.1 | 140 | 132/140 | 138/140 | 4.3 | complete |
| claude-opus-5-5 | None | final | 155/163 | 148/163 | 146/163 | 4.3 | 5.5 | 161 | 146/161 | 154/161 | 5.0 | complete |
| deepseek-v4-pro | None | initial | 157/163 | 141/163 | 117/163 | 9.8 | 24.5 | 132 | 117/132 | 130/132 | 9.8 | complete |
| deepseek-v4-pro | None | final | 157/163 | 141/163 | 140/163 | 9.8 | 10.4 | 161 | 140/161 | 155/161 | 9.3 | complete |
