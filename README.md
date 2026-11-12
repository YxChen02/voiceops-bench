# VoiceOps-Bench

基于 BANKING77 的银行客服意图评测与标注质检项目。项目使用四类英文意图建立分类基线，验证去重、标签冲突和数据泄漏检查规则，并用中英边界样本演示模型初标与人工复核流程。

## 快速开始

需要 Git 和 Python 3.10 或更新版本。以下三个实验只使用 Python 标准库。

```powershell
git clone https://github.com/YxChen02/voiceops-bench.git
cd voiceops-bench
git clone https://github.com/PolyAI-LDN/task-specific-datasets.git
git -C task-specific-datasets checkout 57ec275d8078af65b7731c2a98be812d844a6d6b

python voiceops.py --data task-specific-datasets/banking_data
python quality_regression.py --data task-specific-datasets/banking_data
python annotation_audit.py demo_predictions.jsonl
```

## 数据与评测方法

BANKING77 包含 77 类英文银行客服提问，官方训练集有 10,003 条，测试集有 3,080 条。本项目沿用原始划分，选取银行卡遗失或被盗、手机遗失或被盗、未识别的刷卡交易和未识别的取款四类，共 **531 条训练样本和 160 条测试样本**。上游 `banking_data/train.csv` 用于构建训练池，`banking_data/test.csv` 用于评测。两个文件均包含提问文本 `text` 和意图标签 `category`。数据以 CC BY 4.0 发布。[上游数据说明](https://github.com/PolyAI-LDN/task-specific-datasets#banking) · [原始论文](https://arxiv.org/abs/2003.04807)

两个训练池均遮盖邮箱和长数字串，并排除规范化后与测试集完全匹配的记录。清洗版额外合并训练池中同文本、同标签的记录，并隔离同文本、不同标签的记录。分类基线基于词和字符三元组计算 Jaccard 相似度，由最相近的五条训练样本投票。两版使用同一个分类器和测试集。

标注质检另用 10 条人工编写的中英边界样本，其中两条含模拟语音转写错误。遗失对象或交易渠道缺失时，参考标签可以是 `needs_review`。预测需附原文证据，脚本检查证据是否出现在输入中，复核时再判断证据是否支持意图。

## 实验结果

- **分类基线。** 两版训练池各有 531 条样本，Macro-F1 均为 **0.9564**，在 160 条测试样本上各有 7 条误判。该子集未触发训练池内去重或标签冲突规则，两版实际使用相同的训练样本。
- **清洗规则回归。** 向训练池注入三条已知问题记录，分别是格式变体、同文本异标签和跨集合重复。脚本识别了全部三条，并一并隔离了与注入记录冲突的一条原始样本。
- **标注质检。** 对 10 条参考样本提供 9 条手工构造的预测，7 条标签匹配且证据通过检查，5 条进入复核队列。复核队列包含两条正确标为 `needs_review` 的歧义样本。初标接口已用模拟服务验证，真实 LLM 的标注表现尚未测量。

错例 `test:1673` 的文本是 “Someone stole my cards!”。基线判为银行卡被盗，数据集标签为手机遗失。报告保留原文、预测和数据集标签，可据此复核标签是否准确。

## 文件说明

- `voiceops.py` 读取 BANKING77 的训练和测试 CSV，生成两版训练池，并输出评测指标、错例和清洗记录。[分类评测脚本](voiceops.py)
- `quality_regression.py` 复用同一套清洗规则，注入已知问题并检查处理结果。[清洗回归脚本](quality_regression.py)
- `edge_cases.jsonl` 保存中英参考样本，每行包含样本 ID、原文、参考标签和判定理由。字段 `noise` 标记模拟语音转写样本。[标注参考集](edge_cases.jsonl)
- `demo_predictions.jsonl` 保存手工构造的预测，每行包含样本 ID、预测标签和证据，用于演示错标、证据缺失和漏标的检查。[质检示例输入](demo_predictions.jsonl)
- `annotate.py` 将脱敏后的样本文本发送给本机模型服务，把模型返回的意图和证据连同样本 ID 写入预测文件。[模型初标脚本](annotate.py)
- `annotation_audit.py` 按样本 ID 对照参考标签与预测，检查证据、漏标和歧义，并输出汇总和复核队列。[标注质检脚本](annotation_audit.py)
- `README.md` 记录项目范围、实验结果和运行方法。[项目文档](README.md)
- `.gitignore` 排除本地运行结果、上游数据仓库、Python 缓存和 `.env`。[Git 忽略规则](.gitignore)

例如，`edge-02` 的原文说明手机被盗，银行卡仍在钱包里。参考集将其标为手机被盗，示例预测却标为银行卡遗失。质检脚本通过相同的样本 ID 将两条记录对应起来，并将标签分歧写入复核队列。

## 运行产物

- `runs/local/report.json` 包含输入文件哈希、两版 Macro-F1、混淆矩阵和逐条错例。
- `runs/local/pool-v1.json` 保存排除与测试集重复记录后的基线训练池。
- `runs/local/pool-v2.json` 保存额外处理训练池内重复和标签冲突后的训练池。
- `runs/local/review.json` 记录清洗时移除的训练样本 ID 及原因。
- `runs/regression.json` 记录注入缺陷后的保留数量及每条复核记录。
- `runs/annotation-audit.json` 包含质检计数，以及待复核样本的参考标签、预测和触发原因。
- `runs/model_predictions.jsonl` 由本地模型初标生成，保存样本 ID、预测意图和证据。

## 使用本地模型初标

启动支持 JSON 输出的本地 Chat Completions 服务后，将 `MODEL_ID` 替换为服务中的模型名。脚本默认连接 `127.0.0.1:11434`，端口可用 `--port` 修改。

```powershell
python annotate.py --model MODEL_ID
python annotation_audit.py runs/model_predictions.jsonl
```
