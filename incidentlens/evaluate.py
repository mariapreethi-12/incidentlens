"""Repeated controlled lab evaluations. Ground truth stays outside investigator input."""
import argparse
import json
import tempfile
import time
from pathlib import Path
from .agent import investigate
from .config import load_local_env
from .lab import Lab, SCENARIOS


def evaluate(mode="baseline", repeats=2):
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        lab = Lab(directory)
        try:
            for repeat in range(repeats):
                for expected in SCENARIOS:
                    lab.inject(expected)
                    lab.probe(6)
                    start = time.perf_counter()
                    try:
                        result = investigate(lab.snapshot(), mode)
                        diagnosis = result["diagnosis"]
                        rows.append({"repeat": repeat + 1, "expected": expected, "predicted": diagnosis["category"],
                                     "correct": diagnosis["category"] == expected, "elapsed_ms": result["elapsed_ms"],
                                     "citations": len(diagnosis["evidence_ids"]), "usage": result["usage"], "error": None})
                    except Exception as exc:
                        rows.append({"repeat": repeat + 1, "expected": expected, "predicted": "error", "correct": False,
                                     "elapsed_ms": round((time.perf_counter()-start)*1000, 1), "error": type(exc).__name__})
        finally:
            lab.close()
    import os
    return {"mode": mode, "model": os.environ.get("OPENAI_MODEL") if mode != "baseline" else None,
            "trials": len(rows), "correct": sum(r["correct"] for r in rows),
            "accuracy": round(sum(r["correct"] for r in rows)/len(rows), 3), "rows": rows,
            "scope": "Controlled, known local fault families, not production accuracy or held-out generalization. Baseline rules were designed for these faults. API failures count as incorrect."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "agent", "single-pass"], default="baseline")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", default="results/evaluation.json")
    args = parser.parse_args()
    load_local_env()
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be between 1 and 10")
    result = evaluate(args.mode, args.repeats)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
