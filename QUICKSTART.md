# 🚀 DeepAgent 快速开始指南

## 1️⃣ 环境准备

### 安装依赖
```bash
pip install langchain-openai pyyaml fastapi uvicorn
```

### 设置 API Key
```bash
# Windows PowerShell
$env:AI_KEY="your-api-key-here"

# Linux/Mac
export AI_KEY="your-api-key-here"
```

---

## 2️⃣ 选择你的 Agent

### 🤖 DeepAgent（推荐用于复杂任务）

**特点**：
- ✅ 动态决策，自主纠错
- ✅ 主动追问缺失信息
- ✅ 多轮记忆持久化
- ⚠️ Token 消耗较高

**适用场景**：
- 不确定的复杂任务
- 需要多步推理的任务
- 可能需要用户补充信息的任务

**快速启动**：
```bash
# CLI 模式
python deep_agent.py --query "帮我分析员工绩效并生成报告"

# 交互模式
python deep_agent.py

# WebUI 模式
python deep_agent_server.py
# 浏览器访问: http://localhost:8766
```

---

### ⚡ WorkBuddy（推荐用于简单任务）

**特点**：
- ✅ 静态规划，执行快速
- ✅ 支持多 Skill 协作
- ✅ Token 消耗较低
- ❌ 不支持主动追问

**适用场景**：
- 明确的单步任务
- 参数完整的多步任务
- 对响应速度要求高的场景

**快速启动**：
```bash
# CLI 模式
python workbuddy.py --query "@weather 查询北京天气"

# 交互模式
python workbuddy.py
```

---

## 3️⃣ 使用示例

### DeepAgent 示例

#### 示例 1：基础对话
```python
from deep_agent import DeepAgent

agent = DeepAgent("./skills")

# 第一轮
response = agent.chat("帮我搜索人工智能最新发展")
print(response)

# 第二轮（自动记住上下文）
response = agent.chat("总结一下关键点")
print(response)
```

#### 示例 2：处理追问
```python
agent = DeepAgent("./skills")

# 第一次调用 - Agent 可能会追问
response = agent.chat("帮我分析销售数据")
# 输出: "[需要追问] 需要以下信息才能继续：年份、地区，请提供。"

# 检查是否需要追问
if agent.waiting_for_user:
    print("Agent 需要更多信息...")
    
    # 用户补充信息
    response = agent.chat("2025年，华东地区")
    print(response)  # 继续执行任务
```

#### 示例 3：指定 Skill
```python
# 直接使用 @skill_name 语法
response = agent.chat("@baidu-search 查询 Python 教程")
```

---

### WorkBuddy 示例

#### 示例 1：单步任务
```python
from workbuddy import WorkBuddy

buddy = WorkBuddy("./skills")

# 直接指定 Skill
result = buddy.chat("@weather 查询上海天气")
print(result)
```

#### 示例 2：多步任务
```python
# 自动规划多步骤
result = buddy.chat("先搜索最新手机价格，然后查询物流报价")
# WorkBuddy 会自动：
# 1. 规划步骤
# 2. 执行 baidu-search
# 3. 将结果传给 logistics-sales-agent
# 4. 汇总最终答案
print(result)
```

---

## 4️⃣ 创建自定义 Skill

### Skill 目录结构
```
skills/
└── my-skill/
    ├── SKILL.md              # 必需：Skill 描述文件
    ├── scripts/              # 可选：可执行脚本
    │   └── main.py
    ├── references/           # 可选：参考文档
    │   └── api_docs.md
    └── assets/               # 可选：资源文件
        └── config.json
```

### SKILL.md 模板
```markdown
---
name: my-skill
description: 我的自定义技能描述
tags: [category, keyword]
version: 1.0.0
---

# My Skill

## 功能说明
详细描述这个 Skill 的功能...

## 使用方法
```bash
python scripts/main.py --param1 value1 --param2 value2
```

## 参数说明
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| param1 | str | Yes | - | 参数1说明 |
| param2 | int | No | 10 | 参数2说明 |

## 示例
```bash
python scripts/main.py --param1 "测试" --param2 20
```
```

### 脚本示例（Python）
```python
#!/usr/bin/env python3
"""My Skill 主脚本"""
import sys
import json

def main():
    # 方式1: JSON 参数
    if len(sys.argv) > 1:
        params = json.loads(sys.argv[1])
        param1 = params.get("param1", "")
        param2 = params.get("param2", 10)
    
    # 方式2: argparse
    # import argparse
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--param1", required=True)
    # parser.add_argument("--param2", type=int, default=10)
    # args = parser.parse_args()
    
    # 你的业务逻辑
    result = f"处理结果: param1={param1}, param2={param2}"
    print(result)

if __name__ == "__main__":
    main()
```

---

## 5️⃣ 调试技巧

### 查看日志输出

#### DeepAgent 日志
```
[ReAct] 步骤 1 | action=use_skill
[ReAct] 推理: 用户需要搜索信息，应该使用 baidu-search
[SkillTool] 调用 Skill: baidu-search
[SkillTool] 选中脚本: search.py
[SkillTool] 提取到参数: {'query': '人工智能'}
[ReAct] Observation: 搜索结果...
```

#### WorkBuddy 日志
```
[WorkBuddy] 任务规划中...
[WorkBuddy] 匹配到 Skill: baidu-search
[WorkBuddy] 选中脚本: search.py
[WorkBuddy] 提取到参数: {'query': '人工智能'}
[ScriptRunner] 执行: python scripts/search.py '{"query":"人工智能"}'
```

### 常见问题排查

#### 问题 1：Skill 未被识别
```bash
# 检查 skills 目录结构
ls skills/

# 确认 SKILL.md 存在且有正确的 frontmatter
cat skills/my-skill/SKILL.md | head -10
```

#### 问题 2：参数提取失败
```python
# 查看提取到的参数
print(f"[DEBUG] 提取到参数: {params}")

# 检查 SKILL.md 中的参数定义是否正确
# 确保有 Parameters 表格
```

#### 问题 3：脚本执行超时
```python
# 在 workbuddy.py 中调整超时时间
proc = subprocess.run(cmd, capture_output=True, timeout=300, ...)  # 改为 300s
```

#### 问题 4：记忆未持久化
```bash
# 检查 .memory 目录是否存在
ls -la .memory/

# 查看记忆文件
cat .memory/memory.json
```

---

## 6️⃣ 性能优化建议

### 减少 Token 消耗
1. **精简 SKILL.md**：只保留必要信息
2. **限制 references**：单个文件不超过 3000 字
3. **使用 WorkBuddy**：对于明确任务，优先使用 WorkBuddy

### 提高响应速度
1. **本地缓存**：缓存常用的 LLM 响应
2. **并行执行**：无依赖的 Skill 可并行调用（需自行实现）
3. **简化提示词**：减少 prompt 长度

---

## 7️⃣ 进阶用法

### 自定义 LLM 模型
```python
from workbuddy import make_llm

# 使用不同的模型
llm = make_llm(
    model="gpt-4-turbo",
    temperature=0.5
)

# 在 DeepAgent 中使用
from deep_agent import DeepAgent
agent = DeepAgent("./skills")
agent.llm = llm  # 替换默认 LLM
```

### 访问记忆系统
```python
agent = DeepAgent("./skills")

# 查看长期记忆
for msg in agent.memory.long_term:
    print(f"{msg.role}: {msg.content[:50]}")

# 查看关键事件
for event in agent.memory.episodic:
    print(f"{event['timestamp']}: {event['type']}")
    print(f"  数据: {event['data']}")

# 清除记忆
import shutil
shutil.rmtree("./.memory")
```

### 批量处理
```python
agent = DeepAgent("./skills")

queries = [
    "查询北京天气",
    "搜索人工智能新闻",
    "分析销售数据"
]

for query in queries:
    print(f"\n处理: {query}")
    response = agent.chat(query)
    print(f"结果: {response[:100]}...")
```

---

## 8️⃣ WebUI 使用

### 启动服务器
```bash
python deep_agent_server.py
```

### 访问界面
打开浏览器访问：http://localhost:8766

### 功能特性
- ✅ 实时显示 ReAct 思维链
- ✅ 查看 Skill 列表
- ✅ 多轮对话支持
- ✅ 日志面板

---

## 9️⃣ 最佳实践

### ✅ 推荐做法
1. **选择合适的 Agent**：
   - 简单任务 → WorkBuddy
   - 复杂任务 → DeepAgent

2. **编写清晰的 SKILL.md**：
   - 详细的参数说明
   - 丰富的使用示例
   - 必要的参考资料

3. **利用记忆系统**：
   - 定期清理无用记忆
   - 重要对话会自动保存

4. **监控执行日志**：
   - 关注错误信息
   - 优化参数提取

### ❌ 避免的做法
1. **不要在 SKILL.md 中包含敏感信息**（会保存在记忆中）
2. **不要执行不可信的脚本**（本地执行，有安全风险）
3. **不要硬编码 API Key**（使用环境变量）
4. **不要忽略错误日志**（帮助定位问题）

---

## 🔟 获取帮助

### 文档
- [OPTIMIZATION.md](OPTIMIZATION.md) - 优化说明
- [ARCHITECTURE.md](ARCHITECTURE.md) - 架构设计

### 社区
- 提交 Issue：GitHub Issues
- 讨论交流：Discussions

### 常见问题
查看本文档第 5 节「调试技巧」

---

## 🎉 开始构建！

现在你已经掌握了 DeepAgent 的基础知识，开始构建你的智能 Agent 吧！

```python
from deep_agent import DeepAgent

agent = DeepAgent("./skills")
response = agent.chat("你的第一个任务")
print(response)
```

祝你使用愉快！🚀
