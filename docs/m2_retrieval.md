# M2 — 混合检索、RRF、Rerank 与 LlamaIndex 全模式

> **学习入口**：M2 检索链路、模式对比、验收集中在此。  
> **指标演进表**（Recall@5 / P95）：[retrieval_modes.md](./retrieval_modes.md)。  
> **操作命令**：[COLLABORATION.md](./COLLABORATION.md) §3.7.1。  
> **下游 M3**：Agent 固定用 `hybrid_rerank`，见 [m3_agent.md](./m3_agent.md)。

---

## 1. M2 解决什么问题？

| 里程碑 | 关注点 | 典型问题 |
|--------|--------|----------|
| **M1** | 数据进索引 | ingest 后 Milvus/OpenSearch 能否命中？ |
| **M2** | 检索策略 | 向量、BM25、混合、Rerank 谁更好？LlamaIndex 各模式如何对比？ |
| **M3** | Agent | 在 M2 最优链路上加改写、生成、拒答 |

M2 **不调用 LLM**（`sub_question` 等可扩展 LLM）；验收看 **Recall@5** 与 **P95 延迟**。

---

## 2. 模块与文件地图

```
apps/retrieval/core.py              ← vector_search / bm25_search / ChunkHit
apps/retrieval/hybrid/merge.py      ← hybrid_retrieve（双路 + RRF）
apps/retrieval/hybrid/rrf.py        ← reciprocal_rank_fusion
apps/retrieval/langchain/hybrid_chain.py  ← retrieve_context 主入口
apps/retrieval/rerank/bge_reranker.py     ← BGE CrossEncoder rerank
apps/retrieval/llamaindex/*.py      ← Vector/Summary/Tree/Graph/Router/SubQuestion
apps/gateway/main.py                ← POST /v1/search 多 mode 分发
scripts/verify_m2.py                ← 10 题 golden × 5 模式对比
data/eval/m2_golden.jsonl           ← M2 评测集（question + doc_ids）
tests/test_rrf.py                   ← RRF 单元测试
deploy/profiles/dev-single-node.yaml  ← retrieval.* / rerank.*
```

---

## 3. 生产主链路：hybrid_rerank

M3 Agent 与 Gateway 默认生产路径均为 **hybrid → RRF → BGE rerank**。

```mermaid
flowchart TD
    Q[query] --> V[vector_search<br/>Milvus bge-m3]
    Q --> B[bm25_search<br/>OpenSearch]
    V --> RRF[RRF 融合<br/>rrf_k=60]
    B --> RRF
    RRF --> Rel1[release_embedder<br/>卸载 embedder]
    Rel1 --> RR[BGE reranker<br/>CrossEncoder CPU]
    RR --> Rel2[release_reranker]
    Rel2 --> TopN[top rerank_top_n=5]
```

### 3.1 各阶段说明

| 阶段 | 存储 | 模型 | top_k 来源 |
|------|------|------|------------|
| Vector | Milvus | bge-m3（CPU） | `retrieval.vector_top_k`（20） |
| BM25 | OpenSearch | 内置 BM25 | `retrieval.bm25_top_k`（20） |
| RRF | 内存 | 无 | 融合后取 `rerank_top_n * 3` 条进 rerank |
| Rerank | CPU | bge-reranker-v2-m3 | 输出 `rerank.top_n` / `rerank_top_n`（5） |

### 3.2 RRF 公式（通俗）

两路排名列表里，每个 chunk 得分 += `1 / (k + rank)`，`k` 默认 60。  
**直觉**：在 vector 和 BM25 都靠前的 chunk 总分更高，缓解单路偏科。

### 3.3 exclusive 内存（与 M3 相同）

16GB RAM 不能同时常驻 embedder 与 reranker：

```mermaid
flowchart LR
    E[embedder 加载] --> V[vector 检索]
    V --> RRF[RRF]
    RRF --> X[release_embedder]
    X --> R[reranker 加载]
    R --> Out[top_n hits]
    Out --> Y[release_reranker]
```

**勿改 release 逻辑**（防 OOM）。`hybrid_rerank` P95 在本机可达 **数秒～十余秒**（含两次模型加载）。

---

## 4. 检索模式一览

### 4.1 LangChain 路径（生产 + verify_m2 前四模式）

| mode | 路径 | rerank | 适用场景 |
|------|------|--------|----------|
| `vector` | Milvus 语义 | 否 | 现象描述、口语化问法 |
| `bm25` / `keyword` | OpenSearch 关键词 | 否 | 故障码、型号、精确词 |
| `hybrid` | RRF 融合 | 否 | 对比 RRF 增益 |
| **`hybrid_rerank`** | RRF + BGE | **是** | **M3 默认 / M2 验收口径** |

### 4.2 LlamaIndex 路径（研究 / Gateway 扩展 mode）

| mode | 模块 | 说明 |
|------|------|------|
| `vector` | `vector_engine.py` | 封装 `core.vector_search` |
| `bm25` | `keyword_engine.py` | 封装 `core.bm25_search` |
| `summary` | `summary_engine.py` | 章节级 summary 索引粗召回 |
| `tree` | `tree_engine.py` | 手册目录树检索 |
| `graph` | `graph_engine.py` | 部件/故障关系图谱 |
| `router` | `router_engine.py` | 规则路由：故障码→keyword，否则 hybrid_rerank |
| `sub_question` | `subquestion/` | 复杂问题拆子问 + 多工具 RRF |

**Router 规则**（`router_engine.py`）：匹配 `E01`、`ALM-101`、`故障码 xxx` 等 → 优先 BM25；否则走 hybrid_rerank。

### 4.3 双编排分工

```mermaid
flowchart TB
    GW[Gateway /v1/search]
    GW --> LC[LangChain hybrid_chain<br/>生产主链]
    GW --> LI[LlamaIndex engines<br/>模式研究/A-B]
    LC --> M3[M3 Agent hybrid_search]
```

| 框架 | M2 角色 |
|------|---------|
| **LangChain** | hybrid + RRF + rerank，M3 生产链 |
| **LlamaIndex** | 七种 QueryEngine；**graph** 已接 `relations.yaml` 1-hop 扩展 |

### 4.4 LlamaIndex 七种引擎架构

```mermaid
flowchart TB
    subgraph Gateway分发
        SEARCH[POST /v1/search<br/>mode参数]
    end
    
    SEARCH --> ModeSelect{mode选择}
    
    ModeSelect -->|vector| VE[Vector Engine<br/>封装core.vector_search]
    ModeSelect -->|bm25/keyword| KE[Keyword Engine<br/>封装core.bm25_search]
    ModeSelect -->|hybrid| HE[Hybrid Engine<br/>RRF无rerank]
    ModeSelect -->|hybrid_rerank| HRE[HybridRerank Engine<br/>RRF+BGE]
    ModeSelect -->|summary| SE[Summary Engine<br/>章节级粗召回]
    ModeSelect -->|tree| TE[Tree Engine<br/>目录树检索]
    ModeSelect -->|graph| GE[Graph Engine<br/>图谱1-hop扩展]
    ModeSelect -->|router| RE[Router Engine<br/>规则路由]
    ModeSelect -->|sub_question| SQE[SubQuestion Engine<br/>问题分解]
    
    VE & KE & HE & HRE --> Core[core.py<br/>Milvus+OpenSearch]
    GE --> GraphStore[relations.yaml<br/>实体关系图谱]
    RE --> RuleCheck{故障码匹配?}
    RuleCheck -->|是| KE
    RuleCheck -->|否| HRE
    
    style Core fill:#ffe1e1
    style GraphStore fill:#e1ffe1
```

**各引擎说明：**

| Engine | 适用场景 | 实现位置 | 是否需LLM |
|--------|---------|----------|----------|
| **Vector** | 语义搜索、口语化问法 | `vector_engine.py` | 否 |
| **Keyword** | 故障码、精确型号 | `keyword_engine.py` | 否 |
| **Summary** | 文档章节级概览 | `summary_engine.py` | 否 |
| **Tree** | 手册目录层级检索 | `tree_engine.py` | 否 |
| **Graph** | 部件/故障关联扩展 | `graph_engine.py` | 否 |
| **Router** | 自动选最佳模式 | `router_engine.py` | 否 |
| **SubQuestion** | 复杂问题拆解 | `subquestion/` | **否**（rule-based；`generator=llm` 可扩展 M6） |

> **注意**：M2 默认全部引擎不调用 LLM；`sub_question` 用规则分解 + 多工具 RRF，`retrieval.sub_question.generator=llm` 预留 vLLM 子问题生成（M6）。

### 4.5 Router Engine 规则逻辑

```mermaid
flowchart TD
    Query[用户query] --> PatternMatch{正则匹配故障码?}
    
    PatternMatch -->|匹配| KeywordSearch[query_keyword<br/>BM25检索]
    PatternMatch -->|不匹配| HybridRerank[retrieve_context<br/>mode=hybrid_rerank]
    
    KeywordSearch --> CountCheck{命中数 ≥ 3?}
    CountCheck -->|是| ReturnKW[返回Top5 keyword结果]
    CountCheck -->|否| HybridRerank
    
    HybridRerank --> ReturnHR[返回hybrid_rerank结果]
    
    style PatternMatch fill:#ffffcc
    style CountCheck fill:#ffffcc
```

**故障码正则模式：**
```python
FAULT_CODE_PATTERN = re.compile(
    r"\b(?:ALM|E|F)[-_]?\d{2,4}\b|\b(?:故障码|报警码)\s*[A-Z0-9-]+\b",
    re.IGNORECASE,
)
```

示例匹配：`E01`, `ALM-101`, `故障码 E1024`

### 4.6 Graph Engine 扩展流程

```mermaid
flowchart TD
    Start[query_graph] --> Seed[hybrid_retrieve种子检索<br/>top_k=10]
    Seed --> Catalog[读取全部chunks<br/>按doc_id分组]
    
    Catalog --> EntityMatch[match_entity_ids<br/>提取实体ID]
    EntityMatch --> Expand[expand_doc_ids<br/>图谱1-hop扩展]
    
    Expand --> MergeDoc[合并图谱关联文档<br/>score=base*0.85]
    Seed --> MergeSibling[合并同文档兄弟chunk<br/>score=hit*0.9]
    
    MergeDoc --> Rank[按score降序排列]
    MergeSibling --> Rank
    Rank --> TopK[返回Top K结果]
```

**扩展策略：**
1. **图谱边关联**：通过 `relations.yaml` 找到相关文档
2. **同文档兄弟**：同一文档的其他chunk作为补充

### 4.7 SubQuestion Engine 流程

```mermaid
flowchart TD
    Q[复合 query] --> Gen[RuleBasedQuestionGenerator<br/>规则拆分 + 工具路由]
    Gen --> SQ1[子问1 → hybrid]
    Gen --> SQ2[子问2 → keyword]
    Gen --> SQ0[可选：原问句 → hybrid]
    SQ1 & SQ2 & SQ0 --> Retrieve[各工具独立检索]
    Retrieve --> RRF[RRF 融合]
    RRF --> TopK[Top K hits<br/>retriever=sub_question]
```

**配置**（`deploy/profiles/dev-single-node.yaml` → `retrieval.sub_question`）：

| 键 | 默认 | 说明 |
|----|------|------|
| `generator` | `rule_based` | `llm` 为 M6 预留（当前 NotImplemented） |
| `min_subquestion_len` | 4 | 拆分后子问最短字符数 |
| `include_original` | true | 复合问句时额外检索完整原问 |

---

## 5. Gateway API：`POST /v1/search`

```json
{
  "query": "P-101 出口压力正常范围",
  "mode": "hybrid_rerank",
  "top_k": 5
}
```

| 字段 | 说明 |
|------|------|
| `mode` | 见 §4；默认 `hybrid_rerank` |
| `top_k` | 返回条数上限 1–50 |

响应 `hits[]`：`chunk_id`, `doc_id`, `source_file`, `title`, `text`, `score`, `retriever`。

**工业约定（Retrieve / Generate 分离）**：`/v1/search` **永远只返 hits**，不含 LLM 合成答案。`mode=sub_question` 仅表示多路检索 + RRF；完整拆问+合成走 **`POST /v1/chat`**（`retrieval_mode=sub_question`），见 [plans/subquestion-complete-roadmap.md](./plans/subquestion-complete-roadmap.md) §2.3。

**Windows**：用 `curl.exe` + UTF-8 JSON 文件，见 COLLABORATION §3.7.1。

---

## 6. Profile 配置（`retrieval` / `rerank` / `embedding`）

| 路径 | dev 默认 | 含义 | 何时改 |
|------|----------|------|--------|
| `retrieval.vector_top_k` | 20 | Milvus 召回数 | 增大提 recall、增延迟 |
| `retrieval.bm25_top_k` | 20 | OpenSearch 召回数 | 同上 |
| `retrieval.rrf_k` | 60 | RRF 平滑常数 | 越小 top 排名权重越大 |
| `retrieval.rerank_top_n` | 5 | 最终进下游 chunk 数 | M3 context 默认同源 |
| `rerank.top_n` | 5 | rerank 输出条数 | 与上对齐 |
| `embedding.device` | cpu | bge-m3 设备 | 6GB GPU 留给 LLM |
| `rerank.device` | cpu | reranker 设备 | 同上 |

---

## 7. 验收 `verify_m2.py`

### 7.1 评测逻辑

- 读 `data/eval/m2_golden.jsonl`（10 题）
- 每题：某 mode 检索 Top5，`source_file` 是否含期望 `doc_ids` 之一 → 命中
- **M2 通过线**：`hybrid_rerank` ≥ **8/10**

### 7.2 对比的 5 种 mode

| verify 名称 | 实现 |
|-------------|------|
| vector | `retrieve_context(..., mode=vector, rerank=False)` |
| bm25 | `mode=bm25` |
| hybrid | `mode=hybrid, rerank=False` |
| hybrid_rerank | `mode=hybrid_rerank` |
| router | `query_router` |

**扩展 4 模式**（`--extended`，含 sub_question，均无 LLM）：

| verify 名称 | 实现 |
|-------------|------|
| graph | `query_graph(top_k=5)` |
| summary | `query_summary(top_k=5)` |
| tree | `query_tree(top_k=5)` |
| sub_question | `query_subquestion(top_k=5)` |

### 7.3 命令参数

| 参数 | 默认 | 作用 |
|------|------|------|
| `--golden` | `data/eval/m2_golden.jsonl` | 评测集路径 |
| `--output` | `reports/m2_verify.json` | JSON 报告 |
| `--write-evolution` | off | 回填 `retrieval_modes.md` 指标表 |

```powershell
# 前提：Compose 中间件 + ingest（M1）+ Gateway 可选（verify 直连 Python API）
python scripts/verify_m2.py --write-evolution
```

**排障**：`WinError 10055` 端口耗尽 → 停 python 进程、sleep 30s 再跑（COLLABORATION §3.7.1）。

### 7.4 golden 文件格式

```json
{"question": "P-101 出口压力正常范围是多少？", "doc_ids": ["pump_p101_manual.md"], "category": "parameter"}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `question` | 是 | 中文问句 |
| `doc_ids` | 是 | 期望命中的 source 文件名（可多个取 OR） |
| `category` | 否 | 题类标签，便于分析 |

与 `golden.jsonl`（RAGAS，含 `ground_truth`）**不是同一文件**。

---

## 8. 与 M1 / M3 的关系

| | M1 | M2 | M3 |
|--|----|----|-----|
| 脚本 | `verify_m1.py` | `verify_m2.py` | `verify_m3.py` |
| 指标 | 向量/BM25 各 ≥8/10 | hybrid_rerank ≥8/10 | 多轮+拒答+引用 |
| LLM | 无 | 无 | 有 |
| API | 直连 core | `retrieve_context` / `/v1/search` | `/v1/chat` |

---

## 9. M2 验收清单

- [ ] M1 ingest 完成 — 见 [m1_ingest.md §10](./m1_ingest.md#10-m1-验收清单)
- [ ] Compose：Milvus + OpenSearch 健康
- [ ] `pytest tests/test_rrf.py -q`
- [ ] `python scripts/verify_m2.py --write-evolution` → hybrid_rerank ≥8/10
- [ ] （可选）curl `/v1/search` 单条自测

---

## 10. 相关文档

- [architecture.md §3–4](./architecture.md) — 双编排与推理层分界
- [apps/retrieval/README.md](../apps/retrieval/README.md) — 目录速查
- [decisions.md](./decisions.md) — embedder/reranker 分时释放
