# 分支说明：feature/auto-evaluation-optimization

## 概述

本分支实现了从研究到生产的完整文档体系，并规划了自动化评测与优化的四阶段升级路线。

## 主要变更

### 1. 文档更新（3个文件）

#### docs/architecture.md
**新增内容**：
- 3.2节：双框架协作架构图（Mermaid流程图）
- 3.3节：LangChain生产链路详细流程（含6次LLM调用路径）

**价值**：清晰展示LangChain和LlamaIndex如何协作，以及生产环境的完整请求流程。

#### docs/m2_retrieval.md
**新增内容**：
- 4.4节：LlamaIndex七种引擎架构图
- 4.5节：Router Engine规则逻辑（故障码匹配）
- 4.6节：Graph Engine扩展流程（图谱1-hop扩展）

**价值**：详细说明每种检索模式的实现原理和适用场景。

#### docs/research-to-production.md（新建）
**核心内容**：
- 半自动化流程详解（自动化部分 vs 人工部分）
- 研究成果输出机制（评测框架、Golden Dataset、指标演进）
- 三种应用路径（固定模式、动态路由、配置调优）
- 完整闭环流程图
- 实际案例演示
- 最佳实践总结

**价值**：为团队提供从研究到生产的标准操作指南。

### 2. 开发计划（1个文件）

#### docs/plans/auto-evaluation-roadmap.md（新建）
**四阶段规划**：

**Phase 1: 评测所有7种模式**（1-2周）
- 扩展verify_m2.py支持summary/tree/graph模式
- 扩充Golden Dataset到40-80题
- 生成7种模式对比报告

**Phase 2: 基于规则的自动调参**（3-4周）
- 开发auto_tune_params.py（网格搜索）
- 实现bayesian_optimize.py（贝叶斯优化）
- CI/CD集成，每周自动调优

**Phase 3: A/B测试框架**（6-8周）
- 实现ABTestRouter（流量分流）
- 数据库Schema设计（实验数据记录）
- 统计分析引擎（显著性检验）
- 自动决策与部署

**Phase 4: 强化学习自动优化**（3-6月）
- Multi-Armed Bandit基础版
- Contextual Bandit（个性化策略）
- Deep RL（长期目标）

**价值**：清晰的实施路线图，包含技术方案、验收标准、风险评估和时间线。

## 如何使用

### 查看文档

1. **理解当前架构**：
   ```bash
   open docs/architecture.md
   ```

2. **学习检索模式**：
   ```bash
   open docs/m2_retrieval.md
   ```

3. **掌握优化流程**：
   ```bash
   open docs/research-to-production.md
   ```

4. **了解未来规划**：
   ```bash
   open docs/plans/auto-evaluation-roadmap.md
   ```

### 开始实施Phase 1

```bash
# 1. 确保在当前分支
git checkout feature/auto-evaluation-optimization

# 2. 扩展verify_m2.py
# 编辑 scripts/verify_m2.py，添加graph/summary/tree模式

# 3. 扩充Golden Dataset
# 编辑 data/eval/m2_golden.jsonl，增加到40+题

# 4. 运行评测
python scripts/verify_m2.py --extended

# 5. 查看结果
cat reports/m2_verify.json
cat docs/retrieval_modes.md
```

## 关键设计决策

### 为什么采用半自动化而非全自动？

1. **成本考量**：全自动MLOps系统需要大量基础设施投入
2. **复杂度控制**：半自动化更易理解和维护
3. **渐进式升级**：可逐步从半自动过渡到全自动
4. **人工监督**：关键决策仍需人工Review，避免自动化错误

### 为什么分四个阶段？

1. **风险分散**：每个阶段独立验证，降低整体风险
2. **价值递进**：每完成一个阶段都能带来实际收益
3. **学习曲线**：团队可逐步掌握更复杂的技术
4. **资源优化**：根据前期成果决定后续投入

## 下一步行动

### 本周（2026-06-03至2026-06-10）

- [ ] Review本文档和计划
- [ ] 开始Phase 1：扩展verify_m2.py
- [ ] 扩充Golden Dataset到40题

### 本月（2026-06）

- [ ] 完成Phase 1全部任务
- [ ] 启动Phase 2：开发自动调参脚本
- [ ] Review并合并Phase 1代码到main

### 本季度（Q3 2026）

- [ ] 完成Phase 2和Phase 3
- [ ] 生产环境部署A/B测试
- [ ] 开始Phase 4调研

## 相关资源

- **主分支**：`main`
- **当前分支**：`feature/auto-evaluation-optimization`
- **提交信息**：`docs: 添加双框架编排架构和自动化评测路线图`

## 联系方式

如有问题或建议，请：
1. 在GitHub上创建Issue
2. 联系开发团队
3. 参考相关文档

---

**创建日期**：2026-06-03  
**最后更新**：2026-06-03  
**维护者**：开发团队
