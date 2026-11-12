"""Reproducible BANKING77 quality audit and intent classification baseline."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata

LABELS = {
    "lost_or_stolen_card", "lost_or_stolen_phone",
    "card_payment_not_recognised", "cash_withdrawal_not_recognised",
}


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def redact(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    return re.sub(r"(?<!\d)\d(?:[ -]?\d){7,}(?!\d)", "[LONG_NUMBER]", text)


def read_split(path, split):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [
            {"id": f"{split}:{index}", "text": row["text"], "label": row["category"]}
            for index, row in enumerate(csv.DictReader(stream), 1)
            if row["category"] in LABELS and row["text"].strip()
        ]


def curate(rows, blocked_keys):
    groups = defaultdict(list)
    for row in rows:
        groups[normalize(row["text"])].append(row)
    clean, review = [], []
    for key, group in groups.items():
        labels = {row["label"] for row in group}
        if key in blocked_keys:
            reason = "evaluation_overlap"
        elif len(labels) > 1:
            reason = "conflicting_labels"
        else:
            clean.append(group[0])
            group = group[1:]
            reason = "normalized_duplicate"
        review.extend({"id": row["id"], "reason": reason} for row in group)
    return clean, review


def features(text):
    text = normalize(text)
    words = re.findall(r"\w+", text)
    return set(words) | {text[i:i+3] for i in range(len(text) - 2)}


def evaluate(pool, test):
    prepared = [(row["label"], features(row["text"])) for row in pool]
    confusion = {label: Counter() for label in sorted(LABELS)}
    errors = []
    for row in test:
        query = features(row["text"])
        ranked = sorted(prepared, key=lambda item: len(query & item[1]) / max(1, len(query | item[1])), reverse=True)
        votes = Counter(label for label, _ in ranked[:5])
        prediction = votes.most_common(1)[0][0]
        actual = row["label"]
        confusion[actual][prediction] += 1
        if actual != prediction:
            errors.append({"id": row["id"], "text": row["text"], "actual": actual, "prediction": prediction})
    scores = []
    for label in confusion:
        tp = confusion[label][label]
        denominator = sum(confusion[label].values()) + sum(counts[label] for counts in confusion.values())
        scores.append(2 * tp / denominator if denominator else 0)
    return {"rows": len(test), "macro_f1": round(sum(scores) / len(scores), 4),
            "confusion": confusion, "errors": errors}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("runs/local"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    train, test = (read_split(args.data / f"{name}.csv", name) for name in ("train", "test"))
    for row in train + test:
        row["text"] = redact(row["text"])
    blocked = {normalize(row["text"]) for row in test}
    # Apply the same evaluation-overlap rule to both versions.
    raw = [row for row in train if normalize(row["text"]) not in blocked]
    clean, review = curate(train, blocked)
    if not clean or not test:
        parser.error("Both training and test data must contain selected BANKING77 labels.")
    report = {
        "source_sha256": {name: hashlib.sha256((args.data / f"{name}.csv").read_bytes()).hexdigest()
                          for name in ("train", "test")},
        "selected_train_rows": len(train),
        "raw_pool": len(raw), "curated_pool": len(clean),
        "review_reasons": Counter(row["reason"] for row in review),
        "raw": evaluate(raw, test), "curated": evaluate(clean, test),
    }
    write(args.out / "report.json", report)
    write(args.out / "review.json", review)
    write(args.out / "pool-v1.json", raw)
    write(args.out / "pool-v2.json", clean)
    print(f"Macro-F1: {report['raw']['macro_f1']} -> {report['curated']['macro_f1']}")


if __name__ == "__main__":
    main()
