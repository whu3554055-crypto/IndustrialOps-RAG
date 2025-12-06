# DeepDoc 解析模块（吸收 RAGFlow 思路）

> **M1 当前范围**：仅 `documents.py` 加载 **md/txt**；PDF/表格见本文「后续计划」。  
> **学习 hub**：[docs/m1_ingest.md](../../docs/m1_ingest.md)

## 后续计划

- PDF 版面分析、表格提取
- 故障码表按行切块
- 图片页 OCR（多模态 POC，见 `../multimodal/`）

实现后仍写入同一 Milvus + OpenSearch 双索引 schema。
