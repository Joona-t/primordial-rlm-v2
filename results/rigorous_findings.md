# Rigorous Follow-up Findings

**Status:** experimental follow-up report.

This document records a stricter second pass on the original Primordial x RLM demo.
It should be read as an **experimental log**, not as a final validation report.

Generated: 2026-03-15T11:30:14Z  
Environment: local repository virtualenv (`.venv`) with Python 3.11.14

---

## Purpose

The initial repository demonstrated four baseline scenarios:
- linear execution
- recursive execution
- compaction
- deliberate invariant violations

That was enough to show that the idea was mechanically plausible.
It was **not** enough to show that the idea held up under stronger structural probes.

This follow-up therefore asked four harder questions:

1. Does provenance survive a deeper recursive chain?
2. Can compaction refs be checked semantically, not just structurally?
3. Can deliberate structural mutation and trace tampering actually be detected?
4. What important parts of the protocol remain underspecified?

---

## Added runner

A dedicated stricter runner was added:

- `rigorous_tests.py`

It complements, rather than replaces, the original baseline experiment.

---

## Results by scenario

### E_deep_recursion
**Question:** Does the bridge preserve provenance under a larger recursive chain than the original demo?

**Outcome:** PASS

**Observed values**
- response: `Combined: 5, 35, 24`
- stage count: `7`
- maximum provenance depth: `4`
- all artifacts reach root: `true`
- trace verified: `true`
- validation errors: `0`
- vanilla parent logger iterations: `4`

**Interpretation**
The bridge survives a deeper recursive ancestry chain while preserving explicit lineage and trace integrity. This strengthens the original reversibility claim beyond the smaller scripted recursion case.

---

### F_compaction_semantic_check
**Question:** When compaction occurs, do the stored refs correspond to the correct compacted iterations, rather than merely existing as valid references?

**Outcome:** PASS

**Observed values**
- compaction ref count: `2`
- expected ref count: `2`
- actual refs matched the expected compacted iteration IDs exactly

**Interpretation**
This is stronger than a structural validation check. In this scenario, the compaction artifact did not merely contain valid refs; it pointed to the semantically correct pre-compaction iteration set.

**Caution**
This is still a scripted case. It supports the claim that semantic checking is possible, not that semantic correctness is solved in general.

---

### G_mutation_detection
**Question:** Can the protocol detect corruption introduced after generation, rather than only validating clean traces?

**Outcome:** PASS

**Observed values**
- baseline chamber validation errors: `0`
- deliberate artifact-index desync errors: `1`
- desync detected: `true`
- trace tamper detected: `true`
- hash match after tamper: `false`
- content match after tamper: `false`

**Interpretation**
The protocol detects both:
- chamber-level structural corruption
- encoded-trace tampering

This matters because it distinguishes the system from passive logging. The layer is not merely describing good executions; it is capable of rejecting corrupted ones.

---

### H_transition_probe
**Question:** Is the typed-absence ontology already strong enough to support rigorous state evolution claims?

**Outcome:** SPEC GAP IDENTIFIED

**Finding**
Typed absence labels exist, but legal transition rules between those labels are not yet encoded in the protocol or validator.

**Examples of unresolved transition questions**
- `not_invoked -> invalid`
- `deleted -> pruned_recoverable`
- `unknown -> resolved`

**Interpretation**
This is now the clearest design weakness in the current system. The protocol has an ontology of absence labels, but not yet an explicit state machine governing legal evolution among them.

This limits how strongly one can argue about correctness over time.

---

## Overall assessment

The stricter follow-up supports three claims more strongly than the original demo alone:

1. **Provenance survives deeper recursion**
2. **Compaction refs can be semantically checked, not just structurally validated**
3. **Mutations and tampering are detectable**

The main unresolved weakness is not trace encoding or provenance itself.
It is the lack of a formal **absence-transition semantics**.

That means the project is stronger on:
- lineage
- artifact integrity
- compaction grounding

than it currently is on:
- state evolution theory
- legality of null/absence transitions over time

---

## What this log does and does not show

### Supported by this run
- the bridge remains structurally coherent under deeper recursion
- compaction lineage can be tested more semantically than before
- corruption can be detected rather than silently tolerated

### Not yet established
- behavior under real-model output noise at scale
- behavior under retries, tool crashes, partial registration, or interrupted persistence
- a complete formal semantics for absence-state transitions
- generalization across multiple agent runtimes

---

## Recommended next moves

### 1. Formalize the absence-state machine
Encode legal and illegal transitions explicitly.
This is the highest-leverage next step.

### 2. Add randomized / property-based corruption tests
The current mutation checks are targeted and useful, but still scripted.
A stronger regime would generate malformed graphs and corrupted traces automatically.

### 3. Add crash/interruption scenarios
Examples:
- artifact created but not registered
- registered but not sealed
- persisted partially
- subcall returns ambiguous incomplete state

### 4. Add more explicit baselines
Compare against:
- vanilla logging
- provenance-only wrapper
- hash-only wrapper
- full Primordial layer

### 5. Run against recorded real-model traces
This is required before making stronger claims about practical agent reliability.

---

## Bottom line

This follow-up does **not** turn the repository into a finished research result.

It does something valuable and narrower:

> it converts the original demo from a plausible instrumentation sketch into a more credible experimental prototype with concrete pass/fail evidence and one clearly exposed theoretical gap.

That is enough to justify continued work.
