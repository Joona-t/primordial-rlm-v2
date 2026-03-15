from __future__ import annotations

import json
import sys
import time
from pathlib import Path

repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "rlm"))

import rlm.core.rlm as rlm_module
from rlm.logger import RLMLogger
from tests.mock_lm import MockLM

from forge_chamber import ForgeChamberError, validate_chamber
from forge_reversible_summary import ForgeRefError
from forge_trace_codec import decode_trace, encode_trace, verify_trace
from forge_stage_output import create_v1_stage_artifact
from primordial_rlm_bridge import PrimordialRLM, run_primordial_analysis

_original_get_client = rlm_module.get_client
_original_count_tokens = rlm_module.count_tokens


def _patch_get_client(mock_lm: MockLM):
    rlm_module.get_client = lambda backend, kwargs: mock_lm


def _restore_patches():
    rlm_module.get_client = _original_get_client
    rlm_module.count_tokens = _original_count_tokens


def _fake_count_tokens(messages, model_name):
    if len(messages) > 5:
        return 200_000
    return 100


def _run_primordial(responses, prompt, rlm_kwargs, *, force_compaction=False):
    mock_lm = MockLM(responses=list(responses))
    _patch_get_client(mock_lm)
    if force_compaction:
        rlm_module.count_tokens = _fake_count_tokens
    logger = RLMLogger()
    rlm = PrimordialRLM(logger=logger, **rlm_kwargs)
    try:
        result = rlm.completion(prompt)
        chamber = rlm.chamber
        trajectory = logger.get_trajectory()
    finally:
        rlm.close()
        _restore_patches()
    return result, chamber, trajectory


def scenario_deep_recursion():
    responses = [
        'Need part A.\n```repl\nr1 = rlm_query("What is 2+3?")\nprint(r1)\n```',
        'FINAL(5)',
        'Need part B.\n```repl\nr2 = rlm_query("What is 5*7?")\nprint(r2)\n```',
        'FINAL(35)',
        'Need part C.\n```repl\nr3 = rlm_query("What is 35-11?")\nprint(r3)\n```',
        'FINAL(24)',
        'FINAL(Combined: 5, 35, 24)',
    ]
    kwargs = dict(
        backend="openai",
        backend_kwargs={"model_name": "mock-model"},
        environment="local",
        max_depth=3,
        max_iterations=8,
    )
    result, chamber, trajectory = _run_primordial(responses, "compute chain", kwargs)
    analysis = run_primordial_analysis(chamber, 0)
    return {
        "scenario": "E_deep_recursion",
        "result_response": result.response,
        "stage_count": analysis["stage_count"],
        "max_depth": analysis["provenance"]["max_depth"],
        "all_reach_root": analysis["provenance"]["all_reach_root"],
        "trace_verified": analysis["trace_verified"],
        "validation_errors": analysis["validation_errors"],
        "vanilla_iteration_count": len(trajectory.get("iterations", [])) if trajectory else 0,
    }


def scenario_compaction_semantic_check():
    responses = [
        "Step 1.\n```repl\na = 1\nprint(a)\n```",
        "Step 2.\n```repl\nb = a + 9\nprint(b)\n```",
        "Summary: established a=1 and b=10; proceed to final.",
        "FINAL(Final b=10)",
    ]
    kwargs = dict(
        backend="openai",
        backend_kwargs={"model_name": "mock-model"},
        environment="local",
        max_depth=1,
        max_iterations=8,
        compaction=True,
        compaction_threshold_pct=0.85,
    )
    _, chamber, _ = _run_primordial(responses, "compute b", kwargs, force_compaction=True)
    compaction_stages = [s for s in chamber.get("stages", []) if ":compact:" in s.get("stage_id", "")]
    if not compaction_stages:
        return {"scenario": "F_compaction_semantic_check", "passed": False, "reason": "no compaction stage produced"}
    compaction = compaction_stages[0]
    refs = [r.get("ref") for r in compaction["artifact"].get("refs", []) if isinstance(r, dict) and r.get("state") == "resolved"]
    expected = [s.get("stage_id") for s in chamber.get("stages", []) if ":iter:" in s.get("stage_id", "")][: len(refs)]
    return {
        "scenario": "F_compaction_semantic_check",
        "passed": refs == expected and len(refs) > 0,
        "compaction_ref_count": len(refs),
        "expected_ref_count": len(expected),
        "refs": refs,
        "expected": expected,
    }


def scenario_mutation_detection():
    responses = [
        "Working.\n```repl\nx = 4\nprint(x)\n```",
        "FINAL(4)",
    ]
    kwargs = dict(
        backend="openai",
        backend_kwargs={"model_name": "mock-model"},
        environment="local",
        max_depth=1,
        max_iterations=4,
    )
    _, chamber, _ = _run_primordial(responses, "return 4", kwargs)
    base_errors = validate_chamber(chamber)

    mutated_missing_index = json.loads(json.dumps({**chamber, "artifact_index": sorted(chamber["artifact_index"])}))
    if len(mutated_missing_index["artifact_index"]) > 1:
        mutated_missing_index["artifact_index"].pop()
    desync_errors = validate_chamber(mutated_missing_index)

    trace = encode_trace(chamber)
    if trace.get("stages") and trace["stages"][0].get("artifact"):
        trace["stages"][0]["artifact"]["output"] = "tampered"
    verify = verify_trace(trace, chamber)

    return {
        "scenario": "G_mutation_detection",
        "base_error_count": len(base_errors),
        "desync_error_count": len(desync_errors),
        "desync_detected": len(desync_errors) > 0,
        "tamper_detected": not verify.get("valid", False),
        "tamper_hash_match": verify.get("hash_match"),
        "tamper_content_match": verify.get("content_match"),
    }


def scenario_illegal_transition_probe():
    chamber_like = {
        "transition_examples": [
            ("not_invoked", "invalid"),
            ("deleted", "pruned_recoverable"),
            ("unknown", "resolved"),
        ]
    }
    return {
        "scenario": "H_transition_probe",
        "status": "spec_gap",
        "finding": "Null ontology states exist, but legal transition rules are not yet encoded in the protocol or validator.",
        "examples": chamber_like["transition_examples"],
    }


def main():
    started = time.time()
    results = [
        scenario_deep_recursion(),
        scenario_compaction_semantic_check(),
        scenario_mutation_detection(),
        scenario_illegal_transition_probe(),
    ]
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - started, 3),
        "results": results,
    }
    out = repo_root / "results" / "rigorous_test_results.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
