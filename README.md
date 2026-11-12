# VoiceOps-Bench

> “Someone stole my cards!”

这条 BANKING77 样本说的是卡被盗，数据集却标成了「手机遗失」。分类器把它判为「银行卡遗失或被盗」，评测报告里仍然记了一次错误。看这类错例时，光看分数很难判断该改哪里。这个项目把原文、预测和原始标签放在一起，方便回到具体样本做复核。

## 先跑一个英文基线

[PolyAI BANKING77](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data) 收录了 77 类英文银行客服提问，官方训练集有 10,003 条，测试集有 3,080 条，按 CC BY 4.0 发布。这个实验沿用官方划分，只选了银行卡遗失、手机遗失、陌生刷卡交易和陌生取款四类，得到 **531 条训练样本、160 条测试样本**。

每来一条测试样本，基线就用词和字符三元组找出文本最相近的五条训练样本，再让这五条的标签投票。两版训练数据都先遮盖邮箱和长数字串，再统一文本格式来检查训练集和测试集有没有重复。清洗版还会按规范化后的文本给训练样本分组。同标签的重复记录留一条，标签冲突的整组送去复核。

**两版 Macro-F1 都是 0.9564，各错了 7 条。** 这 531 条样本没有触发去重或标签冲突规则，两版实际用了同一批数据。为了确认规则遇到问题时会怎么处理，又加了三条已知有问题的记录：一条格式变体、一条同文本异标签、一条与测试集重复。三条都被识别，和注入记录发生标签冲突的那条原始样本也一并隔离。

## 遇到说不清的意图，怎么标？

另一条英文错例只说「账户里有一笔不是我做的交易」。原标签是陌生刷卡交易，基线猜的是陌生取款。原文没交代渠道，所以中英质检样本把这类输入标成 `needs_review`。遗失物没说清，或者一句话里有多个诉求、无法确定主诉求时，也用这个标签。

[中英质检样本](edge_cases.jsonl) 有 10 条，每条都写了判定理由，其中有两条模拟语音转写错误。初标需要返回意图和一段原文证据。质检脚本按 ID 核对标签，检查证据能否在原文中找到，并把疑似错标、漏标和歧义样本列进复核队列。比如「手机被偷了，银行卡在钱包里」里，后一小句确实能从原文摘出来，但它支持不了「银行卡遗失」这个标签。脚本能检查出处，证据是否支持标签还得看上下文。

用 9 条手工构造的预测跑这 10 条样本，**7 条标签匹配且证据通过检查，5 条进入复核队列**，其中有两条的参考标签和示例预测都标成了 `needs_review`。本地 LLM 接口用模拟服务跑通，真实模型的标注表现尚未测量。

## 仓库里的文件怎么读

第一次看这个项目，可以从 `voiceops.py` 开始，先看英文数据怎样进入评测。想了解标注质检，可以直接打开 `edge_cases.jsonl` 和 `demo_predictions.jsonl`，找一对 ID 相同的记录对照看。

**英文分类和清洗**

- [`voiceops.py`](voiceops.py) 是基线入口。它从 PolyAI 的 `banking_data/train.csv` 读取带标签的训练样本，从 `banking_data/test.csv` 读取用于打分的测试样本。两个 CSV 都是 `text`（用户提问）和 `category`（意图名称）两列。脚本筛出项目使用的四个意图、遮盖邮箱和长数字串、比较两个训练池，再生成评测报告。
- [`quality_regression.py`](quality_regression.py) 用来检查清洗规则。它读同一份 BANKING77 数据，在内存里制造三种缺陷，再检查 `voiceops.py` 的清洗函数有没有正确处理每条记录。调整去重或冲突规则后，可以重跑这个脚本看看结果有没有变。

**中英样本、模型初标和质检**

- [`edge_cases.jsonl`](edge_cases.jsonl) 是人工编写的参考样本，一行就是一条记录。`id` 用来对应预测，`text` 是用户原话，`label` 是参考标签，`reason` 解释标注依据。`noise` 字段为 `simulated_asr` 的两条样本模拟了语音转写错误。
- [`demo_predictions.jsonl`](demo_predictions.jsonl) 是手工构造的待检查预测，用来演示质检脚本。每条有 `id`、预测的 `label` 和作为证据的 `evidence`。比如 `edge-02` 在参考文件里标的是手机被盗，示例预测却标成了银行卡遗失。同一个 ID 让脚本能找到这处错标。
- [`annotate.py`](annotate.py) 负责让模型初标。它读取待标样本，把遮盖后的用户原话发给本机模型服务，取回意图和证据，再加上原样本的 ID，写进 `runs/model_predictions.jsonl`。参考标签和理由留在样本文件里，供后面的质检使用。
- [`annotation_audit.py`](annotation_audit.py) 负责检查初标结果。它可以读手工示例，也可以读 `annotate.py` 生成的预测。脚本按 ID 对照参考文件，找出漏标、标签不一致或证据无法在原文中定位的记录，并把歧义样本一起放入复核队列。

**仓库说明**

- [`README.md`](README.md) 就是本页，记录项目的数据来源、实验结果和复现方法。
- [`.gitignore`](.gitignore) 告诉 Git 忽略运行结果 `runs/`、克隆的上游数据仓库 `task-specific-datasets/`、Python 缓存 `__pycache__/` 和本地配置 `.env`。

## 跑完以后看哪些文件

这些是脚本默认生成的文件。想先看评测结果就打开 `report.json`，想顺着一条标注追查问题就打开 `annotation-audit.json`。

- `runs/local/report.json`：记录数据文件哈希、两版 Macro-F1、混淆矩阵和错例。错例含样本 ID、脱敏后的文本、数据集标签和分类预测。
- `runs/local/pool-v1.json`：基线的训练示例池，已排除与测试集重复的文本。
- `runs/local/pool-v2.json`：清洗后的训练示例池，额外处理了训练集内的重复和标签冲突。
- `runs/local/review.json`：记录清洗时移除的训练样本 ID 及原因，可用 ID 找回对应记录。
- `runs/regression.json`：记录注入缺陷后的保留数量，以及进入复核的样本和处理原因。
- `runs/model_predictions.jsonl`：运行本地模型初标后生成，每行是一条带 ID、意图和证据的预测。
- `runs/annotation-audit.json`：汇总质检结果，并逐条列出需要复核的样本、参考标签、预测和触发原因。

## 在本地跑一遍

在项目根目录运行下面的命令。三个实验脚本都只用 Python 标准库，运行环境为 Python 3.10 或更新版本。

```powershell
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b

python voiceops.py --data task-specific-datasets/banking_data
python quality_regression.py --data task-specific-datasets/banking_data
python annotation_audit.py demo_predictions.jsonl
```

有支持 JSON 输出的本地 Chat Completions 服务时，可以换成真实模型预测。把 `MODEL_ID` 换成已加载的模型名，服务端口有变化时加上 `--port`（默认 11434）。

```powershell
python annotate.py --model MODEL_ID
python annotation_audit.py runs/model_predictions.jsonl
```
