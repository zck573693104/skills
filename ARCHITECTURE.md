# DeepAgent 架构设计 (v2.0)

## 🏗️ 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      DeepAgent v2.0                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Memory     │    │  ReActLoop   │    │  SkillTool   │  │
│  │              │    │              │    │              │  │
│  │ • Long-term  │◄──►│ • Thought    │◄──►│ • Load L2/L3 │  │
│  │ • Short-term │    │ • Action     │    │ • Select     │  │
│  │ • Episodic   │    │ • Obs        │    │ • Extract    │  │
│  │ • Persist    │    │ • Retry      │    │ • Execute    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         ▲                    ▲                    │          │
│         │                    │                    ▼          │
│         │                    │          ┌──────────────┐    │
│         │                    │          │  WorkBuddy   │    │
│         │                    │          │  Components  │    │
│         │                    │          │              │    │
│         │                    │          │ • Registry   │    │
│         │                    │          │ • Disclosure │    │
│         │                    │          │ • Selector   │    │
│         │                    │          │ • Extractor  │    │
│         │                    │          │ • Runner     │    │
│         │                    │          └──────────────┘    │
└─────────┼────────────────────┼──────────────────┼──────────┘
          │                    │                  │
          ▼                    ▼                  ▼
    ┌──────────┐        ┌──────────┐      ┌──────────┐
    │ User     │        │ LLM      │      │ Skills   │
    │ Input    │        │ API      │      │ Dir      │
    └──────────┘        └──────────┘      └──────────┘
```

---

## 🔄 数据流

### DeepAgent 执行流程

```
用户输入
   │
   ▼
┌─────────────────┐
│  Memory         │ ← 加载历史对话 + 关键事件
│  • Long-term    │
│  • Episodic     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ReActLoop      │ ← 开始循环（最多 8 步）
│  Step 1-N       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Thought        │ ← LLM 推理下一步行动
│  • Reasoning    │   - use_skill
│  • Action Type  │   - ask_user
│  • Parameters   │   - final_answer
└────────┬────────┘
         │
         ├─→ ask_user → 返回追问，等待用户输入
         │
         ├─→ final_answer → 返回最终答案
         │
         └─→ use_skill
                │
                ▼
        ┌─────────────────┐
        │  SkillTool      │
        │  • Load L2/L3   │ ← 渐进式披露
        │  • Select Script│ ← LLM 选择脚本
        │  • Extract Params│ ← LLM 提取参数
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  Check Required │ ← 检查必填参数
        └────────┬────────┘
                 │
          缺失?  ├─Yes─→ 返回追问
                 │
                 No
                 │
                 ▼
        ┌─────────────────┐
        │  Execute Script │ ← 执行脚本（带重试）
        │  • Attempt 1    │
        │  • Attempt 2    │ ← 失败时重新提取参数
        └────────┬────────┘
                 │
          成功?  ├─Yes─→ 记录到 Episodic Memory
                 │        返回 Observation
                 │
                 No
                 │
                 ▼
        ┌─────────────────┐
        │ 连续失败 ≥ 3?   │
        └────────┬────────┘
                 │
          Yes    ├─No─→ 返回 Observation（继续循环）
                 │
                 ▼
          强制终止，给出建议
```

---

## 📦 核心组件详解

### 1. Memory（记忆系统）

```
┌──────────────────────────────────────┐
│           Memory                     │
├──────────────────────────────────────┤
│                                      │
│  Long-term (长期记忆)                │
│  ├─ 最近 20 条对话                   │
│  ├─ 角色: user / assistant           │
│  └─ 持久化到 .memory/memory.json     │
│                                      │
│  Short-term (短期记忆)               │
│  ├─ 本轮 ReAct 步骤链                │
│  ├─ Thought / Observation            │
│  └─ 每轮对话重置                     │
│                                      │
│  Episodic (事件记忆)                 │
│  ├─ 技能调用记录                     │
│  ├─ 用户偏好                         │
│  ├─ 最近 50 个事件                   │
│  └─ 包含时间戳 + 类型 + 数据         │
│                                      │
└──────────────────────────────────────┘
```

**持久化机制**：
- 每次添加长期记忆时自动保存
- 启动时自动加载 `.memory/memory.json`
- 格式：JSON（人类可读）

---

### 2. ReActLoop（推理循环）

```
┌──────────────────────────────────────┐
│         ReActLoop                    │
├──────────────────────────────────────┤
│                                      │
│  状态跟踪:                           │
│  ├─ _step_count: 当前步骤数          │
│  ├─ _done: 是否完成                  │
│  ├─ _final_answer: 最终答案          │
│  ├─ _pending_question: 待追问        │
│  └─ _consecutive_failures: 失败计数  │
│                                      │
│  循环逻辑:                           │
│  ├─ MAX_STEPS = 8 (防止无限循环)     │
│  ├─ 每步调用 LLM 生成 Thought        │
│  ├─ 根据 action_type 分支处理        │
│  └─ 连续失败 3 次强制终止            │
│                                      │
└──────────────────────────────────────┘
```

**Thought 结构**：
```json
{
  "reasoning": "我的推理过程",
  "action_type": "use_skill | ask_user | final_answer",
  "skill_name": "skill名称（可选）",
  "instruction": "给Skill的指令（可选）",
  "question": "追问内容（可选）",
  "answer": "最终答案（可选）"
}
```

---

### 3. SkillTool（工具调用）

```
┌──────────────────────────────────────┐
│          SkillTool                   │
├──────────────────────────────────────┤
│                                      │
│  调用流程:                           │
│  ├─ 1. 加载 Skill 元数据 (L1)        │
│  ├─ 2. 加载详情 (L2/L3)              │
│  ├─ 3. 选择脚本 (LLM)                │
│  ├─ 4. 提取参数 (LLM + Context)      │
│  ├─ 5. 检查必填参数                  │
│  ├─ 6. 执行脚本 (带重试)             │
│  └─ 7. 记录执行历史                  │
│                                      │
│  重试机制:                           │
│  ├─ 最多重试 2 次                    │
│  ├─ 每次重试重新提取参数             │
│  └─ 失败后返回详细错误信息           │
│                                      │
└──────────────────────────────────────┘
```

**参数传递模式**：
- JSON 字符串：`python script.py '{"query":"..."}'`
- Flag 参数：`python script.py --followup`
- Key-Value：`python script.py --city 北京`
- 位置参数：`python script.py 北京`

---

### 4. WorkBuddy Components（复用组件）

```
┌──────────────────────────────────────┐
│     WorkBuddy 组件（被 DeepAgent     │
│      和 WorkBuddy 共同使用）          │
├──────────────────────────────────────┤
│                                      │
│  SkillRegistry                       │
│  ├─ 扫描 skills 目录                 │
│  ├─ 解析 SKILL.md frontmatter        │
│  ├─ 维护 L1 元数据索引               │
│  └─ 提供 summary_for_llm()           │
│                                      │
│  SkillDisclosure                     │
│  ├─ L2: 加载 SKILL.md 全文           │
│  ├─ L3: 解析脚本列表 + 参数定义      │
│  ├─ L3: 加载 references/ assets/     │
│  └─ 渐进式披露（按需加载）            │
│                                      │
│  ScriptSelector                      │
│  ├─ 单脚本直接返回                   │
│  ├─ 多脚本用 LLM 选择                │
│  └─ 支持 NONE 选项（无需脚本）        │
│                                      │
│  ParamExtractor                      │
│  ├─ 综合 SKILL.md + references       │
│  ├─ LLM 提取/推断参数                │
│  ├─ 支持 flag 参数（bool 类型）      │
│  └─ 自动填充必填参数（基于上下文）    │
│                                      │
│  ScriptRunner                        │
│  ├─ 支持 .py / .sh / .js             │
│  ├─ 智能判断传参方式                 │
│  ├─ UTF-8 编码处理                   │
│  └─ 超时控制（120s）                 │
│                                      │
└──────────────────────────────────────┘
```

---

## 🔑 关键设计决策

### 1. 为什么选择 ReAct 而非 Plan-and-Execute？

| 维度 | ReAct | Plan-and-Execute |
|------|-------|------------------|
| **灵活性** | ✅ 高（动态调整） | ❌ 低（固定计划） |
| **容错性** | ✅ 强（可纠错） | ❌ 弱（一步错全错） |
| **复杂度** | ⚠️ 中 | ✅ 简单 |
| **Token 消耗** | ⚠️ 较高 | ✅ 较低 |
| **适用场景** | 不确定任务 | 明确任务 |

**结论**：DeepAgent 选择 ReAct 以应对复杂、不确定的任务。

---

### 2. 为什么需要三层记忆？

- **Long-term**：保持对话连贯性（跨会话）
- **Short-term**：支撑 ReAct 推理（单轮内）
- **Episodic**：记录关键事件（用于分析和优化）

**类比人类记忆**：
- Long-term ≈ 长期记忆（经验、知识）
- Short-term ≈ 工作记忆（当前思考）
- Episodic ≈ 情景记忆（特定事件）

---

### 3. 为什么设置重试机制？

**问题场景**：
1. LLM 第一次提取的参数可能有误
2. 脚本执行可能因网络波动失败
3. 参数格式可能不符合脚本要求

**解决方案**：
- 第 1 次失败 → 重新提取参数 → 第 2 次尝试
- 仍失败 → 返回错误，让 LLM 决定下一步

**收益**：
- 提高成功率（约 20-30% 的失败可通过重试解决）
- 减少用户挫败感
- 避免无效的人工干预

---

### 4. 为什么限制连续失败次数？

**风险**：
- ReAct 循环可能陷入死循环
- 反复调用同一失败的 Skill
- 浪费 Token 和时间

**保护机制**：
- 连续失败 3 次 → 强制终止
- 给出明确的排查建议
- 让用户决定下一步

---

## 🎯 性能指标

### Token 消耗估算

| 组件 | 单次调用 Token | 说明 |
|------|---------------|------|
| ReAct Thought | ~500 | 推理 + JSON 输出 |
| Skill Selection | ~300 | 从多个脚本中选择 |
| Param Extraction | ~800 | 综合文档 + 提取参数 |
| Script Execution | 0 | 本地执行，无 Token |
| **总计（单步）** | **~1600** | 平均情况 |

**示例**：
- 3 步完成任务 → ~4800 Token
- 8 步（上限） → ~12800 Token

### 响应时间估算

| 阶段 | 耗时 | 说明 |
|------|------|------|
| LLM 推理（Thought） | 2-5s | 取决于模型和网络 |
| Skill 加载 | <0.1s | 本地文件读取 |
| 参数提取 | 2-5s | LLM 调用 |
| 脚本执行 | 1-10s | 取决于脚本复杂度 |
| **总计（单步）** | **5-20s** | 平均情况 |

---

## 🔐 安全考虑

### 1. 脚本执行安全
- ✅ 超时控制（120s）
- ✅ 捕获 stdout/stderr
- ✅ UTF-8 编码处理
- ⚠️ **注意**：脚本在本地运行，需确保来源可信

### 2. 记忆数据安全
- ✅ 本地存储（不上传云端）
- ✅ JSON 格式（易于审计）
- ⚠️ **注意**：敏感信息会保存在 `.memory/memory.json`

### 3. API Key 管理
- ✅ 通过环境变量 `AI_KEY` 传递
- ⚠️ **注意**：不要硬编码在代码中

---

## 🚀 扩展方向

### 短期优化
1. **向量检索**：为 episodic memory 添加语义搜索
2. **缓存机制**：缓存常用的 Skill 执行结果
3. **并行执行**：支持无依赖的 Skill 并行调用

### 长期规划
1. **多 Agent 协作**：多个 DeepAgent 协同完成复杂任务
2. **技能学习**：从执行历史中自动优化参数提取
3. **可视化调试**：WebUI 展示 ReAct 思维链

---

## 📚 参考资料

- [ReAct Paper](https://arxiv.org/abs/2210.03629) - Reasoning and Acting in Language Models
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/) - LangChain Agent 框架
- [OpenClaw Skills](https://github.com/openclaw/openclaw) - Skill 系统设计
