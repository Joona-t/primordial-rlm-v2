# Primordial x RLM Experiment

Can a grammar-level enforcement layer catch structural problems in recursive LLM execution that native logging misses?

This experiment wraps [RLM](https://github.com/alexzhang13/rlm) (Recursive Language Model) execution with [Primordial Computing](https://github.com/Joona-t) tools — typed absence enforcement, grounded summaries, and hash-verified trace compression — and measures what each system sees.

## The Problem

RLM runs iterative LLM + code execution loops with recursion and context compaction. Its built-in logger stores iterations as a flat list with no structural invariants:

- **No provenance**: Can't trace an output back to the iteration that produced it
- **No integrity**: No content hashing — outputs could be silently modified
- **No null discipline**: Empty responses, missing data accepted without complaint
- **Compaction is lossy**: When context is compressed, original messages are deleted with no recovery path
- **Subcalls are invisible**: Child RLM iterations go to a separate logger the parent can't see

## What Primordial Adds

Primordial Computing is a set of Python modules that enforce structural invariants on data flowing through multi-step AI systems:

| Module | Invariant |
|---|---|
| `forge_nulls.py` | No `None`/empty value without a typed absence state (8 canonical states: `not_generated`, `not_invoked`, `unknown`, `withheld`, `invalid`, `deleted`, `pruned_recoverable`, `unresolved`) |
| `forge_reversible_summary.py` | No summary without `source_refs` pointing to what was summarized. Ungrounded compression is a protocol violation. |
| `forge_chamber.py` | Append-only artifact registration with dangling ref detection, duplicate rejection, and sealed-state enforcement |
| `forge_trace_codec.py` | Dict-level dedup with `$ref` replacement. SHA-256 hash verification on encode/decode round-trip. |
| `forge_stage_output.py` | Full v1 artifact envelopes with content hashing, producer metadata, and protocol code validation |

## The Bridge

`primordial_rlm_bridge.py` subclasses `RLM` as `PrimordialRLM` and overrides four methods:

```
RLM.completion()          → Creates chamber, seals on completion
RLM._completion_turn()    → Wraps each iteration as a v1 artifact with refs to previous
RLM._subcall()            → Wraps child results as artifacts with refs to parent iteration
RLM._compact_history()    → Creates SummaryView with source_refs to all compacted iterations
```

No modifications to RLM source or Primordial tools. The bridge is a pure extension.

## Three Hypotheses

### H1: Reversibility

> After an RLM run (including compaction and subcalls), can we trace every output back to its source?

**Metric**: `reversibility_score` = fraction of artifacts with valid provenance chains to root. Plus SHA-256 hash-verified trace round-trip.

### H2: Violation Detection

> Does Primordial catch structural problems that vanilla logging can't?

**Metric**: Count of invariant violations detected by each system across 6 violation types.

### H3: Overhead

> How does Primordial's trace size compare to vanilla logger output?

**Metric**: Byte size of Primordial compressed trace vs vanilla logger JSON payload.

## Results

Four scenarios tested with MockLM (no API keys needed):

| Scenario | Description |
|---|---|
| **A: Linear** | 3 iterations, no recursion, no compaction |
| **B: Tree Recursion** | 3 parent iterations + 2 subcalls, depth=2 |
| **C: Compaction** | 3 iterations + 1 forced compaction |
| **D: Violations** | 6 deliberate structural violations |

### H1: Reversibility

```
Scenario                    Primordial      Vanilla   Trace OK
------------------------------------------------------------
A_linear                          1.00         0.00        YES
B_tree_recursion                  1.00         0.00        YES
C_compaction                      1.00         0.00        YES
```

**Every artifact has a valid provenance chain to root. Every trace round-trips exactly. Vanilla has zero provenance.**

Scenario B achieves provenance depth 4 (iteration → subcall → iteration → subcall chain). Scenario C's compaction SummaryView preserves `source_refs` to all pre-compaction iterations — the originals are still reachable through the chamber even though RLM deleted them from the prompt.

### H2: Violation Detection

```
Scenario                    Primordial      Vanilla    Tests
----------------------------------------------------------
D_violations                         6            0        6
```

| Test | Violation | Caught By |
|---|---|---|
| D1 | `output=None` without typed absence state | `ForgeNullError` |
| D2 | Summary with empty `source_refs` | `ForgeRefError` |
| D3 | Artifact referencing nonexistent upstream | `ForgeChamberError` |
| D4 | Duplicate artifact ID registration | `ForgeChamberError` |
| D5 | Registration on sealed chamber | `ForgeChamberError` |
| D6 | Missing `summary_state` when summary is `None` | `ForgeChamberError` |

**Primordial catches all 6. RLM's logger catches 0.** The logger has no invariant checks — it serializes whatever you give it.

### H3: Overhead

```
Scenario                    P bytes   V bytes  vs Vanilla  Compress
-----------------------------------------------------------------
A_linear                       4032     35750      -88.7%     1.08x
B_tree_recursion               6858     59899      -88.5%     1.10x
C_compaction                   5571     36582      -84.8%     1.10x
```

**Primordial traces are ~87% smaller than vanilla logger output** because vanilla stores the full prompt history (including system prompt + entire growing message history) in every iteration record, while Primordial stores only semantic content with structural dedup.

Trace compression achieves 1.08-1.10x via `$ref` replacement of repeated producer metadata, hash objects, and ref entries.

## Limitations

These results come with caveats:

1. **MockLM responses are ~80 characters**. Real LLM responses are 500-5000 tokens. The absolute overhead ratio (Primordial metadata vs raw output text) is high for tiny payloads. The vs-vanilla comparison is meaningful; the absolute numbers need real payloads to be credible.

2. **Scenarios are scripted**. Every MockLM response succeeds on cue. Real RLM runs have failures, retries, and partial outputs. Adversarial fuzzing would stress-test edge cases.

3. **Semantic correctness is untested**. We proved all refs resolve, but didn't verify they point to the *right* ancestors. A compaction SummaryView has source_refs — but do those refs exactly match the iterations that were compacted?

4. **Single-process only**. RLM can run in Docker/Modal/E2B environments. This experiment only tested local execution.

## Next Steps

- **Recorded traces**: Run RLM against a real LLM, record responses, replay through MockLM for deterministic tests with realistic payloads
- **Adversarial fuzzing**: Random response lengths, failing code blocks, empty outputs — hundreds of iterations to find edge cases
- **Semantic verification**: After compaction, verify SummaryView source_refs exactly match pre-compaction iteration set
- **Scale testing**: 50+ iteration runs to measure overhead at realistic scale

## Reproduction

```bash
# Clone this repo
git clone https://github.com/Joona-t/primordial-rlm-experiment.git
cd primordial-rlm-experiment

# Setup (clones RLM, installs deps)
./setup.sh

# Run the experiment
python run_experiment.py

# Run vanilla baseline
python vanilla_baseline.py
```

Requires Python 3.11+. No API keys needed — all scenarios use MockLM.

## File Structure

```
primordial-rlm-experiment/
  run_experiment.py           # Main experiment: 4 scenarios, metrics, comparison table
  vanilla_baseline.py         # Baseline: same scenarios with RLM logger only
  primordial_rlm_bridge.py    # PrimordialRLM subclass (the bridge)
  forge_nulls.py              # Typed absence enforcement
  forge_reversible_summary.py # Grounded summaries with mandatory source_refs
  forge_chamber.py            # Append-only chamber with ref validation
  forge_trace_codec.py        # Structural trace compression with hash verification
  forge_stage_output.py       # v1 artifact envelope builder
  forge_v1_bridge.py          # v1 validator bridge (shim or canonical)
  forge_protocol_dict.json    # Protocol code definitions
  setup.sh                    # Clones RLM dependency
  results/
    experiment_results.json   # Full Primordial results
    vanilla_baseline_results.json  # Vanilla baseline results
```

## License

MIT
