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

## 在本地跑一遍

在项目根目录运行下面的命令。三个实验脚本都只用 Python 标准库，运行环境为 Python 3.10 或更新版本。

```powershell
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b

python voiceops.py --data task-specific-datasets/banking_data
python quality_regression.py --data task-specific-datasets/banking_data
python annotation_audit.py demo_predictions.jsonl
```

- `runs/local/report.json` 有数据文件哈希、两版分数、混淆矩阵和错例。同目录的 `pool-v1.json`、`pool-v2.json` 和 `review.json` 可用来追查训练数据的变动。
- `runs/regression.json` 记录三种注入问题的处理结果。
- `runs/annotation-audit.json` 记录标注检查结果和逐条复核原因。

有支持 JSON 输出的本地 Chat Completions 服务时，可以换成真实模型预测。把 `MODEL_ID` 换成已加载的模型名，服务端口有变化时加上 `--port`（默认 11434）。

```powershell
python annotate.py --model MODEL_ID
python annotation_audit.py runs/model_predictions.jsonl
```
