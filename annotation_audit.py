"""Score model annotations and export a review queue against bilingual reference cases."""
import argparse
from collections import Counter
import json
from pathlib import Path

from voiceops import LABELS, redact, write


def load_jsonl(path):
    rows = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            row = json.loads(line)
            if row["id"] in rows:
                raise ValueError(f"Duplicate ID: {row['id']}")
            rows[row["id"]] = row
    return rows


def audit(cases, predictions):
    unknown = predictions.keys() - cases.keys()
    if unknown:
        raise ValueError(f"Unknown prediction IDs: {sorted(unknown)}")
    queue, reasons = [], Counter()
    matches = 0
    for case_id, case in cases.items():
        candidate = predictions.get(case_id, {})
        label, evidence = candidate.get("label"), candidate.get("evidence")
        flags = []
        if label not in sorted(LABELS | {"needs_review"}):
            flags.append("invalid_or_missing_label")
        if not isinstance(evidence, str) or not evidence.strip() or evidence not in redact(case["text"]):
            flags.append("evidence_not_in_source")
        if label != case["label"]:
            flags.append("reference_disagreement")
        elif not flags:
            matches += 1
        if label == "needs_review" or case["label"] == "needs_review":
            flags.append("ambiguous_intent")
        if flags:
            queue.append({"id": case_id, "text": redact(case["text"]), "reference": case["label"],
                          "reference_reason": case["reason"], "candidate": candidate, "flags": flags})
            reasons.update(flags)
    return {"cases": len(cases), "predictions": len(predictions),
            "matches_with_valid_evidence": matches, "review_counts": reasons, "queue": queue}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("edge_cases.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("runs/annotation-audit.json"))
    args = parser.parse_args()
    report = audit(load_jsonl(args.cases), load_jsonl(args.predictions))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write(args.out, report)
    print(f"{report['matches_with_valid_evidence']}/{report['cases']} matches with valid evidence")


if __name__ == "__main__":
    main()
