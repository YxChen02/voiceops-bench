# VoiceOps-Bench

VoiceOps-Bench classifies English banking support messages and flags annotation problems for human review. The project uses BANKING77 for classification and a small set of English and Chinese examples to demonstrate annotation review.

1. **Classify support messages.** Assign a message to one of four intents: lost or stolen card, lost or stolen phone, unrecognized card payment, or unrecognized cash withdrawal. The baseline finds the five most similar labeled messages and uses their labels to vote.
2. **Check training data.** Detect duplicate messages, conflicting labels for the same text, and test messages that appear in training. The cleanup report records each removed sample and the reason.
3. **Audit annotations.** Compare predictions with reference labels and flag missing predictions, label disagreements, evidence excerpts missing from the input, and ambiguous requests. The audit accepts the included demo predictions or output from a local model.

**Example:** In case `edge-02`, the customer says in Chinese, “My phone was stolen. My bank card is in my wallet.” The reference label is **lost or stolen phone**. The demo prediction deliberately labels it **lost or stolen card**. The audit matches the two records by ID and puts the disagreement in the review queue.

## Quick start

The three experiments below use the Python standard library. You need Git and Python 3.10 or later.

```sh
git clone https://github.com/YxChen02/voiceops-bench.git
cd voiceops-bench
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b

python voiceops.py --data task-specific-datasets/banking_data
python quality_regression.py --data task-specific-datasets/banking_data
python annotation_audit.py demo_predictions.jsonl
```

## Data and evaluation

BANKING77 contains 77 English banking intents, with 10,003 training examples and 3,080 test examples in the original split. This project keeps the original split and selects **531 training examples and 160 test examples** across the four intents above. The upstream `banking_data/train.csv` and `banking_data/test.csv` files contain a customer message in `text` and its intent in `category`. The dataset is distributed under CC BY 4.0. [Dataset documentation](https://github.com/PolyAI-LDN/task-specific-datasets#banking) · [Original paper](https://arxiv.org/abs/2003.04807)

Both training pools mask email addresses and long digit sequences and exclude exact matches with the test set after text normalization. The cleaned pool also collapses duplicates that share a label and excludes groups with conflicting labels. The classifier ranks examples by Jaccard similarity over words and character trigrams. Both runs use the same classifier and test set.

The annotation audit uses 10 manually written English and Chinese reference cases, including two with simulated speech recognition errors. Cases can be labeled `needs_review` when the missing item or transaction channel is unclear. The audit checks whether the evidence appears in the input. A reviewer still needs to judge whether that excerpt supports the label.

## Results

- **Classification.** Both training pools contained 531 examples. Both runs achieved **0.9564 Macro-F1**, with **7 errors on 160 test examples**. The duplicate and conflict rules did not change the selected training pool, so this comparison provides no estimate of their effect on classification performance.
- **Cleanup regression.** The script injected three known defects: a formatting variant, an identical message with a conflicting label, and a message copied from the test set. It detected all three and also excluded the original record that conflicted with the injected label.
- **Annotation audit.** The demo supplies 9 predictions for 10 reference cases. Seven had matching labels and evidence found in the input. Five cases entered the review queue, including two for which the prediction and reference both used `needs_review`. A mock service verified the local model integration. Real LLM annotation performance has yet to be measured.

In BANKING77 case `test:1673`, the message reads “Someone stole my cards!” The baseline predicted a lost or stolen card, while the dataset label says lost or stolen phone. The evaluation report keeps the message, prediction, and dataset label together for review.

## Repository files

- [`voiceops.py`](voiceops.py) reads the BANKING77 CSV files, builds both training pools, and writes the classification metrics, errors, and cleanup records.
- [`quality_regression.py`](quality_regression.py) injects known defects into the training pool and checks that the cleanup rules produce the expected results.
- [`edge_cases.jsonl`](edge_cases.jsonl) contains the English and Chinese reference cases, with an ID, message, reference label, and reason on each line. The `noise` field marks simulated speech recognition errors.
- [`demo_predictions.jsonl`](demo_predictions.jsonl) contains hand-written predictions used to demonstrate label disagreements, evidence checks, and missing predictions.
- [`annotate.py`](annotate.py) sends masked messages to a local model and saves the resulting intent and evidence alongside each case ID.
- [`annotation_audit.py`](annotation_audit.py) matches predictions to reference cases by ID and writes summary counts and a review queue.
- [`README.md`](README.md) documents the project, experiments, and commands.
- [`.gitignore`](.gitignore) excludes generated outputs, the cloned dataset repository, Python caches, and local `.env` files.

## Generated files

- `runs/local/report.json` contains source file hashes, Macro-F1 scores, confusion matrices, and individual classification errors for both runs.
- `runs/local/pool-v1.json` contains the baseline training pool after excluding matches with the test set.
- `runs/local/pool-v2.json` contains the training pool after also handling duplicates and label conflicts within training.
- `runs/local/review.json` records the IDs of removed training samples and the reasons for removal.
- `runs/regression.json` records the number of retained samples and the disposition of flagged records in the injected-defect experiment.
- `runs/annotation-audit.json` contains audit counts and the review queue, including reference labels, predictions, and review reasons.
- `runs/model_predictions.jsonl` contains the case ID, predicted intent, and evidence for each response from the local model.

## Run annotations with a local model

Start a local Chat Completions service that supports JSON output. Replace `MODEL_ID` with the name of a loaded model. The script connects to `127.0.0.1:11434` by default. Use `--port` to select another port.

```sh
python annotate.py --model MODEL_ID
python annotation_audit.py runs/model_predictions.jsonl
```
