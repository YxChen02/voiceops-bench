"""Inject known data defects into BANKING77 and verify the curation rules."""
import argparse
from collections import Counter
from pathlib import Path

from voiceops import LABELS, curate, normalize, read_split, redact, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("runs/regression.json"))
    args = parser.parse_args()
    train = read_split(args.data / "train.csv", "train")
    test = read_split(args.data / "test.csv", "test")
    for row in train + test:
        row["text"] = redact(row["text"])
    blocked = {normalize(row["text"]) for row in test}
    baseline, _ = curate(train, blocked)
    first, second = baseline[:2]
    injected = [
        {**first, "id": "injected:duplicate", "text": "  " + first["text"].upper() + "  "},
        {**second, "id": "injected:conflict",
         "label": min(LABELS - {second["label"]})},
        {**test[0], "id": "injected:overlap"},
    ]
    cleaned, queue = curate(baseline + injected, blocked)
    expected = {
        "injected:duplicate": "normalized_duplicate",
        "injected:conflict": "conflicting_labels",
        "injected:overlap": "evaluation_overlap",
        second["id"]: "conflicting_labels",
    }
    observed = {row["id"]: row["reason"] for row in queue}
    if observed != expected or cleaned != [row for row in baseline if row["id"] != second["id"]]:
        raise SystemExit(f"Curation regression: {observed}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write(args.out, {"original_rows": len(baseline), "injected_rows": len(injected),
                     "accepted_rows": len(cleaned), "review_counts": Counter(observed.values()),
                     "review": queue})
    print(f"Verified {len(injected)} injected defects and {len(queue)} review records.")


if __name__ == "__main__":
    main()
