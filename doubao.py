# ==============================================
# MiniDeepAgent - 升级版
# 大模型意图识别 → 自动调用 Skill
# ==============================================
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
import json

# --------------------------
# 1. 大模型抽象层
# --------------------------
class BaseLLM:
    def chat(self, prompt: str) -> str:
        raise NotImplementedError

class LangChainLLM(BaseLLM):
    def __init__(self, llm):
        self.llm = llm

    def chat(self, prompt: str) -> str:
        return self.llm.invoke(prompt).content

# --------------------------
# 2. Skill 插件体系
# --------------------------
class Skill:
    name: str
    description: str
    def execute(self, **kwargs) -> Any:
        raise NotImplementedError

class SkillManager:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}

    def register(self, skill: Skill):
        self.skills[skill.name] = skill

    def get_skill_list(self) -> List[Dict]:
        return [
            {"name": s.name, "desc": s.description}
            for s in self.skills.values()
        ]

    def execute_skill(self, name: str, **kwargs):
        if name not in self.skills:
            return f"技能 {name} 不存在"
        return self.skills[name].execute(**kwargs)

# --------------------------
# 3. 核心 Agent（大模型自动意图识别）
# --------------------------
class MiniDeepAgent:
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.skill_manager = SkillManager()

    def add_skill(self, skill: Skill):
        self.skill_manager.register(skill)

    # ========================
    # ⭐ 你要的升级版本
    # 大模型意图识别 → 自动调用技能
    # ========================
    def run(self, user_input: str):
        # 1. 获取所有技能列表
        skill_list = self.skill_manager.get_skill_list()

        # 2. 构造大模型意图识别 Prompt
        prompt = f"""
你是一个物流销售智能体的意图识别引擎。
根据用户输入，从下面技能中选择【唯一一个最匹配的技能名称】返回，只返回技能名，不要解释。

技能列表：
{json.dumps(skill_list, ensure_ascii=False, indent=2)}

用户输入：{user_input}

输出（只输出技能名）：
""".strip()

        # 3. 大模型识别意图
        skill_name = self.llm.chat(prompt).strip()

        # 4. 执行匹配到的技能
        if skill_name in self.skill_manager.skills:
            return self.skill_manager.execute_skill(skill_name)
        else:
            # 无匹配技能 → 直接对话
            return self.llm.chat(user_input)

# --------------------------
# 4. 物流销售技能集合
# --------------------------
class SalesWeeklySkill(Skill):
    name = "sales_weekly_report"
    description = "生成销售周报、工作汇报、业绩总结"

    def execute(self, **kwargs):
        return """
【物流销售周报】
📦 本月总发货量：860 吨
💰 总毛利：24.6 万元
👥 负责客户：6 家
✅ 高价值客户：3 家
⚠️ 需跟进风险客户：1 家

AI 建议：
1. 重点维护高价值客户
2. 立即回访发货量下滑客户
3. 推广高利润线路
"""

class MyCustomersSkill(Skill):
    name = "my_customers"
    description = "查看我的客户、客户列表、名下客户"

    def execute(self, **kwargs):
        return """
👥 我的客户列表：
1. 上海电子科技 | 线路：上海→广州
2. 苏州服装批发 | 线路：苏州→北京
3. 杭州电商仓   | 线路：杭州→成都
"""

class RiskCustomersSkill(Skill):
    name = "risk_customers"
    description = "查询风险客户、流失客户、发货下滑客户"

    def execute(self, **kwargs):
        return "⚠️ 高风险客户：杭州电商仓（发货量环比下降 23%）"

class HighValueCustomersSkill(Skill):
    name = "high_value_customers"
    description = "查询高价值客户、高利润客户、大客户"

    def execute(self,** kwargs):
        return "💰 高价值客户：上海电子科技、苏州服装批发、宁波五金"

class QueryRoutesSkill(Skill):
    name = "query_routes"
    description = "查询物流线路、主营线路、运输路线"

    def execute(self,** kwargs):
        return """
🚚 主营线路：
上海→广州
苏州→北京
杭州→成都
宁波→武汉
"""

# --------------------------
# 5. 你的 LLM 配置（完全保留）
# --------------------------
llm = LangChainLLM(
    ChatOpenAI(
        model="gpt-5.4",
        api_key="os.getenv('AI_KEY')",
        base_url="https://api.heabl.top/v1",
        temperature=0.7,
    )
)

# --------------------------
# 6. 启动
# --------------------------
if __name__ == "__main__":
    agent = MiniDeepAgent(llm)

    agent.add_skill(SalesWeeklySkill())
    agent.add_skill(MyCustomersSkill())
    agent.add_skill(RiskCustomersSkill())
    agent.add_skill(HighValueCustomersSkill())
    agent.add_skill(QueryRoutesSkill())

    print("=" * 60)
    print("    物流销售智能体 · 大模型意图识别版")
    print("=" * 60)

    test_querys = [
        "帮我生成周报",
        "我要看看我的客户",
        "哪些客户快流失了",
        "大客户有哪些",
        "我们有哪些运输线路",
        "你好呀"
    ]

    for q in test_querys:
        print(f"\n🧑‍💼 你：{q}")
        print(f"🤖 AI：{agent.run(q)}")