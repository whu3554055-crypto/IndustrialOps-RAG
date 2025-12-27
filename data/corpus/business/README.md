# 脱敏后的真实业务语料（本地目录，默认不进 git）

将 **已脱敏** 的 `.md` / `.txt` 放在此目录，勿提交未脱敏原文。

```powershell
# 复制到 ingest 目录（不覆盖 demo 时可改 --dst）
python scripts\seed_demo_corpus.py --src data\corpus\business --dst data\raw\business

# mini ingest（演示：仅 3 篇、小 batch）
python pipelines\ingest\run_ingest.py --input data/raw --max-docs 3 --batch-size 4
```

检查清单见 `docs/m7_demo.md` §5。`data/corpus/demo` 仍保留为仓库内默认演示语料。
