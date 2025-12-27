# M7 公开脱敏演示语料（git 跟踪，共 5 篇）

虚构设备与参数，**不含真实客户信息**。ingest 前执行 `seed_demo_corpus.py` → `data/raw/samples/`。

| 文件 | 设备 |
|------|------|
| `pump_p101_manual.md` | 离心泵 P-101 |
| `reactor_r201_sop.md` | 反应釜 R-201 |
| `compressor_sa01_fault_codes.md` | 空压机 SA-01 |
| `heat_exchanger_e301_manual.md` | 换热器 E-301 |
| `conveyor_cv110_sop.md` | 皮带机 CV-110 |

- **M1 验收**：`scripts/verify_m1.py`（10 题，每篇 2 题）  
- **M7 golden**：`data/eval/golden_m7.jsonl.example`（前 10 题与 M1 对齐，`doc_ids` 为 `samples/<file>`）

学习文档：`docs/m7_demo.md`
