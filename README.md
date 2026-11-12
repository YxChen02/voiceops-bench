# VoiceOps-Bench

VoiceOps-Bench uses **Qwen2.5-1.5B-Instruct** to label banking support messages and identify cases for human review. Given a message, the model returns an intent and a supporting excerpt. The evaluation checks the label against BANKING77 and verifies that the excerpt appears in the input.

- **Classification** covers lost or stolen cards, lost or stolen phones, unrecognized card payments, and unrecognized cash withdrawals. The model can return `needs_review` when the request is ambiguous.
- **Data quality checks** mask email addresses and long digit sequences, merge duplicate training messages, isolate conflicting labels, and exclude training messages that match the test set after normalization.
- **Annotation review** records the reference label, predicted label, evidence, and reason for review. It covers English and Chinese, including two cases with simulated speech recognition errors.

For example, in bilingual case `edge-06`, a simulated transcription error affects a Chinese message about an ATM withdrawal. Qwen labeled it as an unrecognized card payment. The audit flagged the mismatch for human review.

## Results

The evaluation uses the same 160 English test examples for both Qwen prompts. The zero-shot prompt provides the labeling rules. The four-example prompt adds one example per intent from the cleaned training pool. Abstentions count as classification errors, and the report also counts them separately.

- **Zero-shot:** **0.7592 Macro-F1**, with 110 of 160 labels correct and 34 predicted as `needs_review`.
- **Four examples:** **0.6526 Macro-F1**, with 89 of 160 labels correct and 58 predicted as `needs_review`. The additional examples increased abstentions and reduced the score on this split.
- **Bilingual annotation audit.** Qwen returned predictions for all 10 reference cases. Seven matched their reference labels and had evidence in the input. Four entered the review queue, including one correctly flagged as ambiguous.

The earlier 5-NN baseline scored **0.9564 Macro-F1** on the same split. It used all 531 labeled training examples and always selected one of the four intents. [Run report](results/qwen2.5-report.json) · [Bilingual predictions](results/qwen2.5-bilingual-predictions.jsonl)

## Reproduce the evaluation

You need Git, Python 3.10 or later, and a local server that supports the Chat Completions API with JSON responses. The recorded run used **llama.cpp b6500** with the **Q4_K_M** GGUF weights and offloaded all model layers to an RTX 5060 Laptop GPU. The report records the model checksum, prompt checksum, and input data hashes. [llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b6500) · [Qwen weights](https://www.modelscope.cn/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF)

Download `qwen2.5-1.5b-instruct-q4_k_m.gguf` and start the server in one terminal. Adjust the model path and device for your system. Use `llama-server --list-devices` to find the available devices.

```sh
llama-server --model qwen2.5-1.5b-instruct-q4_k_m.gguf --alias qwen2.5-1.5b-instruct-q4_k_m --host 127.0.0.1 --port 18763 --ctx-size 8192 --parallel 4 --device Vulkan1 --n-gpu-layers 99
```

Run the evaluation in another terminal.

```sh
git clone https://github.com/YxChen02/voiceops-bench.git
cd voiceops-bench
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b

python evaluate_llm.py --data task-specific-datasets/banking_data --model qwen2.5-1.5b-instruct-q4_k_m --port 18763 --workers 4
python annotate.py --model qwen2.5-1.5b-instruct-q4_k_m --port 18763
python annotation_audit.py runs/model_predictions.jsonl
```

The baseline, cleanup regression, and demo annotation audit can be run without a model server.

```sh
python voiceops.py --data task-specific-datasets/banking_data
python quality_regression.py --data task-specific-datasets/banking_data
python annotation_audit.py demo_predictions.jsonl
```

## Data

BANKING77 contains 77 English banking intents, with 10,003 training examples and 3,080 test examples in the original split. The project preserves that split and selects **531 training examples and 160 test examples** across four intents. The upstream `banking_data/train.csv` and `banking_data/test.csv` files store the customer message in `text` and the reference label in `category`. The data is distributed under CC BY 4.0. [Dataset documentation](https://github.com/PolyAI-LDN/task-specific-datasets#banking) · [Original paper](https://arxiv.org/abs/2003.04807)

The bilingual audit uses 10 manually written reference cases. `needs_review` is used when the missing item or the transaction channel is unclear. The script verifies that the evidence excerpt occurs in the input. Its relevance to the label is a separate judgment for the reviewer.

## Repository files

- `evaluate_llm.py` evaluates zero-shot and four-example prompts on the same test set, then saves predictions, metrics, and review flags. [LLM evaluation](evaluate_llm.py)
- `annotate.py` sends masked messages to the local model and saves predicted labels and excerpts. It also defines the labeling prompt used by the evaluation. [Annotation client](annotate.py)
- `annotation_audit.py` joins predictions to reference cases by ID and produces the audit counts and review queue. [Audit script](annotation_audit.py)
- `voiceops.py` reads BANKING77, defines the cleaning rules, and runs the 5-NN comparison. [Data preparation and baseline](voiceops.py)
- `quality_regression.py` adds known duplicate, conflicting, and test-overlap records to check the cleaning rules. [Cleanup regression](quality_regression.py)
- `edge_cases.jsonl` contains one reference case per line, with an ID, message, label, and annotation rationale. [Bilingual reference cases](edge_cases.jsonl)
- `demo_predictions.jsonl` contains hand-written predictions for demonstrating the audit without a model server. [Audit demo input](demo_predictions.jsonl)
- `results/qwen2.5-report.json` records the real run, including model provenance, metrics, confusion counts, and bilingual audit results. [Published run report](results/qwen2.5-report.json)
- `results/qwen2.5-bilingual-predictions.jsonl` contains the 10 predictions emitted by Qwen for the bilingual reference cases. [Published model output](results/qwen2.5-bilingual-predictions.jsonl)
- `README.md` documents the project and its reproduction steps. [Project documentation](README.md)
- `.gitignore` excludes generated runs, the cloned dataset repository, Python caches, and local environment files. [Git ignore rules](.gitignore)

## Generated files

- `runs/llm/report.json` contains both LLM evaluations, per-intent F1, confusion counts, the four prompt examples, and review totals.
- `runs/llm/zero_shot-predictions.json` contains each zero-shot prediction, its evidence, reference label, and review flags.
- `runs/llm/few_shot-predictions.json` contains the corresponding records for the prompt with four examples.
- `runs/model_predictions.jsonl` contains model predictions for the bilingual cases.
- `runs/annotation-audit.json` contains bilingual audit counts and the records that need review.
- `runs/local/report.json` contains the 5-NN baseline results and classification errors.
- `runs/local/pool-v1.json` contains the baseline training pool after excluding matches with the test set.
- `runs/local/pool-v2.json` contains the training pool after also removing duplicates and excluding conflicting labels.
- `runs/local/review.json` contains the IDs of removed training records and their removal reasons.
- `runs/regression.json` contains the outcomes for the three injected data defects.
