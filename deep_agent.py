"""
DeepAgent - 基于 ReAct 循环的智能 Agent
========================================
架构：
  Memory        - 对话历史 + 工作记忆（本轮步骤链）
  SkillTool     - 将每个 Skill 包装为 Agent 可调用的 Tool
  ReActLoop     - 思考(Thought) → 行动(Action) → 观察(Observation) 循环
  DeepAgent     - 主入口：管理循环、记忆、工具调用、主动追问

与 WorkBuddy 的区别：
  WorkBuddy: 提前规划好所有步骤，线性执行，失败直接返回
  DeepAgent: 每步根据上一步观察动态决策，可自主纠错、换工具、主动追问
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI

# 复用 workbuddy.py 中已有的基础组件
from workbuddy import (
    SkillRegistry,
    SkillDisclosure,
    ScriptSelector,
    ParamExtractor,
    ScriptRunner,
    ScriptInfo,
    SkillDetail,
    make_llm,
    log_collector,
)


# ─────────────────────────────────────────────
# 1. Memory — 对话记忆
# ─────────────────────────────────────────────
@dataclass
class Message:
    role: str   # user / assistant / system / observation
    content: str


class Memory:
    """
    两层记忆：
      - long_term:  多轮对话历史（跨 chat 调用持久）
      - short_term: 本轮 ReAct 步骤链（每次 chat 重置）
    """

    def __init__(self, max_long_term: int = 20):
        self.long_term: List[Message] = []
        self.short_term: List[Message] = []   # 本轮思考链
        self.max_long_term = max_long_term

    def add_long(self, role: str, content: str):
        self.long_term.append(Message(role, content))
        # 超出上限时，保留最新的
        if len(self.long_term) > self.max_long_term:
            self.long_term = self.long_term[-self.max_long_term:]

    def add_short(self, role: str, content: str):
        self.short_term.append(Message(role, content))

    def reset_short(self):
        self.short_term = []

    def long_term_text(self) -> str:
        """格式化长期记忆供 LLM 阅读"""
        if not self.long_term:
            return ""
        lines = []
        for m in self.long_term[-10:]:  # 最多注入最近 10 条
            prefix = {"user": "用户", "assistant": "助手"}.get(m.role, m.role)
            lines.append(f"{prefix}: {m.content[:300]}")
        return "\n".join(lines)

    def short_term_text(self) -> str:
        """格式化本轮步骤链"""
        lines = []
        for m in self.short_term:
            lines.append(f"[{m.role}] {m.content}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
# 2. SkillTool — Skill 包装为 Agent 工具
# ─────────────────────────────────────────────
@dataclass
class ToolResult:
    success: bool
    output: str
    need_clarify: bool = False   # True = 需要向用户追问
    clarify_question: str = ""   # 追问内容


class SkillTool:
    """
    将单个 Skill 包装为 Agent 可调用的工具。
    调用时：
      1. 加载 Skill 详情（L2/L3）
      2. 选择脚本
      3. 用 LLM 提取/生成参数
      4. 检查必填参数 → 不足时返回 need_clarify=True
      5. 执行脚本，返回结果
    """

    def __init__(
        self,
        llm: ChatOpenAI,
        registry: SkillRegistry,
        disclosure: SkillDisclosure,
        selector: ScriptSelector,
        extractor: ParamExtractor,
        runner: ScriptRunner,
    ):
        self.llm = llm
        self.registry = registry
        self.disclosure = disclosure
        self.selector = selector
        self.extractor = extractor
        self.runner = runner

    def call(self, skill_name: str, instruction: str, context: str = "") -> ToolResult:
        """
        执行一个 Skill。
        context: Agent 本轮已有的观察结果，注入参数提取 prompt，帮助 LLM 生成更好的参数。
        """
        meta = self.registry.get(skill_name)
        if not meta:
            return ToolResult(False, f"Skill '{skill_name}' 不存在")

        print(f"[SkillTool] 调用 Skill: {skill_name}")
        detail = self.disclosure.load(meta)

        # 无脚本 → LLM 直接回答
        if not detail.scripts:
            answer = self._answer_with_content(instruction, detail)
            return ToolResult(True, answer)

        # 选脚本
        script = self.selector.select(instruction, detail.scripts, detail)
        if not script:
            answer = self._answer_with_content(instruction, detail)
            return ToolResult(True, answer)

        print(f"[SkillTool] 选中脚本: {script.path.name}")

        # 提取参数（把 context 注入 instruction，辅助生成）
        full_instruction = instruction
        if context:
            full_instruction = f"{instruction}\n\n[已知上下文]\n{context}"

        params = self.extractor.extract(full_instruction, script, detail)
        print(f"[SkillTool] 提取到参数: {params}")

        # 检查必填参数
        missing = self._check_required(script, params)
        if missing:
            question = f"需要以下信息才能继续：{', '.join(missing)}，请提供。"
            return ToolResult(False, "", need_clarify=True, clarify_question=question)

        # 执行脚本
        ok, output = self.runner.run(script, params)
        if ok:
            return ToolResult(True, output)
        else:
            return ToolResult(False, f"脚本执行失败: {output}")

    def _check_required(self, script: ScriptInfo, params: Dict) -> List[str]:
        missing = []
        for p in script.params:
            if p.required and p.name not in params and not p.default:
                missing.append(p.name)
        return missing

    def _answer_with_content(self, instruction: str, detail: SkillDetail) -> str:
        from workbuddy import llm_chat
        md_body = re.sub(r"^---.*?---\n", "", detail.full_content, flags=re.DOTALL)[:2000]
        prompt = f"请基于以下文档回答问题。\n\n{md_body}\n\n问题：{instruction}"
        return llm_chat(self.llm, prompt)


# ─────────────────────────────────────────────
# 3. ReAct 数据结构
# ─────────────────────────────────────────────
@dataclass
class Thought:
    """LLM 一次思考的输出"""
    reasoning: str           # 推理过程
    action_type: str         # "use_skill" | "ask_user" | "final_answer"
    skill_name: str = ""     # action_type == use_skill 时填写
    instruction: str = ""    # 传给 Skill 的指令
    question: str = ""       # action_type == ask_user 时填写
    answer: str = ""         # action_type == final_answer 时填写


# ─────────────────────────────────────────────
# 4. ReActLoop — 核心推理循环
# ─────────────────────────────────────────────
class ReActLoop:
    """
    单轮 ReAct 循环控制器。
    每次调用 step() 推进一步，直到 is_done() 为 True。
    """

    MAX_STEPS = 8   # 防止无限循环

    def __init__(self, llm: ChatOpenAI, registry: SkillRegistry, tool: SkillTool, memory: Memory):
        self.llm = llm
        self.registry = registry
        self.tool = tool
        self.memory = memory
        self._done = False
        self._final_answer = ""
        self._pending_question = ""   # 需要向用户追问的内容
        self._step_count = 0

    def is_done(self) -> bool:
        return self._done

    def final_answer(self) -> str:
        return self._final_answer

    def pending_question(self) -> str:
        return self._pending_question

    def step(self, user_input: str) -> str:
        """
        推进一步 ReAct 循环。
        返回本步的 Observation 文本（用于 WebUI 实时展示）。
        """
        if self._done or self._step_count >= self.MAX_STEPS:
            self._done = True
            if not self._final_answer:
                self._final_answer = "已达最大步骤数，任务结束。"
            return self._final_answer

        self._step_count += 1
        skills_summary = self.registry.summary_for_llm()
        history = self.memory.long_term_text()
        steps_so_far = self.memory.short_term_text()

        prompt = f"""你是一个智能 Agent，通过 ReAct 循环完成用户任务。

## 可用工具（Skill）
{skills_summary}

## 历史对话（最近）
{history or "（无）"}

## 本轮已执行步骤
{steps_so_far or "（尚未执行任何步骤）"}

## 用户当前输入
{user_input}

## 你的任务
分析当前情况，决定下一步行动。只能选择以下三种 action_type 之一：

1. use_skill   - 调用某个 Skill 获取信息或执行操作
2. ask_user    - 当前信息不足，需要向用户追问
3. final_answer - 已有足够信息，给出最终回答

## 输出格式（严格 JSON，不要任何额外文字）
{{
  "reasoning": "你的推理过程（中文，简洁）",
  "action_type": "use_skill | ask_user | final_answer",
  "skill_name": "（action_type=use_skill 时填写 skill name）",
  "instruction": "（action_type=use_skill 时填写给 Skill 的具体指令）",
  "question": "（action_type=ask_user 时填写追问内容）",
  "answer": "（action_type=final_answer 时填写完整回答）"
}}

注意：
- 如果上一步 Skill 已返回结果，优先基于结果作答，不要重复调用同一 Skill
- 如果 Skill 执行失败，尝试换参数重试或换其他 Skill，最多重试 2 次
- 只有真正缺少关键信息时才 ask_user，不要频繁追问

输出："""

        from workbuddy import llm_chat
        raw = llm_chat(self.llm, prompt)

        thought = self._parse_thought(raw)
        print(f"\n[ReAct] 步骤 {self._step_count} | action={thought.action_type}")
        print(f"[ReAct] 推理: {thought.reasoning[:120]}")

        self.memory.add_short("Thought", f"{thought.reasoning} → {thought.action_type}")

        if thought.action_type == "final_answer":
            self._final_answer = thought.answer
            self._done = True
            return thought.answer

        elif thought.action_type == "ask_user":
            self._pending_question = thought.question
            self._done = True   # 暂停循环，等用户回复
            return f"[需要追问] {thought.question}"

        elif thought.action_type == "use_skill":
            skill_name = thought.skill_name
            instruction = thought.instruction

            # 把当前步骤链摘要作为 context 传给 SkillTool
            context = self.memory.short_term_text()
            result = self.tool.call(skill_name, instruction, context)

            if result.need_clarify:
                # Skill 内部发现参数不足
                self._pending_question = result.clarify_question
                self._done = True
                return f"[需要追问] {result.clarify_question}"

            obs = result.output if result.success else f"[失败] {result.output}"
            self.memory.add_short("Observation", f"Skill={skill_name}: {obs[:500]}")
            print(f"[ReAct] Observation: {obs[:200]}...")
            return obs

        else:
            # 解析失败，直接 LLM 回答
            self._final_answer = llm_chat(self.llm, user_input)
            self._done = True
            return self._final_answer

    def _parse_thought(self, raw: str) -> Thought:
        """解析 LLM 输出的 JSON Thought"""
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return Thought(reasoning="解析失败", action_type="final_answer", answer=raw)
        try:
            data = json.loads(m.group())
            return Thought(
                reasoning=data.get("reasoning", ""),
                action_type=data.get("action_type", "final_answer"),
                skill_name=data.get("skill_name", ""),
                instruction=data.get("instruction", ""),
                question=data.get("question", ""),
                answer=data.get("answer", ""),
            )
        except json.JSONDecodeError:
            return Thought(reasoning="JSON解析失败", action_type="final_answer", answer=raw)


# ─────────────────────────────────────────────
# 5. DeepAgent — 主入口
# ─────────────────────────────────────────────
class DeepAgent:
    """
    基于 ReAct 循环的智能 Agent。

    与 WorkBuddy 对比：
      WorkBuddy  → 静态规划 + 线性执行
      DeepAgent  → 动态决策 + 循环推理 + 自主纠错 + 主动追问 + 记忆

    用法：
        agent = DeepAgent("./skills")
        response = agent.chat("帮我分析员工绩效并生成报告")
        # 如果需要追问：
        if agent.waiting_for_user:
            response = agent.chat("2025年的数据")  # 用户继续回复
    """

    def __init__(self, skills_dir: str):
        print("\n" + "=" * 55)
        print("  DeepAgent 启动中...")
        print("=" * 55)
        self.llm = make_llm()
        self.registry = SkillRegistry(skills_dir)
        self.memory = Memory()
        self.disclosure = SkillDisclosure()
        self.selector = ScriptSelector(self.llm)
        self.extractor = ParamExtractor(self.llm)
        self.runner = ScriptRunner()
        self.tool = SkillTool(
            self.llm, self.registry, self.disclosure,
            self.selector, self.extractor, self.runner
        )
        self._loop: Optional[ReActLoop] = None
        self._pending_user_input: str = ""   # 等待用户回复时暂存原始问题
        print(f"\n共发现 {len(self.registry.all())} 个 Skill\n")

    @property
    def waiting_for_user(self) -> bool:
        """当前是否在等待用户补充信息"""
        return self._loop is not None and bool(self._loop.pending_question())

    def chat(self, user_input: str) -> str:
        """
        处理用户输入，返回最终回答。
        支持多轮追问：如果 Agent 需要补充信息，返回追问内容；
        用户再次调用 chat() 时自动续上。
        """
        user_input = user_input.strip()
        if not user_input:
            return ""

        # 如果上一轮有待追问，把用户回复合并进原始问题
        if self._loop and self._loop.pending_question() and self._pending_user_input:
            combined = f"{self._pending_user_input}\n[用户补充] {user_input}"
            print(f"[DeepAgent] 用户补充信息，续接任务: {combined[:80]}")
            # 把补充信息注入记忆后重新推进循环
            self.memory.add_long("user", f"[补充] {user_input}")
            self.memory.add_short("UserReply", user_input)
            self._loop._pending_question = ""  # 清除追问状态
            self._loop._done = False            # 恢复循环
            return self._run_loop(combined)

        # 全新一轮对话
        self.memory.add_long("user", user_input)
        self.memory.reset_short()
        self._pending_user_input = user_input
        self._loop = ReActLoop(self.llm, self.registry, self.tool, self.memory)

        result = self._run_loop(user_input)
        self.memory.add_long("assistant", result[:500])
        return result

    def _run_loop(self, user_input: str) -> str:
        """驱动 ReAct 循环直到完成或需要追问"""
        assert self._loop is not None
        last_obs = ""

        while not self._loop.is_done():
            obs = self._loop.step(user_input)
            last_obs = obs

            if self._loop.pending_question():
                # 需要向用户追问，暂停并返回问题
                return self._loop.pending_question()

        return self._loop.final_answer() or last_obs

    def list_skills(self):
        print("\n已加载 Skill 列表:")
        for m in self.registry.all():
            print(f"  @{m.name}  —  {m.description}")


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="DeepAgent - ReAct 智能 Agent")
    parser.add_argument(
        "--skills-dir",
        default=str(Path(__file__).parent / "skills"),
        help="Skills 根目录（默认: ./skills）",
    )
    parser.add_argument("--query", "-q", help="单次查询后退出")
    args = parser.parse_args()

    agent = DeepAgent(args.skills_dir)
    agent.list_skills()

    if args.query:
        print(f"\n你: {args.query}")
        result = agent.chat(args.query)
        print(f"\nDeepAgent:\n{result}")
        return

    print("\n" + "=" * 55)
    print("  DeepAgent 就绪！（ReAct 循环模式）")
    print("  输入 'exit' 退出")
    print("=" * 55 + "\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("再见！")
            break

        result = agent.chat(user_input)
        print(f"\nDeepAgent:\n{result}\n")


if __name__ == "__main__":
    main()
