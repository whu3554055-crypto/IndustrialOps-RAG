# 系统架构

**M0 详解**（双路径、profile、Compose、K8s）：[m0_infra.md](./m0_infra.md)

## 1. 总览

IndustrialOps-RAG 采用分层微服务形态，Kubernetes 为最终运行环境；本地通过 `dev-single-node` profile 在单节点上启用**全部组件**（通过资源 limits 与 GPU 互斥保证可启动）。

```mermaid
flowchart TB
  subgraph access[接入层]
    UI[Web UI 中文]
    GW[FastAPI Gateway]
  end
  subgraph orch[编排层]
    AG[Agentic Orchestrator]
    LC[LangChain LCEL]
    LI[LlamaIndex Engines]
  end
  subgraph ret[检索层]
    HY[Hybrid RRF]
    MV[(Milvus)]
    OS[(OpenSearch BM25)]
    GR[Graph Store]
    RR[BGE Reranker]
  end
  subgraph inf[推理服务]
    RT[LLM Router]
    VLLM[vLLM]
    TRT[TensorRT-LLM]
    KD[KEDA]
  end
  subgraph store[数据]
    PG[(PostgreSQL)]
    RD[(Redis)]
    MI[(MinIO)]
  end
  subgraph batch[批处理]
    ING[Ingest Job]
    EV[RAGAS CronJob]
    FT[QLoRA Train Job]
  end
  subgraph obs[可观测]
    PR[Prometheus]
    GF[Grafana]
  end
  UI --> GW --> AG
  AG --> LC & LI
  LC & LI --> HY
  HY --> MV & OS & GR --> RR --> RT
  RT --> VLLM & TRT
  KD --> VLLM & TRT
  GW --> PG & RD
  VLLM & TRT --> MI
  ING --> MV & OS & GR
  EV --> HY
  FT --> MI
  PR --> GF
```

## 2. 请求时序（问答）

1. `POST /v1/chat` 携带 `session_id`, `query`
2. Gateway 加载会话历史（PostgreSQL）
3. Agent：query rewrite（多轮指代）
4. Router：选择 LangChain 路径 / LlamaIndex 路径 / 混合
5. Hybrid 检索：Milvus(top_k) + OpenSearch(top_k) → RRF → Rerank(top_n)
6. 可选 Graph 扩展（故障码/部件关系）
7. Prompt 组装：系统提示 + few-shot + CoT 模板 + contexts
8. LLM Router → 当前 active backend（vLLM 或 TRT）
9. Self-check：是否被 context 支持；不支持则拒答或二次检索
10. 响应：答案 + citations + `retrieval_log_id`
11. 异步写入检索日志供排查

**M3 详解**（流程图、拒答、多轮、verify_m3）：[m3_agent.md](./m3_agent.md)

## 3. 双编排分工

### 3.1 框架职责对比

| 框架 | 职责 |
|------|------|
| **LangChain** | 生产主链路：Agent、Tools、LCEL、与 Gateway 集成 |
| **LlamaIndex** | 检索模式研究与对比：Vector/Summary/Tree/Graph/Router/SubQuestion |

两路检索结果可在 Router 层融合或 A/B 评测（见 [m2_retrieval.md](./m2_retrieval.md)）。

**M2 详解**（hybrid_rerank、RRF、verify_m2）：[m2_retrieval.md](./m2_retrieval.md)

### 3.2 双框架协作架构图

```mermaid
flowchart TB
    subgraph 接入层
        UI[Web UI / API Client]
        GW[FastAPI Gateway<br/>POST /v1/chat & /v1/search]
    end
    
    subgraph Agent编排层
        AG[Agentic Orchestrator<br/>run_agentic_rag]
        RW[Query Rewrite<br/>多轮指代消解]
        SC[Self Check<br/>答案忠实度检验]
    end
    
    subgraph 检索路由层
        ROUTER{检索模式路由}
        LC_PATH[LangChain 路径<br/>生产主链路]
        LI_PATH[LlamaIndex 路径<br/>研究/对比]
    end
    
    subgraph LangChain检索
        HYBRID[hybrid_retrieve<br/>RRF融合]
        RERANK[BGE Reranker<br/>重排序]
    end
    
    subgraph LlamaIndex引擎
        VEC[Vector Engine]
        KW[Keyword Engine]
        SUM[Summary Engine]
        TREE[Tree Engine]
        GRAPH[Graph Engine<br/>图谱扩展]
        SUBQ[SubQuestion Engine<br/>问题分解]
        LI_ROUTER[Router Engine<br/>规则路由]
    end
    
    subgraph 数据存储层
        MILVUS[(Milvus<br/>向量索引)]
        OPENSEARCH[(OpenSearch<br/>BM25全文)]
        GRAPHDB[(Graph Store<br/>实体关系)]
    end
    
    subgraph 推理服务层
        LLM_ROUTER[LLM Router]
        VLLM[vLLM<br/>Qwen2.5-7B-AWQ]
        TRT[TensorRT-LLM<br/>可选]
    end
    
    UI --> GW
    GW --> AG
    AG --> RW
    RW --> ROUTER
    ROUTER --> LC_PATH
    ROUTER --> LI_PATH
    
    LC_PATH --> HYBRID
    HYBRID --> RERANK
    
    LI_PATH --> VEC & KW & SUM & TREE & GRAPH & SUBQ & LI_ROUTER
    
    HYBRID --> MILVUS & OPENSEARCH
    GRAPH --> GRAPHDB
    RERANK --> LLM_ROUTER
    VEC & KW --> MILVUS & OPENSEARCH
    
    LLM_ROUTER --> VLLM
    LLM_ROUTER --> TRT
    
    AG --> SC
    SC --> LLM_ROUTER
```

### 3.3 LangChain 生产链路详细流程

M3 Agent 固定使用 `hybrid_rerank` 模式的完整流程：

```mermaid
flowchart TD
    Start([POST /v1/chat]) --> LoadHist[加载会话历史<br/>max_history_turns=3]
    LoadHist --> Rewrite[rewrite_query<br/>LLM调用#1: 多轮指代消解]
    
    Rewrite --> Retrieve[hybrid_search<br/>mode=hybrid_rerank]
    
    subgraph 混合检索过程
        Retrieve --> Vec[Milvus向量检索<br/>top_k=20]
        Retrieve --> BM25[OpenSearch BM25<br/>top_k=20]
        Vec --> RRF[RRF融合<br/>rrf_k=60]
        BM25 --> RRF
        RRF --> Rel1[release_embedder<br/>释放内存]
        Rel1 --> Rerank[BGE Reranker重排<br/>top_n=5]
        Rerank --> Rel2[release_reranker<br/>释放内存]
    end
    
    Rel2 --> ConfCheck{检索置信度检查<br/>score ≥ -2.0?}
    
    ConfCheck -->|否| RefuseLow[拒答<br/>refused=true]
    ConfCheck -->|是| Generate[generate回答<br/>LLM调用#2]
    
    Generate --> SelfChk{self_check_enabled?}
    SelfChk -->|否| ReturnOK[返回答案+citations]
    SelfChk -->|是| AnswerCheck[check_answer_supported<br/>LLM调用#3: 忠实度检验]
    
    AnswerCheck -->|YES| ReturnOK
    AnswerCheck -->|NO| Expand[rewrite expand=true<br/>LLM调用#4: 扩展改写]
    
    Expand --> Retry[二次hybrid_search]
    Retry --> RetryConf{置信度OK?}
    RetryConf -->|否| RefuseRetry[拒答+部分citations]
    RetryConf -->|是| Gen2[generate重答<br/>LLM调用#5]
    
    Gen2 --> Check2[check_answer_supported<br/>LLM调用#6]
    Check2 -->|YES| ReturnOK
    Check2 -->|NO| RefuseFinal[最终拒答]
    
    ReturnOK --> SaveSession[append_turn保存会话]
    RefuseLow & RefuseRetry & RefuseFinal --> SaveRefuse[记录拒答日志]
    
    SaveSession --> End([JSON Response])
    SaveRefuse --> End
```

**关键特点：**
- **正常路径**：3次LLM调用 + 1次CPU检索
- **自检失败重试**：最多6次LLM调用
- **内存优化**：embedder和reranker分时加载（16GB RAM限制）
- **耗时**：本机单次chat约数分钟（含模型加载卸载）

详见 [m3_agent.md](./m3_agent.md)。

## 4. 推理双引擎

| 引擎 | 角色 |
|------|------|
| **vLLM** | 日常开发、动态 batching、OpenAI 兼容 API |
| **TensorRT-LLM** | 编译引擎、低延迟对比、生产路径演示 |

`mutual_exclusive_gpu: true` 时同一时刻仅一个 Deployment 占用 GPU（KEDA 或 Helm 开关切换）。

**M4 详解**（流程图、压测、KEDA、vLLM↔TRT 切换）：[m4_serving.md](./m4_serving.md)

## 5. 数据流（Ingest）

**M1 详解**（流程图、参数、verify）：[m1_ingest.md](./m1_ingest.md)

```
原始文档(PDF/MD/DOCX)
  → deepdoc 解析（RAGFlow 思路：版面/表格）— M1 当前为 md/txt
  → 切块 + 中文 metadata(device_model, fault_code, ...)
  → Embedding(bge-m3) → Milvus
  → 全文/BM25 索引 → OpenSearch
  → 实体关系抽取 → Graph Store
```

## 6. 安全与可用性（逻辑生产）

- liveness / readiness 探针
- PDB：`minAvailable: 1`（推理服务）
- NetworkPolicy：仅 Gateway 访问 Milvus/OpenSearch
- 限流：Gateway 层 QPS（`apps/rate_limit.py` + Redis）
- SLO 文档化：单机为 dev SLO；生产 overlay 目标 99.9%

## 7. 配置入口

- Profile：`deploy/profiles/dev-single-node.yaml`
- Helm values：`deploy/helm/industrial-ops-rag/values-dev-single-node.yaml`
- 环境变量：`.env`（由 `.env.example` 复制）
