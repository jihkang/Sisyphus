# Gemma 12B Benchmark Evidence

## Evaluated System

- Date: `2026-07-12`
- Model file identity: `gemma-4-12B-it-qat-q4_0.gguf`
- Model API parameter count: `11,907,350,576`
- Quantization/profile label: `Q4_0 QAT`
- llama.cpp server: `9290 (bcfd1989e)`
- Server context: `4096`
- Hardware: `Apple M5 Max`, Metal memory reported as `38,338 MiB`
- Sampling: `temperature=0`, `max_tokens=1024`, no fallback provider
- Fixture manifest: `benchmarks/local-agent/fixtures.json`

Model weights and machine-specific model paths are not stored in the repository.

## Results

| Artifact | Policy context/reserve/ratio | Overall | Coding | Safety | Actions | Blocked | Protocol | Compactions | Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemma-12b.json` | `2048/384/0.60` | 3/5 | 2/4 | 1/1 | 82 | 25 | 0 | 61 | 97.869 s |
| `gemma-12b-balanced.json` | `4096/1024/0.75` | 5/5 | 4/4 | 1/1 | 36 | 1 | 0 | 0 | 38.581 s |
| `gemma-12b-compaction.json` | `3072/768/0.75` | 5/5 | 4/4 | 1/1 | 36 | 1 | 0 | 2 | 38.176 s |

The 3072-token profile is the measured operating point for this fixture set. It
preserved full coding and safety success while exercising deterministic automatic
compaction in the median and multi-file cases.

## Claim Boundary

These results show that this exact Gemma 12B quantization, llama.cpp build,
configuration, runtime revision, and five small fixtures completed the measured
coding and safety checks. They do not establish general coding competence,
performance on large repositories, or expected behavior for a 31B model.

The 2048-token result is intentionally retained. It shows that compaction can be
too aggressive: 61 compactions coincided with two coding cases exhausting their
24-action budgets. The benchmark should therefore report context configuration
with every result instead of treating compaction count alone as a quality signal.
