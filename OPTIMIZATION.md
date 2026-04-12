# DeepAgent 框架优化说明 (v2.0)

## 📋 优化概览

本次优化基于 **Deep Agents** 框架的核心理念，对代码进行了全面重构和增强。

---

## ✨ 核心改进

### 1. **增强的记忆系统 (Memory)**

#### 新增功能
- ✅ **三层记忆架构**：
  - `long_term`: 长期对话历史（跨会话持久化）
  - `short_term`: 短期工作记忆（单轮 ReAct 步骤链）
  - `episodic`: 关键事件记录（技能调用、用户偏好等）

- ✅ **持久化存储**：
  - 自动保存对话历史到 `.memory/memory.json`
  - 重启后自动加载历史记忆
  - 支持自定义记忆存储目录

- ✅ **事件追踪**：
  - 记录每次技能调用的详细信息
  - 保留最近 50 个关键事件
  - 可用于分析和调试

#### 代码示例
```python
# 初始化时指定记忆目录
agent = DeepAgent("./skills", memory_dir="./my_memory")

# 自动保存和加载
# 重启后会看到: [Memory] 已加载持久化记忆: 10 条对话, 5 个事件
```

---

### 2. **智能重试机制 (SkillTool)**

#### 新增功能
- ✅ **自动重试**：脚本执行失败时自动重试最多 2 次
- ✅ **参数重提取**：重试时重新调用 LLM 提取参数（可能修正错误）
- ✅ **执行历史**：记录所有成功的技能调用到 Memory
- ✅ **失败保护**：连续失败 3 次后强制终止，避免无限循环

#### 工作流程
```
第1次尝试 → 失败 → 重新提取参数 → 第2次尝试 → 成功/失败
                                              ↓
                                    连续3次失败 → 终止并给出建议
```

#### 代码示例
```python
# SkillTool 内部自动处理重试
result = self.tool.call(skill_name, instruction, context)
# 如果失败，会自动重试并重新提取参数
```

---

### 3. **优化的 ReAct 循环 (ReActLoop)**

#### 新增功能
- ✅ **失败计数追踪**：监控连续失败次数
- ✅ **智能终止**：连续失败 3 次后给出明确建议
- ✅ **状态重置**：用户补充信息后重置失败计数
- ✅ **更详细的日志**：区分成功/失败的 Observation

#### 改进点
```python
# 之前：失败后继续循环，可能无限重试
# 现在：连续失败 3 次后强制终止
if self._consecutive_failures >= 3:
    self._final_answer = "抱歉，多次尝试后仍无法完成任务。请检查：\n..."
    self._done = True
```

---

### 4. **简化的代码结构**

#### workbuddy.py 优化
- ✅ **简化日志输出**：移除冗余的调试信息
- ✅ **LLM 工厂增强**：支持自定义 model 和 temperature
- ✅ **llm_chat 增强**：支持 max_tokens 参数
- ✅ **代码行数减少**：从 951 行优化到 ~940 行（功能不变）

#### 改进对比
```python
# 之前
print(f"[WorkBuddy] 加载 Skill 详情 (L2/L3)...")
print(f"[WorkBuddy] 提取参数: {script.path.name}")
print(f"[WorkBuddy] 执行脚本: {script.path.name}")

# 现在（更简洁）
params = self.extractor.extract(instruction, script, detail)
ok, output = self.runner.run(script, params)
return output if ok else f"❌ {script.path.name} 执行失败:\n{output}"
```

---

### 5. **模块整合与弃用标记**

#### 整合策略
- ✅ **skill_loader.py**：标记为废弃，建议使用 `workbuddy.SkillRegistry`
- ✅ **skill_executor.py**：标记为废弃，建议使用 `workbuddy.ScriptRunner`
- ✅ **统一入口**：所有功能通过 `workbuddy.py` 和 `deep_agent.py` 提供

#### 迁移指南
```python
# 旧代码
from skill_loader import SkillLoader
from skill_executor import SkillExecutor

loader = SkillLoader("./skills")
executor = SkillExecutor("./skills")

# 新代码（推荐）
from workbuddy import SkillRegistry, SkillDisclosure, ScriptRunner

registry = SkillRegistry("./skills")
disclosure = SkillDisclosure()
runner = ScriptRunner()
```

---

## 🎯 架构对比

### WorkBuddy vs DeepAgent

| 特性 | WorkBuddy | DeepAgent |
|------|-----------|-----------|
| **规划方式** | 静态规划（提前生成所有步骤） | 动态决策（每步根据上一步结果决定） |
| **执行模式** | 线性执行（按预定义顺序） | 循环推理（ReAct 循环） |
| **错误处理** | 失败直接返回 | 自动重试 + 参数修正 |
| **用户交互** | 不支持追问 | 主动追问缺失参数 |
| **记忆系统** | 无 | 三层记忆 + 持久化 |
| **适用场景** | 明确的单步/多步任务 | 复杂、不确定的任务 |

---

## 🚀 使用示例

### DeepAgent 基础用法
```python
from deep_agent import DeepAgent

# 初始化 Agent（自动加载持久化记忆）
agent = DeepAgent("./skills")

# 对话（支持多轮追问）
response = agent.chat("帮我分析员工绩效")
# 如果需要追问：
# "[需要追问] 需要以下信息才能继续：年份，请提供。"

response = agent.chat("2025年的数据")  # 自动续接上一轮任务
print(response)
```

### WorkBuddy 基础用法
```python
from workbuddy import WorkBuddy

buddy = WorkBuddy("./skills")

# 单步任务
result = buddy.chat("@weather 查询北京天气")

# 多步任务（自动规划）
result = buddy.chat("先搜索人工智能最新发展，然后分析相关数据")
```

---

## 📊 性能优化

### Token 节省
- ✅ **渐进式披露**：按需加载 Skill 内容，避免一次性注入所有文档
- ✅ **记忆裁剪**：长期记忆只保留最近 10 条对话
- ✅ **上下文压缩**：Observation 限制在 500 字符内

### 执行效率
- ✅ **智能重试**：避免无效重复调用
- ✅ **快速失败**：连续失败 3 次后终止，节省时间
- ✅ **缓存机制**：持久化记忆避免重复学习

---

## 🔧 配置选项

### DeepAgent 配置
```python
# 自定义记忆目录
agent = DeepAgent(
    skills_dir="./skills",
    memory_dir="./custom_memory"  # 默认: ./.memory
)

# 修改最大步骤数（在 ReActLoop 类中）
ReActLoop.MAX_STEPS = 10  # 默认: 8
```

### WorkBuddy 配置
```python
# 自定义 LLM 模型
from workbuddy import make_llm

llm = make_llm(
    model="gpt-4",           # 默认: deepseek-reasoner
    temperature=0.5          # 默认: 0.7
)
```

---

## 🐛 常见问题

### Q1: 如何清除记忆？
```python
# 删除记忆文件
import shutil
shutil.rmtree("./.memory")

# 或在代码中重置
agent.memory.long_term = []
agent.memory.episodic = []
```

### Q2: 重试次数如何调整？
```python
# 在 deep_agent.py 的 SkillTool.call() 方法中
max_retries = 3  # 修改此值（默认: 2）
```

### Q3: 如何查看执行历史？
```python
# 查看关键事件
for event in agent.memory.episodic:
    print(f"{event['timestamp']}: {event['type']}")
    print(f"  数据: {event['data']}")
```

---

## 📝 更新日志

### v2.0 (2026-04-11)
- ✨ 新增三层记忆系统（long_term + short_term + episodic）
- ✨ 新增记忆持久化功能
- ✨ 新增智能重试机制（最多 2 次）
- ✨ 新增连续失败保护（3 次后终止）
- ✨ 新增执行历史记录
- 🔧 简化 workbuddy.py 日志输出
- 🔧 增强 LLM 工厂函数（支持自定义参数）
- 📦 标记 skill_loader.py 和 skill_executor.py 为废弃
- 📝 优化代码注释和文档

---

## 🎓 最佳实践

1. **选择合适的 Agent**：
   - 简单任务 → WorkBuddy（更快、更确定）
   - 复杂任务 → DeepAgent（更灵活、更智能）

2. **利用记忆系统**：
   - 定期清理无用记忆（`.memory` 目录）
   - 重要对话会自动保存，无需手动管理

3. **监控执行日志**：
   - 关注 `[ReAct]` 前缀的日志（DeepAgent）
   - 关注 `[WorkBuddy]` 前缀的日志（WorkBuddy）

4. **处理追问**：
   - DeepAgent 会主动追问缺失参数
   - 直接回复即可续接任务，无需特殊处理

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发环境设置
```bash
# 安装依赖
pip install langchain-openai pyyaml fastapi uvicorn

# 设置 API Key
export AI_KEY="your-api-key"

# 运行 DeepAgent
python deep_agent.py --query "测试查询"

# 运行 WebUI
python deep_agent_server.py
```

---

## 📄 许可证

本项目采用 MIT 许可证。
