# VoiceOps-Bench

基于 BANKING77 的银行客服意图分类与标注质检项目。它复现了从训练数据清洗、版本对照到错例复核的流程，并提供中英样本与本地 LLM 初标接口。

## 用了什么数据

- **公开数据：** [PolyAI BANKING77](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data) 包含 77 类英文银行客服提问，官方训练集 10,003 条、测试集 3,080 条。原始 CSV 的 `text` 是用户提问，`category` 是意图标签。数据按 CC BY 4.0 提供。
- **实验子集：** 保留四类容易混淆的意图，得到 **531 条训练样本、160 条测试样本**。沿用官方训练与测试划分。
- **质检样本：** [edge_cases.jsonl](edge_cases.jsonl) 包含 10 条独立编写的中英边界样本，覆盖遗失对象、交易渠道缺失及模拟语音转写错误。公开数据和质检样本分别用于英文分类与标注流程验证。

## 做了什么

1. **清洗与版本管理。** 统一 Unicode、大小写和空白，替换匹配邮箱或长数字串的片段。两个训练版本都排除与测试集规范化文本重复的记录。清洗版额外去除同标签重复，并将同文本异标签的记录隔离。报告保留输入文件哈希、样本 ID 和处理原因。
2. **固定测试集评测。** 使用词集合与字符三元组的 Jaccard 相似度检索五个最近样本，通过投票预测意图。固定分类器与测试集，对照两个训练版本，输出 Macro-F1、混淆矩阵和逐条错例。
3. **标注质检。** 本地 LLM 接口要求返回意图和原文证据。脚本检查标签、证据和漏标，与参考标签核对后生成复核队列。证据出现在原文只证明可追溯，是否支持标签仍需人工判断。

### 标注口径

- `lost_or_stolen_card`：遗失或被盗的是实体银行卡。
- `lost_or_stolen_phone`：遗失或被盗的是手机。
- `card_payment_not_recognised`：明确是未经授权的刷卡或商户交易。
- `cash_withdrawal_not_recognised`：明确是未经授权的 ATM 或现金取款。
- `needs_review`：缺少遗失对象或交易渠道，或无法确定多个意图中的主诉求。该标签用于中英质检样本。

## 结果是什么

- **英文分类：** 原始版和清洗版各有 531 条训练样本，Macro-F1 均为 **0.9564**，160 条测试样本中各有 **7 条误判**。这一子集没有触发规范化去重或标签冲突规则，两个训练版本相同，因此这次对照无法估计清洗带来的模型收益。
- **数据质量回归：** 注入格式变体、同文本异标签和跨集合重复各一条。规则识别了全部 3 条注入记录，并隔离了 1 条与注入标签冲突的原始记录，最终保留 530 条。
- **中英标注质检：** 对 10 条参考样本提供 9 条手工构造的示例预测，其中 7 条标签匹配且证据通过检查。脚本检出了错标、缺失或无法在原文中找到的证据、漏标，以及需复核的歧义。初标到质检的接口用模拟服务跑通，真实 LLM 的标注准确率尚未测量。

两条值得复核的英文错例：一条只说有笔交易未经授权，缺少区分刷卡与取款的证据。另一条说银行卡被盗，BANKING77 的公开标签却是手机遗失。第一条适合补充「渠道不明」标注规则，第二条适合复核原始标签。

## 复现

在项目根目录使用 Python 3.10 或更新版本。基线、回归实验和示例质检只依赖 Python 标准库。

```powershell
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b

python voiceops.py --data task-specific-datasets/banking_data --out runs/local
python quality_regression.py --data task-specific-datasets/banking_data
python annotation_audit.py demo_predictions.jsonl
```

查看 `runs/local/report.json` 获取分类指标和错例，查看同目录的 `pool-v1.json`、`pool-v2.json` 和 `review.json` 追踪数据版本。回归与标注质检结果分别写入 `runs/regression.json` 和 `runs/annotation-audit.json`。

如已启动支持 JSON 输出的本地 Chat Completions 服务，将 `MODEL_ID` 替换为已加载的模型名。默认端口为 11434，可通过 `--port` 指定。服务收到的输入是脱敏后的待标文本。

```powershell
python annotate.py --model MODEL_ID
python annotation_audit.py runs/model_predictions.jsonl
```

目前的文本去重覆盖规范化后的完全匹配，脱敏覆盖邮箱与长数字串两类模式。中英边界样本用于演示质检，模拟转写样本用于检查标注口径。
