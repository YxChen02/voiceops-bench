# VoiceOps-Bench

面向行业垂直模型数据运营实习的银行客服意图分类项目。以 BANKING77 的英文提问为基础，跟踪数据治理、标注复核和固定测试集评测。中英边界案例单独记录来源与判定理由。

## 复现

需要 Python 3.10+，基础实验仅依赖标准库。

```powershell
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b
python voiceops.py --data task-specific-datasets/banking_data --out runs/local
```

脚本生成两个示例池版本、复核清单和评测报告。报告保存输入文件 SHA-256、混淆矩阵和逐条误判。文本会替换形似邮箱或长数字串的片段，规则覆盖范围限于这两类模式。

## 标注规范

- `lost_or_stolen_card`：明确遗失或被盗的是实体银行卡。
- `lost_or_stolen_phone`：明确遗失或被盗的是手机。
- `card_payment_not_recognised`：用户明确表示某笔刷卡或商户交易未经授权。
- `cash_withdrawal_not_recognised`：用户明确表示某笔 ATM 或现金取款未经授权。
- `needs_review`：缺少遗失对象或交易渠道，或者同时存在多个有效意图且无法确定主诉求。记录支持判定的原文和需要追问的信息。

`edge_cases.jsonl` 是独立编写的质检样例，其中的模拟转写错误带有显式标记。BANKING77 官方测试集标签保留用于对照。有争议的标签应进入复核清单，并通过新版本记录修订理由。

## 第一次实验

在固定测试集上，用同一个基于字符三元组与词集合的五近邻分类器，对比原始示例池和清洗后的示例池。两组使用同样的规则排除与测试集规范化文本重复的样本。

531 条训练样本在这四个类别内没有触发规范化去重或冲突规则，两组 Macro-F1 都是 0.9564。这个实验说明当前规则在该子集没有改变示例池，无法据此估计语义去重的效果。

错例中有一条只提到 “a transaction … I didnt make”，缺少商户交易或取款渠道。另一条 “Someone stole my cards!” 的公开标签是手机遗失，值得人工复核。两类错误分别提示了意图证据缺失和疑似标签冲突。

数据来自 [PolyAI BANKING77](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data)，采用 CC BY 4.0。仓库以脚本读取上游 CSV。

## LLM 初标质检

将待标文本与上面的标注规范交给模型。对每条文本要求输出一行 JSON，包含原始 `id`、`label` 和逐字摘录的 `evidence`。只提供待标文本和 ID，参考答案及判定理由留给质检阶段。

```powershell
python annotation_audit.py demo_predictions.jsonl
```

示例预测是手工构造的质检输入，包含错标、无原文证据和漏标。脚本核对标签和证据，按 ID 对照参考答案，并把歧义或冲突样本写进复核队列。证据出现在原文只验证可追溯性，是否支持标签仍需人工判断。实际模型输出可以直接替换示例文件。

## 数据质量回归

在 BANKING77 训练示例池中加入三个已知问题：大小写与空白变体、同文本异标签、跨训练与测试集重复。检查每条记录的处理原因，并验证其余训练样本完整保留。注入样本仅用于验证治理规则。

```powershell
python quality_regression.py --data task-specific-datasets/banking_data
```

当前结果为 3 条注入记录均进入队列，另有 1 条原始记录因与注入标签冲突而一起隔离。可在 `runs/regression.json` 查看逐条原因。

如已启动支持 JSON 输出的本地 Chat Completions 服务，可直接运行初标。将 `MODEL_ID` 换成服务已加载的模型 ID，按需指定 `--port`。请求发送到本机，模型只接收脱敏后的待标文本。

```powershell
python annotate.py --model MODEL_ID
python annotation_audit.py runs/model_predictions.jsonl
```
