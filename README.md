# Primordial x RLM Experiment

**Status:** experimental, preliminary, and intentionally falsifiable.

This repository tests a narrow systems hypothesis:

> Can a grammar-level structural enforcement layer catch failures in recursive LLM execution that native trajectory logging does not represent, detect, or preserve?

The project wraps [RLM](https://github.com/alexzhang13/rlm) (Recursive Language Model) execution with a small set of **Primordial Computing** protocol tools:
- typed absence enforcement
- grounded summaries with explicit source references
- append-only artifact registration
- trace compression with integrity verification
- v1 artifact envelopes with protocol validation

The goal is **not** to claim a finished framework or a general proof of agent reliability.
The goal is to evaluate whether a stricter representation of absence, provenance, and compaction yields measurable structural advantages over flat native logging.

---

## Research Question

Recursive LLM systems generate multi-step traces under conditions that are structurally hostile to reliability:
- recursive subcalls create nested ancestry
- context compaction rewrites or deletes local history
- outputs can be missing, partial, malformed, or silently collapsed into `None`
- native logs often serialize events without preserving explicit provenance or integrity contracts

This repository asks whether a lightweight protocol layer can improve the situation along three dimensions:

1. **Reconstructability** — can outputs be traced back to their producing ancestors?
2. **Violation detection** — can structural failures be caught at generation/registration/verification time?
3. **Integrity under compression** — can traces be compacted while preserving recoverable lineage?

---

## Experimental Idea

The central idea is simple:

**absence, provenance, and compaction should be first-class protocol objects rather than accidental implementation details.**

In practice, the Primordial layer adds the following invariants:

| Module | Invariant introduced |
|---|---|
| `forge_nulls.py` | No `None` / empty field without a typed absence state |
| `forge_reversible_summary.py` | No summary without `source_refs` grounding what was summarized |
| `forge_chamber.py` | Append-only artifact registration, ref validation, duplicate rejection, sealed-state enforcement |
| `forge_trace_codec.py` | Structural compression with SHA-256 round-trip verification |
| `forge_stage_output.py` | Standardized stage artifacts with content hashing, producer metadata, protocol discipline |

This is an **experimental protocol layer**, not a claim of semantic correctness. It is best understood as a structural instrumentation experiment.

---

## Bridge Architecture

`primordial_rlm_bridge.py` subclasses `RLM` as `PrimordialRLM` and overrides four execution points:

```text
RLM.completion()          -> open chamber, seal on completion
RLM._completion_turn()    -> register each iteration as a v1 artifact
RLM._subcall()            -> register child results with parent refs
RLM._compact_history()    -> register compaction summary with source_refs to compacted artifacts
```

No direct modifications are made to RLM internals. The bridge is an extension layer.

---

## Hypotheses

### H1 — Reversibility / provenance survival
After an RLM run, including recursion and compaction, can each artifact be traced back to a root lineage?

**Metric**
- `reversibility_score`: fraction of artifacts whose resolved provenance chain reaches root
- trace round-trip validity after encode/decode verification

### H2 — Structural violation detection
Can the Primordial layer catch structural failures that vanilla logging does not explicitly detect?

**Metric**
- count of deliberate invariant violations detected by Primordial vs vanilla logger

### H3 — Trace overhead / representation efficiency
How large is the Primordial trace representation compared with vanilla logger output?

**Metric**
- encoded Primordial trace size vs vanilla logger JSON payload size
- additional trace-compression statistics

### H4 — Post-demo rigor checks
Do the above claims hold under stronger probes beyond the initial demonstration?

**Additional probes**
- deeper recursive ancestry
- semantic verification of compaction refs
- mutation/tamper detection
- identification of protocol-spec gaps

---

## Experimental Setup

All baseline scenarios currently use `MockLM`, so runs are deterministic and reproducible without API keys.

This makes the repository useful for:
- protocol debugging
- structural evaluation
- repeatable ref/provenance tests

It does **not** yet establish performance under real model noise, retries, malformed outputs, or partial tool failures.

---

## Baseline Scenarios

| Scenario | Description |
|---|---|
| `A_linear` | 3 iterations, no recursion, no compaction |
| `B_tree_recursion` | 3 parent iterations + 2 subcalls |
| `C_compaction` | 3 iterations + forced compaction |
| `D_violations` | 6 deliberate structural violations |

### Main results

#### H1 — Reversibility

```text
Scenario                    Primordial      Vanilla   Trace OK
------------------------------------------------------------
A_linear                          1.00         0.00        YES
B_tree_recursion                  1.00         0.00        YES
C_compaction                      1.00         0.00        YES
```

Interpretation:
- every Primordial artifact in the tested scenarios retained a valid provenance chain to root
- vanilla logger output contained no explicit provenance structure
- encoded traces round-tripped with integrity verification

#### H2 — Violation detection

```text
Scenario                    Primordial      Vanilla    Tests
----------------------------------------------------------
D_violations                         6            0        6
```

Detected violation classes:
- raw `None` without typed absence
- ungrounded summary with empty `source_refs`
- dangling upstream ref
- duplicate artifact registration
- registration after chamber seal
- missing `summary_state` when no summary exists

Interpretation:
- Primordial caught all scripted structural violations
- vanilla logger caught none because it does not encode these invariants

#### H3 — Representation size

```text
Scenario                    P bytes   V bytes  vs Vanilla  Compress
-----------------------------------------------------------------
A_linear                       4032     35750      -88.7%     1.08x
B_tree_recursion               6858     59899      -88.5%     1.10x
C_compaction                   5571     36582      -84.8%     1.10x
```

Interpretation:
- in these scenarios, Primordial traces were substantially smaller than vanilla logger payloads
- this is largely because vanilla stores repeated prompt/message history at every step
- this should **not** be generalized carelessly to all workloads without larger-scale tests

---

## Rigorous Follow-up Tests

A stricter follow-up runner was added in `rigorous_tests.py`.

It extends the initial demo with four additional probes:

### E — deeper recursion provenance
- result: **pass**
- stage count: `7`
- max provenance depth: `4`
- all artifacts reached root
- trace verification passed

### F — compaction semantic verification
- result: **pass**
- compaction refs matched the exact expected pre-compaction iteration IDs in the scripted test

### G — mutation / tamper detection
- result: **pass**
- deliberate chamber index desync was detected
- deliberate encoded-trace tampering was detected
- both hash and content verification failed as expected after mutation

### H — ontology / transition probe
- result: **spec gap identified**
- typed absence labels exist, but legal state-transition rules are not yet encoded in the validator

Example unresolved transitions:
- `not_invoked -> invalid`
- `deleted -> pruned_recoverable`
- `unknown -> resolved`

This is the clearest current weakness in the protocol design.

See:
- `results/rigorous_test_results.json`
- `results/rigorous_findings.md`

---

## Limitations

This repository should be read with restraint.

### 1. The idea is experimental
This is an exploratory structural instrumentation layer, not a mature theory of agent memory or reliability.

### 2. Most runs use MockLM
The current evidence is deterministic and useful for protocol validation, but it does not yet model real-world output entropy.

### 3. Semantic correctness remains narrower than structural correctness
A ref can be well-formed and still be semantically wrong. One follow-up scenario now tests compaction semantics more directly, but the broader semantic-verification problem remains open.

### 4. Absence ontology is incomplete
The label set exists. The transition system does not. This prevents stronger claims about state evolution.

### 5. Single-process local execution only
Distributed, interrupted, and multi-runtime settings remain untested.

---

## What this repository currently supports

Reasonable claims:
- provenance can be explicitly represented across recursive and compacted runs
- structural violations can be detected that vanilla logging does not encode
- trace tampering can be detected with hash/content verification
- compaction can preserve recoverable lineage under the tested cases

Claims **not** yet supported:
- semantic correctness in the general case
- robustness under real model noise at scale
- a complete ontology of absence transitions
- universal overhead conclusions
- portability across many agent runtimes

---

## Next Steps

The strongest next moves are:

1. **Formalize absence-state transitions**
   - define legal transitions
   - define illegal transitions
   - add validator support

2. **Add randomized / property-based tests**
   - malformed refs
   - partial summaries
   - repeated compaction
   - corrupted trace payloads

3. **Inject crash/interruption faults**
   - exception after artifact creation
   - exception after registration but before seal
   - partial persistence failure

4. **Add stronger baselines**
   - hash-only wrapper
   - provenance-only wrapper
   - full Primordial layer

5. **Replay recorded real-model traces**
   - realistic payload sizes
   - malformed outputs
   - retries and partial failures

---

## Reproduction

```bash
git clone https://github.com/Joona-t/primordial-rlm-v2.git
cd primordial-rlm-v2

# Create local environment with Python 3.11+
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e rlm  # after setup clones dependency

# Clone dependency if needed
./setup.sh

# Run baseline experiment
python run_experiment.py

# Run vanilla baseline
python vanilla_baseline.py

# Run stricter follow-up tests
python rigorous_tests.py
```

**Requirement:** Python 3.11+

---

## Repository Structure

```text
primordial-rlm-v2/
  run_experiment.py                # Main structured experiment
  vanilla_baseline.py              # Vanilla logger comparison
  rigorous_tests.py                # Stricter follow-up probes
  primordial_rlm_bridge.py         # RLM -> Primordial bridge
  forge_nulls.py                   # Typed absence protocol
  forge_reversible_summary.py      # Grounded summaries
  forge_chamber.py                 # Append-only artifact chamber
  forge_trace_codec.py             # Trace compression + verification
  forge_stage_output.py            # v1 stage artifact envelopes
  forge_v1_bridge.py               # v1 validators / bridge helpers
  forge_protocol_dict.json         # Protocol code definitions
  setup.sh                         # Dependency bootstrap
  results/
    experiment_results.json
    vanilla_baseline_results.json
    rigorous_test_results.json
    rigorous_findings.md
```

---

## Bottom line

This repository does **not** prove Primordial Computing as a general theory.

It does show something narrower and useful:

> if recursive LLM execution is instrumented with typed absence, explicit provenance, grounded compaction, and trace integrity checks, then some structural failures become visible, testable, and harder to ignore.

That is enough to justify the next round of experiments.

## License

MIT
