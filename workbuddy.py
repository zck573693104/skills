"""
WorkBuddy - 智能 Skill 执行引擎 (v2.0)
==============================
架构：
  1. SkillRegistry   - 扫描并注册所有 skill（Level-1 元数据）
  2. IntentMatcher   - 大模型意图识别，从用户输入匹配最佳 skill（单步备用）
  2.5 TaskPlanner   - 任务规划：分析是否需要多 Skill 协作，输出有序步骤列表
                      支持步骤间结果传递（{step_N_output} 占位符）
  3. SkillDisclosure - 渐进式披露：按需加载 Level-2/3/4 内容
  4. ParamExtractor  - 大模型从 SKILL.md + 用户输入中自动提取脚本参数
  5. ScriptRunner    - 执行脚本并返回结果
  6. WorkBuddy       - 主入口，串联全流程（单步/多步自动切换）

核心特性：
  ✓ 静态规划：提前分析任务，生成执行计划
  ✓ 多步编排：支持多个 Skill 协作完成任务
  ✓ 结果传递：上一步输出可作为下一步输入
  ✓ 渐进式披露：按需加载 Skill 内容，节省 Token
"""


import os
import re
import sys
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
from langchain_openai import ChatOpenAI


# ─────────────────────────────────────────────
# 全局日志收集器（供 WebUI 后端订阅）
# ─────────────────────────────────────────────
class LogCollector:
    """
    拦截所有 print() 输出，同时：
      1. 正常打印到终端
      2. 推送给所有已注册的回调（WebUI SSE 连接）
    用法：with log_collector.capture(): ...
    """
    def __init__(self):
        self._callbacks: List[Callable[[str], None]] = []
        self._active = False

    def subscribe(self, cb: Callable[[str], None]):
        self._callbacks.append(cb)

    def unsubscribe(self, cb: Callable[[str], None]):
        self._callbacks = [c for c in self._callbacks if c is not cb]

    def emit(self, text: str):
        for cb in list(self._callbacks):
            try:
                cb(text)
            except Exception:
                pass

    def capture(self):
        return _PrintInterceptor(self)


class _PrintInterceptor:
    """Context manager：重定向 stdout，同时保留终端输出"""
    def __init__(self, collector: "LogCollector"):
        self._collector = collector
        self._original = None

    def __enter__(self):
        self._original = sys.stdout
        sys.stdout = self
        return self

    def write(self, text: str):
        self._original.write(text)
        if text.strip():
            self._collector.emit(text.rstrip("\n"))

    def flush(self):
        self._original.flush()

    def __exit__(self, *_):
        sys.stdout = self._original


# 全局单例
log_collector = LogCollector()




# ─────────────────────────────────────────────
# LLM 工厂
# ─────────────────────────────────────────────
def make_llm(model: str = "deepseek-reasoner", temperature: float = 0.7) -> ChatOpenAI:
    """创建 LLM 实例"""
    return ChatOpenAI(
        model=model,
        api_key=os.getenv('AI_KEY'),
        base_url="https://api.heabl.top/v1",
        temperature=temperature,
    )


def llm_chat(llm: ChatOpenAI, prompt: str, max_tokens: int = None) -> str:
    """调用 LLM 并返回结果"""
    kwargs = {}
    if max_tokens:
        kwargs['max_tokens'] = max_tokens
    return llm.invoke(prompt, **kwargs).content.strip()


# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────
@dataclass
class ScriptParam:
    """单个脚本参数描述"""
    name: str
    type: str = "str"
    required: bool = False
    description: str = ""
    default: Any = None


@dataclass
class ScriptInfo:
    """脚本文件信息（从 SKILL.md 中解析）"""
    path: Path
    usage_example: str = ""           # 从 SKILL.md 中提取的示例调用
    params: List[ScriptParam] = field(default_factory=list)
    raw_params_section: str = ""      # 原始参数表格文本，供 LLM 理解


@dataclass
class SkillMeta:
    """Level-1：轻量元数据，始终驻内存"""
    name: str
    description: str
    path: Path
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class SkillDetail:
    """Level-2+：按需加载的完整信息"""
    meta: SkillMeta
    full_content: str = ""            # SKILL.md 全文
    scripts: List[ScriptInfo] = field(default_factory=list)
    references: List[Path] = field(default_factory=list)
    assets: List[Path] = field(default_factory=list)


# ─────────────────────────────────────────────
# 1. SkillRegistry — 扫描 & 注册 skills
# ─────────────────────────────────────────────
class SkillRegistry:
    def __init__(self, skills_root: str):
        self.root = Path(skills_root)
        self._meta: Dict[str, SkillMeta] = {}
        self._scan()

    def _scan(self):
        if not self.root.exists():
            print(f"[SkillRegistry] ⚠ 目录不存在: {self.root}")
            return
        for skill_dir in sorted(self.root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            meta = self._parse_meta(skill_md)
            if meta:
                self._meta[meta.name] = meta
                print(f"[SkillRegistry] ✓ {meta.name}  —  {meta.description[:60]}")

    def _parse_meta(self, skill_md: Path) -> Optional[SkillMeta]:
        try:
            text = skill_md.read_text(encoding="utf-8")
            # 需要 YAML frontmatter
            m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            if not m:
                return None
            data = yaml.safe_load(m.group(1)) or {}
            return SkillMeta(
                name=data.get("name", skill_md.parent.name),
                description=data.get("description", ""),
                path=skill_md.parent,
                tags=data.get("tags", []),
                version=data.get("version", "1.0.0"),
            )
        except Exception as e:
            print(f"[SkillRegistry] 解析失败 {skill_md}: {e}")
            return None

    def all(self) -> List[SkillMeta]:
        return list(self._meta.values())

    def get(self, name: str) -> Optional[SkillMeta]:
        return self._meta.get(name)

    def summary_for_llm(self) -> str:
        """给 LLM 的技能摘要（仅 name + description）"""
        lines = []
        for m in self._meta.values():
            lines.append(f"- name: {m.name}\n  desc: {m.description}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
# 2. IntentMatcher — 大模型意图识别
# ─────────────────────────────────────────────
class IntentMatcher:
    def __init__(self, llm: ChatOpenAI, registry: SkillRegistry):
        self.llm = llm
        self.registry = registry

    def match(self, user_input: str) -> Optional[str]:
        """
        返回匹配到的 skill name，无匹配时返回 None。
        """
        skills_summary = self.registry.summary_for_llm()
        if not skills_summary:
            return None

        prompt = f"""你是一个智能助手的意图识别引擎。
根据用户输入，从下列技能中选出【最匹配的一个技能名称】。
- 如果没有合适的技能，输出: NONE
- 只输出技能名或 NONE，不要任何解释。

可用技能：
{skills_summary}

用户输入：{user_input}

输出："""
        result = llm_chat(self.llm, prompt)
        # 清理模型可能多输出的空格/引号
        result = result.strip().strip('"').strip("'")
        if result == "NONE" or result not in [m.name for m in self.registry.all()]:
            return None
        return result


# ─────────────────────────────────────────────
# 2.5 TaskPlanner — 多 Skill 任务规划
# ─────────────────────────────────────────────
@dataclass
class SkillStep:
    """单个执行步骤"""
    skill_name: str                          # 要调用的 skill
    instruction: str                         # 该步骤的具体指令（可含上一步结果占位符）
    depends_on: List[int] = field(default_factory=list)  # 依赖的前置步骤索引（空=无依赖）


class TaskPlanner:
    """
    分析用户意图，决定：
      - 单 Skill：直接返回 [SkillStep]（一步）
      - 多 Skill：规划有序步骤列表，支持结果传递
      - 无 Skill：返回空列表（转通用对话）
    """

    def __init__(self, llm: ChatOpenAI, registry: SkillRegistry):
        self.llm = llm
        self.registry = registry

    def plan(self, user_input: str) -> List[SkillStep]:
        skills_summary = self.registry.summary_for_llm()
        if not skills_summary:
            return []

        prompt = f"""你是一个任务规划引擎。根据用户输入和可用技能，规划执行步骤。

规则：
1. 如果只需一个技能，输出一个步骤
2. 如果需要多个技能协作，按执行顺序列出所有步骤
3. 如果上一步的输出要传给下一步，在 instruction 中用 {{step_N_output}} 占位（N 从 0 开始）
4. 如果没有任何技能能完成任务，输出空数组 []
5. 只输出 JSON 数组，不要任何解释

可用技能：
{skills_summary}

用户输入：{user_input}

输出格式示例（多步骤）：
[
  {{"skill_name": "baidu-search", "instruction": "搜索最新手机价格", "depends_on": []}},
  {{"skill_name": "logistics-sales-agent", "instruction": "根据以下商品信息查询物流报价：{{step_0_output}}", "depends_on": [0]}}
]

输出格式示例（单步骤）：
[
  {{"skill_name": "weather-gd", "instruction": "查询今天热搜", "depends_on": []}}
]

输出："""

        raw = llm_chat(self.llm, prompt)
        # 提取 JSON 数组
        m = re.search(r"\[[\s\S]*\]", raw)
        if not m:
            return []
        try:
            steps_data = json.loads(m.group())
        except json.JSONDecodeError:
            return []

        steps = []
        for item in steps_data:
            name = item.get("skill_name", "")
            if not self.registry.get(name):
                continue  # 忽略不存在的 skill
            steps.append(SkillStep(
                skill_name=name,
                instruction=item.get("instruction", user_input),
                depends_on=item.get("depends_on", []),
            ))
        return steps


# ─────────────────────────────────────────────
# 3. SkillDisclosure — 渐进式披露
# ─────────────────────────────────────────────
class SkillDisclosure:
    """
    四级渐进式披露：
      L1 - meta（始终可用，来自 SkillRegistry）
      L2 - SKILL.md 全文
      L3 - 脚本列表 & 参数 schema（从 SKILL.md 解析）
      L4 - 执行准备（由 ParamExtractor + ScriptRunner 完成）
    """

    def load(self, meta: SkillMeta) -> SkillDetail:
        """加载 L2 + L3"""
        detail = SkillDetail(meta=meta)
        skill_md = meta.path / "SKILL.md"

        # L2: 全文
        if skill_md.exists():
            detail.full_content = skill_md.read_text(encoding="utf-8")

        # L3: 脚本
        scripts_dir = meta.path / "scripts"
        if scripts_dir.exists():
            for f in sorted(scripts_dir.iterdir()):
                if f.is_file() and f.suffix in (".py", ".sh", ".js"):
                    detail.scripts.append(
                        ScriptInfo(
                            path=f,
                            usage_example=self._extract_usage(detail.full_content, f.name),
                            params=self._parse_params_from_md(detail.full_content),
                            raw_params_section=self._extract_params_section(detail.full_content),
                        )
                    )

        # L3: 参考资料 & 资产
        for sub, attr in [("references", "references"), ("assets", "assets")]:
            d = meta.path / sub
            if d.exists():
                setattr(detail, attr, [p for p in d.rglob("*") if p.is_file()])

        return detail

    # ── 从 SKILL.md 解析参数表格 ──────────────────────────────
    def _extract_params_section(self, md_text: str) -> str:
        """提取 SKILL.md 中参数相关段落（## Parameters / ## Request Parameters 等）"""
        pattern = r"(##\s*(?:Request\s+)?Parameters.*?)(?=\n##|\Z)"
        m = re.search(pattern, md_text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _extract_usage(self, md_text: str, script_name: str) -> str:
        """提取与脚本名相关的示例行"""
        lines = []
        for line in md_text.splitlines():
            if script_name in line and ("python" in line or "bash" in line or ".py" in line):
                lines.append(line.strip())
        return "\n".join(lines[:3])

    def _parse_params_from_md(self, md_text: str) -> List[ScriptParam]:
        """
        尝试解析 markdown 参数表格，例如：
        | Param | Type | Required | Default | Description |
        """
        params = []
        in_table = False
        header_cols: List[str] = []

        for line in md_text.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                if in_table:
                    break
                continue

            cells = [c.strip() for c in line.strip("|").split("|")]
            if not header_cols:
                # 检查是否是参数表格的表头
                lower_cells = [c.lower() for c in cells]
                if "param" in lower_cells or "parameter" in lower_cells:
                    header_cols = lower_cells
                    in_table = True
                continue
            # 跳过分隔行
            if all(re.match(r"^[-:]+$", c) for c in cells if c):
                continue

            if len(cells) < 2:
                continue

            def col(name_candidates):
                for n in name_candidates:
                    if n in header_cols:
                        idx = header_cols.index(n)
                        return cells[idx] if idx < len(cells) else ""
                return ""

            param_name = col(["param", "parameter", "name"])
            if not param_name or param_name.startswith("-"):
                continue
            # 去掉 backtick
            param_name = param_name.strip("`")

            params.append(ScriptParam(
                name=param_name,
                type=col(["type"]) or "str",
                required=(col(["required"]).lower() in ("yes", "true", "required")),
                description=col(["description", "desc"]),
                default=col(["default"]) or None,
            ))
        return params


# ─────────────────────────────────────────────
# 4a. ScriptSelector — LLM 选择要执行的脚本
# ─────────────────────────────────────────────
class ScriptSelector:
    """
    当一个 Skill 下有多个脚本时，用 LLM 根据用户意图选出应该执行的那一个。
    单脚本时直接返回，无需 LLM 调用。
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def select(self, user_input: str, scripts: List[ScriptInfo], skill_detail: SkillDetail) -> Optional[ScriptInfo]:
        if not scripts:
            return None
        if len(scripts) == 1:
            return scripts[0]

        # 构造每个脚本的摘要（名称 + 从 SKILL.md 提取的用途说明）
        script_descs = []
        for i, s in enumerate(scripts):
            usage = s.usage_example or ""
            section_desc = self._extract_script_desc(skill_detail.full_content, s.path.name)
            script_descs.append(f"{i}. {s.path.name}  —  {section_desc or usage[:80]}")
        # 最后一个选项：无需脚本
        none_idx = len(scripts)
        script_descs.append(f"{none_idx}. NONE  —  用户意图不需要执行脚本，直接用知识回答即可")

        prompt = f"""你是脚本选择助手。根据用户意图，从以下选项中选出【最合适的一个】。
- 如果用户的问题需要查询数据或执行操作，选对应的脚本序号
- 如果用户只是问知识/建议/话术/FAQ，选 {none_idx}（NONE）
只输出序号，不要任何解释。

可用选项：
{chr(10).join(script_descs)}

用户输入：{user_input}

输出序号："""

        raw = llm_chat(self.llm, prompt).strip()
        m = re.search(r"\d+", raw)
        if m:
            idx = int(m.group())
            if idx == none_idx:
                return None  # 不执行脚本，回退到 LLM 直接回答
            if 0 <= idx < len(scripts):
                return scripts[idx]
        return None  # 解析失败也回退

    def _extract_script_desc(self, md_text: str, script_name: str) -> str:
        """提取 SKILL.md 中脚本对应的说明行（如 `scripts/quote.py` — 运价计算）"""
        for line in md_text.splitlines():
            if script_name in line and "—" in line:
                return line.strip().lstrip("-").strip()
            if script_name in line and "：" in line:
                return line.strip().lstrip("-").strip()
        return ""


# ─────────────────────────────────────────────
# 4b. ParamExtractor — LLM 自动提取脚本参数
# ─────────────────────────────────────────────
class ParamExtractor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def extract(self, user_input: str, script: ScriptInfo, skill_detail: SkillDetail) -> Dict[str, Any]:
        """
        综合 SKILL.md 内容、references/ 参考文件、脚本用法示例、参数定义，
        从用户输入中提取或推断生成脚本所需的参数。
        返回 {param_name: value} 字典。
        """
        # 构造参数说明
        param_desc = ""
        if script.params:
            lines = []
            for p in script.params:
                req = "必填" if p.required else "可选"
                default = f"，默认={p.default}" if p.default else ""
                lines.append(f"  - {p.name} ({p.type}, {req}{default}): {p.description}")
            param_desc = "\n".join(lines)
        elif script.raw_params_section:
            param_desc = script.raw_params_section
        else:
            param_desc = "（未找到参数定义，请根据 SKILL.md 内容推断）"

        # SKILL.md 正文（去掉 frontmatter，避免过长）
        md_body = re.sub(r"^---.*?---\n", "", skill_detail.full_content, flags=re.DOTALL)[:2000]

        # 自动加载 references/ 目录下的参考文件（表结构、指标定义等）
        references_section = self._load_references(skill_detail.meta.path)

        # 从用法示例中补充提取参数名，帮助 LLM 理解
        usage_hint = self._extract_flag_names(script.usage_example)

        prompt = f"""你是参数生成助手。根据用户需求和参考资料，为脚本生成所需的参数值。

脚本文件：{script.path.name}

Skill 说明（节选）：
{md_body}

脚本参数定义：
{param_desc}

用法示例：
{script.usage_example or "（无示例）"}
{references_section}
用户输入：
{user_input}

要求：
1. 以 JSON 格式输出参数名和对应的值
2. 参数名使用纯名称，不带 -- 前缀，例如 {{"from": "北京", "to": "上海"}}
3. 对于 flag 开关参数（如 --followup、--list，后面没有值），用 JSON boolean：{{"followup": true}}
4. 对于可选参数，如果用户未提及则不要包含
5. 只输出 JSON，不要任何解释
6. 参数值类型要匹配定义（int 转为数字，flag 转为 bool）
7. 【重要】如果某个必填参数的值无法从用户输入中直接找到，应根据上方参考资料（表结构/指标定义/示例）自行推断或生成。
   例如：--sql 参数需要 SQL 语句时，请根据表结构和用户分析需求，自行编写合适的 SQL 语句作为参数值。
{f"8. 已知该脚本的参数名有：{usage_hint}" if usage_hint else ""}

输出："""

        raw = llm_chat(self.llm, prompt)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            return {}
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            return {}

    def _load_references(self, skill_path: Path) -> str:
        """加载 skill 目录下 references/ 中的所有 .md 文件，拼成 prompt 段落"""
        refs_dir = skill_path / "references"
        if not refs_dir.exists():
            return ""
        sections = []
        for f in sorted(refs_dir.iterdir()):
            if f.suffix.lower() == ".md":
                try:
                    content = f.read_text(encoding="utf-8")[:3000]  # 单文件最多 3000 字
                    sections.append(f"=== 参考文件：{f.name} ===\n{content}")
                except Exception:
                    pass
        if not sections:
            return ""
        return "\n\n参考资料（表结构/指标定义/示例 SQL 等）：\n" + "\n\n".join(sections) + "\n\n"

    def _extract_flag_names(self, usage_example: str) -> str:
        """从用法示例中提取所有 --xxx 参数名（不含值），返回逗号分隔字符串"""
        if not usage_example:
            return ""
        names = re.findall(r"--(\w[\w\-]*)", usage_example)
        return ", ".join(dict.fromkeys(names))  # 去重保序


# ─────────────────────────────────────────────
# 5. ScriptRunner — 执行脚本
# ─────────────────────────────────────────────
class ScriptRunner:
    def run(self, script: ScriptInfo, params: Dict[str, Any]) -> Tuple[bool, str]:
        """
        根据脚本类型和参数构建命令并执行。
        返回 (success, output)。
        """
        script_path = script.path
        suffix = script_path.suffix

        # 构建命令
        if suffix == ".py":
            cmd = [sys.executable, str(script_path)]
        elif suffix == ".sh":
            cmd = ["bash", str(script_path)]
        elif suffix == ".js":
            cmd = ["node", str(script_path)]
        else:
            return False, f"不支持的脚本类型: {suffix}"

        # 附加参数（智能判断传参方式）
        cmd = self._append_params(cmd, script, params)

        print(f"[ScriptRunner] 执行: {' '.join(str(x) for x in cmd)}")

        try:
            # 强制子进程使用 UTF-8，避免 Windows GBK 环境下 emoji 等字符 UnicodeEncodeError
            utf8_env = os.environ.copy()
            utf8_env["PYTHONIOENCODING"] = "utf-8"
            utf8_env["PYTHONUTF8"] = "1"
            proc = subprocess.run(cmd, capture_output=True, timeout=120, env=utf8_env)
            stdout = self._decode(proc.stdout)
            stderr = self._decode(proc.stderr)
            if proc.returncode == 0:
                output = stdout or "(无输出)"
                # 把原始输出打印到 log（会被 LogCollector 捕获推送到 WebUI 日志面板）
                print(f"[ScriptRunner] 原始输出:\n{output}")
                return True, output
            else:
                error = stderr or f"退出码: {proc.returncode}"
                print(f"[ScriptRunner] 执行失败:\n{error}")
                return False, error
        except subprocess.TimeoutExpired:
            return False, "执行超时（30s）"
        except Exception as e:
            return False, str(e)

    def _append_params(self, cmd: List, script: ScriptInfo, params: Dict[str, Any]) -> List:
        """
        根据 SKILL.md 中的用法示例，智能判断参数传递方式：
          - JSON 字符串（如 baidu-search）
          - --key value 形式（如 weather）
          - 位置参数（如 weather city）
        """
        usage = script.usage_example.lower()

        # 模式1: JSON 字符串传参  python script.py '{"query":"..."}'
        if re.search(r"\.py\s+'?\{", usage) or re.search(r"\.py\s+'\{", usage):
            cmd.append(json.dumps(params, ensure_ascii=False))
            return cmd

        # 模式2: --key value 传参
        if "--" in usage:
            for k, v in params.items():
                clean_key = k.lstrip("-")
                if isinstance(v, bool):
                    # store_true / store_false flag，只传 --key，不传值
                    if v:
                        cmd.append(f"--{clean_key}")
                    # False 则跳过（不传该 flag）
                else:
                    cmd.extend([f"--{clean_key}", str(v)])
            return cmd

        # 模式3: 位置参数（按 params 顺序）
        if params:
            for v in params.values():
                cmd.append(str(v))
        return cmd

    def _decode(self, b: bytes) -> str:
        for enc in ("utf-8", "gbk", "utf-8-sig"):
            try:
                return b.decode(enc)
            except UnicodeDecodeError:
                continue
        return b.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────
# 6. WorkBuddy — 主引擎
# ─────────────────────────────────────────────
class WorkBuddy:
    """
    主入口，串联全流程：
      用户输入 → 任务规划(TaskPlanner) → 逐步执行(单/多 Skill) → 汇总结果
      每步：渐进式披露(L2/L3) → 脚本选择 → 参数提取(L4) → 执行脚本
      多步时：上一步输出自动注入下一步 instruction（{step_N_output} 占位符）
    """

    def __init__(self, skills_dir: str):
        print("\n" + "=" * 55)
        print("  WorkBuddy 启动中...")
        print("=" * 55)
        self.llm = make_llm()
        self.registry = SkillRegistry(skills_dir)
        self.intent = IntentMatcher(self.llm, self.registry)
        self.planner = TaskPlanner(self.llm, self.registry)
        self.disclosure = SkillDisclosure()
        self.selector = ScriptSelector(self.llm)
        self.extractor = ParamExtractor(self.llm)
        self.runner = ScriptRunner()
        print(f"\n共发现 {len(self.registry.all())} 个 Skill\n")

    # ── 公开方法 ────────────────────────────────────────────────

    def chat(self, user_input: str) -> str:
        """处理一次用户输入，返回字符串结果（支持单/多 Skill 编排）"""
        user_input = user_input.strip()
        if not user_input:
            return ""

        # 支持 @skill_name 直接指定（跳过规划，单步执行）
        explicit_name = self._parse_explicit(user_input)
        if explicit_name:
            return self._run_single_skill(explicit_name, user_input)

        # ── 任务规划 ─────────────────────────────────────────────
        print(f"[WorkBuddy] 任务规划中...")
        steps = self.planner.plan(user_input)

        if not steps:
            print("[WorkBuddy] 无匹配 Skill，转为通用对话")
            return llm_chat(self.llm, user_input)

        if len(steps) == 1:
            # 单步：直接执行
            return self._run_single_skill(steps[0].skill_name, steps[0].instruction)

        # 多步：按顺序执行，传递上下文
        print(f"[WorkBuddy] 多步任务，共 {len(steps)} 步")
        return self._run_multi_steps(user_input, steps)

    def list_skills(self):
        """打印所有已加载 Skill"""
        print("\n📋 已加载 Skill 列表:")
        for m in self.registry.all():
            print(f"  @{m.name}  —  {m.description}")

    # ── 内部方法 ────────────────────────────────────────────────

    def _run_single_skill(self, skill_name: str, instruction: str) -> str:
        """执行单个 Skill 的完整流程（优化版：简化日志输出）"""
        meta = self.registry.get(skill_name)
        if not meta:
            return f"Skill '{skill_name}' 未找到"

        print(f"\n[WorkBuddy] 匹配到 Skill: {skill_name}")

        # L2 + L3: 渐进式披露
        detail = self.disclosure.load(meta)

        if not detail.scripts:
            print("[WorkBuddy] 无脚本，LLM 基于 SKILL.md 直接回答")
            return self._answer_with_content(instruction, detail)

        # L3.5: 选择脚本
        script = self.selector.select(instruction, detail.scripts, detail)
        if not script:
            return self._answer_with_content(instruction, detail)
        
        print(f"[WorkBuddy] 选中脚本: {script.path.name}")

        # L4: 参数提取 + 执行
        params = self.extractor.extract(instruction, script, detail)
        print(f"[WorkBuddy] 提取到参数: {params}")

        missing = self._check_required(script, params)
        if missing:
            return f"缺少必填参数: {', '.join(missing)}，请补充后重试。"

        ok, output = self.runner.run(script, params)
        return output if ok else f"❌ {script.path.name} 执行失败:\n{output}"

    def _run_multi_steps(self, user_input: str, steps: List[SkillStep]) -> str:
        """
        多步骤串行执行：
          - 每步结果存入 results[i]
          - 下一步 instruction 中的 {step_N_output} 被替换为对应步结果
          - 最后由 LLM 汇总所有步骤结果，生成完整回答
        """
        results: Dict[int, str] = {}

        for i, step in enumerate(steps):
            # 替换占位符，注入前置步骤输出
            instruction = step.instruction
            for dep_idx in step.depends_on:
                placeholder = f"{{step_{dep_idx}_output}}"
                if placeholder in instruction and dep_idx in results:
                    instruction = instruction.replace(placeholder, results[dep_idx])

            print(f"\n[WorkBuddy] ── 步骤 {i+1}/{len(steps)}: {step.skill_name} ──")
            result = self._run_single_skill(step.skill_name, instruction)
            results[i] = result

        # 汇总：让 LLM 整合所有步骤结果，生成最终回答
        steps_summary = "\n\n".join(
            f"## 步骤{i+1} ({steps[i].skill_name})\n{results[i]}"
            for i in range(len(steps))
        )
        summary_prompt = f"""用户的原始问题：{user_input}

以下是各步骤的执行结果：

{steps_summary}

请根据以上所有结果，整合成一个完整、清晰的回答。"""

        print(f"\n[WorkBuddy] 汇总 {len(steps)} 个步骤结果...")
        return llm_chat(self.llm, summary_prompt)

    def _parse_explicit(self, user_input: str) -> Optional[str]:
        """解析 @skill_name 直接指定语法"""
        m = re.match(r"^@([\w\-]+)", user_input)
        if m:
            name = m.group(1)
            if self.registry.get(name):
                return name
        return None

    def _check_required(self, script: ScriptInfo, params: Dict) -> List[str]:
        missing = []
        for p in script.params:
            if p.required and p.name not in params and not p.default:
                missing.append(p.name)
        return missing

    def _answer_with_content(self, user_input: str, detail: SkillDetail) -> str:
        """
        无脚本时，渐进式披露 SKILL.md + references 文件内容，增强 LLM 回答。
        回答末尾附上引用了哪些文件。
        """
        # ── Step 1: SKILL.md 正文（去掉 frontmatter）────────────────
        md_body = re.sub(r"^---.*?---\n", "", detail.full_content, flags=re.DOTALL)[:2000]

        # ── Step 2: 让 LLM 选出需要读取哪些 reference 文件 ──────────
        used_refs: List[Path] = []
        ref_contents: Dict[str, str] = {}

        if detail.references:
            ref_names = [p.name for p in detail.references]
            select_prompt = f"""你是文档选择助手。根据用户问题，从以下参考文件中选出【需要阅读的文件名】。
只输出文件名列表（JSON 数组），例如 ["sales_scripts.md", "faq.md"]，不要解释。

可用文件：{json.dumps(ref_names, ensure_ascii=False)}

用户问题：{user_input}

输出："""
            raw = llm_chat(self.llm, select_prompt)
            m = re.search(r"\[.*?\]", raw, re.DOTALL)
            if m:
                try:
                    selected_names = json.loads(m.group())
                    # 按选出的名称读取对应文件
                    name_to_path = {p.name: p for p in detail.references}
                    for name in selected_names:
                        p = name_to_path.get(name)
                        if p and p.exists():
                            used_refs.append(p)
                            ref_contents[name] = p.read_text(encoding="utf-8")
                except (json.JSONDecodeError, Exception):
                    pass

        print(f"[WorkBuddy] 参考文件: {[p.name for p in used_refs] or '仅 SKILL.md'}")

        # ── Step 3: 拼接所有文档内容喂给 LLM ────────────────────────
        docs_section = f"【SKILL.md 说明】\n{md_body}"
        for name, content in ref_contents.items():
            docs_section += f"\n\n【{name}】\n{content[:2000]}"

        answer_prompt = f"""你是一个专业智能助手。请基于以下文档内容回答用户问题。

{docs_section}

用户问题：{user_input}

请用中文专业、简洁地回答："""

        answer = llm_chat(self.llm, answer_prompt)

        # ── Step 4: 附加引用文件说明 ─────────────────────────────────
        all_used = ["SKILL.md"] + [p.name for p in used_refs]
        ref_footer = "\n\n---\n📄 **引用文档**: " + " · ".join(f"`{f}`" for f in all_used)

        return answer + ref_footer


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="WorkBuddy - 智能 Skill 执行引擎")
    parser.add_argument(
        "--skills-dir",
        default=str(Path(__file__).parent / "skills"),
        help="Skills 根目录（默认: ./skills）",
    )
    parser.add_argument(
        "--query", "-q",
        help="直接执行一次查询后退出（非交互模式）",
    )
    args = parser.parse_args()

    buddy = WorkBuddy(args.skills_dir)
    buddy.list_skills()

    if args.query:
        print(f"\n🧑 你: {args.query}")
        result = buddy.chat(args.query)
        print(f"\n🤖 WorkBuddy:\n{result}")
        return

    # 交互模式
    print("\n" + "=" * 55)
    print("  WorkBuddy 就绪！")
    print("  输入 'exit' 退出，@skill_name 可直接指定 Skill")
    print("=" * 55 + "\n")

    while True:
        try:
            user_input = input("🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("👋 再见！")
            break

        result = buddy.chat(user_input)
        print(f"\n🤖 WorkBuddy:\n{result}\n")


if __name__ == "__main__":
    main()
