"""Evaluate a local LLM on the four BANKING77 intents used by VoiceOps-Bench."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
from urllib.error import URLError

from annotate import POLICY, annotate
from voiceops import LABELS, curate, normalize, read_split, redact, write

DEMO_CUES = {
    "card_payment_not_recognised": "card payment",
    "cash_withdrawal_not_recognised": "cash withdrawal",
    "lost_or_stolen_card": "card was stolen",
    "lost_or_stolen_phone": "phone was stolen",
}


def select_examples(train, test):
    blocked = {normalize(row["text"]) for row in test}
    pool, review = curate(train, blocked)
    by_label = {label: [] for label in LABELS}
    for row in pool:
        by_label[row["label"]].append(row)
    if any(not rows for rows in by_label.values()):
        raise ValueError("The curated training split must contain all four intents.")
    examples = []
    for label in sorted(LABELS):
        rows = by_label[label]
        explicit = [row for row in rows if DEMO_CUES[label] in normalize(row["text"])]
        examples.append(min(explicit or rows, key=lambda row: (len(row["text"]), row["id"])))
    return examples, len(pool), Counter(row["reason"] for row in review)


def predict_case(row, endpoint, model, examples):
    try:
        result = annotate(row["text"], endpoint, model, examples)
    except (ValueError, KeyError, IndexError, TypeError) as error:
        result = {"label": None, "evidence": None, "response_error": str(error)}
    raw_label = result["label"]
    prediction = raw_label if isinstance(raw_label, str) and raw_label in LABELS | {"needs_review"} else "invalid"
    evidence = result["evidence"]
    grounded = isinstance(evidence, str) and bool(evidence.strip()) and evidence in row["text"]
    flags = []
    if prediction == "needs_review":
        flags.append("ambiguous_intent")
    if prediction == "invalid":
        flags.append("invalid_label_or_response")
    if prediction != row["label"]:
        flags.append("reference_disagreement")
    if not grounded:
        flags.append("evidence_not_in_source")
    return {"id": row["id"], "text": row["text"], "reference": row["label"],
            "prediction": prediction, "evidence": evidence, "flags": flags,
            **({"response_error": result["response_error"]} if "response_error" in result else {})}


def summarize(predictions):
    confusion = {label: Counter() for label in sorted(LABELS)}
    for row in predictions:
        confusion[row["reference"]][row["prediction"]] += 1
    per_intent_f1 = {}
    for label, counts in confusion.items():
        actual = sum(counts.values())
        predicted = sum(row[label] for row in confusion.values())
        per_intent_f1[label] = 2 * counts[label] / (actual + predicted) if actual + predicted else 0
    count = len(predictions)
    correct = sum(row["prediction"] == row["reference"] for row in predictions)
    review = [row for row in predictions if row["flags"]]
    return {
        "rows": count,
        "correct": correct,
        "accuracy": round(correct / count, 4),
        "macro_f1": round(sum(per_intent_f1.values()) / len(LABELS), 4),
        "per_intent_f1": {label: round(score, 4) for label, score in per_intent_f1.items()},
        "confusion": confusion,
        "needs_review_predictions": sum(row["prediction"] == "needs_review" for row in predictions),
        "invalid_predictions": sum(row["prediction"] == "invalid" for row in predictions),
        "review_queue_size": len(review),
        "review_reasons": Counter(flag for row in review for flag in row["flags"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", required=True, help="Model name exposed by the local server")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("runs/llm"))
    args = parser.parse_args()
    if args.workers < 1 or not 1 <= args.port <= 65535:
        parser.error("Provide a positive worker count and a valid server port.")
    train, test = (read_split(args.data / f"{split}.csv", split) for split in ("train", "test"))
    if {row["label"] for row in test} != LABELS:
        parser.error("The test split must contain all four intents.")
    for row in train + test:
        row["text"] = redact(row["text"])
    examples, pool_size, cleanup_reasons = select_examples(train, test)
    endpoint = f"http://127.0.0.1:{args.port}/v1/chat/completions"
    args.out.mkdir(parents=True, exist_ok=True)
    results = {}
    for variant, demonstrations in (("zero_shot", ()), ("few_shot", examples)):
        print(f"Running {variant} on {len(test)} test examples", flush=True)
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as workers:
                rows = list(workers.map(
                    lambda row: predict_case(row, endpoint, args.model, demonstrations), test
                ))
        except URLError as error:
            parser.exit(1, f"Local model request failed: {error}\n")
        results[variant] = summarize(rows)
        write(args.out / f"{variant}-predictions.json", rows)
        print(f"{variant}: Macro-F1 {results[variant]['macro_f1']:.4f}", flush=True)
    source_hashes = {
        split: hashlib.sha256((args.data / f"{split}.csv").read_bytes()).hexdigest()
        for split in ("train", "test")
    }
    write(args.out / "report.json", {"model": args.model, "training_pool_rows": pool_size,
                                   "cleanup_reasons": cleanup_reasons,
                                   "source_sha256": source_hashes,
                                   "policy_sha256": hashlib.sha256(POLICY.encode()).hexdigest(),
                                   "few_shot_examples": examples, **results})


if __name__ == "__main__":
    main()
