# ==============================================
# OpenClaw Agent - 自动加载技能并执行
# 整合 doubao.py 和 skill_loader.py 的功能
# ==============================================

from typing import Dict, Any, List
from doubao import BaseLLM, LangChainLLM, ChatOpenAI, MiniDeepAgent, Skill
from skill_loader import SkillLoader, SkillMetadata
import os
from pathlib import Path


class OpenClawAgent:
    """
    OpenClaw Agent - 自动加载技能并执行
    """
    
    def __init__(self, skills_dir: str = "D:\\python_project\\test_skills"):
        """
        初始化 OpenClaw Agent
        
        Args:
            skills_dir: 技能目录路径
        """
        # 初始化 LLM
        llm = LangChainLLM(
            ChatOpenAI(
                model="grok-4.1-thinking",
                api_key="os.getenv('AI_KEY')",
                base_url="https://api.heabl.top/v1",
                temperature=0.7,
            )
        )
        
        # 初始化 MiniDeepAgent
        self.agent = MiniDeepAgent(llm)
        
        # 使用绝对路径初始化技能加载器
        print(f"使用技能目录: {skills_dir}")
        
        # 初始化技能加载器
        self.skill_loader = SkillLoader(skills_dir)
        
        # 加载技能
        self._load_skills()
    
    def _load_skills(self):
        """
        加载所有技能
        """
        print(f"\n🚀 正在加载技能...")
        print(f"技能目录: {self.skill_loader.skills_root}")
        print(f"技能目录是否存在: {self.skill_loader.skills_root.exists()}")
        
        # 手动扫描技能目录
        if self.skill_loader.skills_root.exists():
            print("\n扫描技能目录:")
            for skill_dir in self.skill_loader.skills_root.iterdir():
                if skill_dir.is_dir():
                    skill_md_path = skill_dir / "SKILL.md"
                    print(f"  - {skill_dir.name}: {'有SKILL.md' if skill_md_path.exists() else '无SKILL.md'}")
        
        skills = self.skill_loader.list_skills()
        print(f"\n发现的技能数量: {len(skills)}")
        
        for skill_metadata in skills:
            # 创建技能实例
            skill = self._create_skill_from_metadata(skill_metadata)
            if skill:
                self.agent.add_skill(skill)
                print(f"✓ 加载技能: {skill.name} - {skill.description}")
        
        print(f"\n✅ 技能加载完成，共加载 {len(skills)} 个技能")
    
    def _create_skill_from_metadata(self, metadata: SkillMetadata) -> Skill:
        """
        根据元数据创建技能实例（实现渐进式披露）
        
        Args:
            metadata: 技能元数据
            
        Returns:
            Skill 实例
        """
        class DynamicSkill(Skill):
            name = metadata.name
            description = metadata.description
            
            def execute(self, **kwargs):
                # 渐进式披露 Level 1: 基本信息
                result = f"执行技能: {self.name}\n描述: {self.description}\n路径: {metadata.path}\n"
                
                # 渐进式披露 Level 2: 加载完整内容
                content = self.__class__.agent.skill_loader.get_skill_content(self.name)
                if content:
                    result += "\n【技能完整内容】\n"
                    result += content[:500] + "..." if len(content) > 500 else content
                
                # 渐进式披露 Level 3: 加载资源文件
                resources = self.__class__.agent.skill_loader.get_skill_resources(self.name)
                if resources:
                    result += "\n【技能资源】\n"
                    if resources.get("scripts"):
                        result += "脚本文件: " + ", ".join([Path(p).name for p in resources["scripts"]]) + "\n"
                    if resources.get("references"):
                        result += "参考资料: " + ", ".join([Path(p).name for p in resources["references"]]) + "\n"
                    if resources.get("assets"):
                        result += "资产文件: " + ", ".join([Path(p).name for p in resources["assets"]]) + "\n"
                
                # 渐进式披露 Level 4: 执行脚本
                scripts_dir = Path(metadata.path) / "scripts"
                if scripts_dir.exists():
                    result += "\n【执行脚本】\n"
                    for script_file in scripts_dir.iterdir():
                        if script_file.is_file() and script_file.suffix == ".py":
                            try:
                                # 解析用户输入，提取参数
                                input_text = kwargs.get('input', '')
                                
                                # 使用大模型识别和解析参数
                                import subprocess
                                import sys
                                
                                # 构建参数解析提示
                                prompt = f"""
                                你是一个参数解析助手，需要从用户输入中提取脚本执行所需的参数。
                                
                                脚本文件: {script_file.name}
                                用户输入: {input_text}
                                
                                请分析脚本的功能，从用户输入中提取相关参数，并以JSON格式返回参数名和值。
                                例如：
                                - 对于查询运价的脚本，提取出发地和目的地
                                - 对于查询运单的脚本，提取运单号
                                - 对于查询客户的脚本，提取客户名称或ID
                                
                                只返回JSON，不要有其他解释。
                                """
                                
                                # 为不同脚本设置参数
                                params = {}
                                
                                if 'quote' in script_file.name.lower():
                                    # 从用户输入中提取出发地和目的地
                                    import re
                                    # 匹配各种格式的出发地和目的地
                                    patterns = [
                                        r'@\w+\s*(.*?)[到至](.*?)的运单价格',
                                        r'@\w+\s*(.*?)[到至](.*?)的运价',
                                        r'@\w+\s*(.*?)[到至](.*?)多少钱',
                                        r'(.*?)[到至](.*?)的运单价格',
                                        r'(.*?)[到至](.*?)的运价',
                                        r'(.*?)[到至](.*?)多少钱'
                                    ]
                                    
                                    origin = None
                                    dest = None
                                    for pattern in patterns:
                                        match = re.search(pattern, input_text)
                                        if match:
                                            # 提取匹配的出发地和目的地
                                            for i in range(1, len(match.groups()), 2):
                                                if match.group(i) and match.group(i+1):
                                                    origin = match.group(i).strip()
                                                    dest = match.group(i+1).strip()
                                                    break
                                        if origin and dest:
                                            break
                                    
                                    # 如果没有提取到，使用默认值
                                    if not origin or not dest:
                                        # 从用户输入中简单提取
                                        if '上海' in input_text and '北京' in input_text:
                                            origin = '上海'
                                            dest = '北京'
                                        elif '北京' in input_text and '上海' in input_text:
                                            origin = '北京'
                                            dest = '上海'
                                        else:
                                            origin = '上海'
                                            dest = '北京'
                                    
                                    params['origin'] = origin
                                    params['destination'] = dest
                                elif 'customer' in script_file.name.lower():
                                    # 客户管理脚本，使用 --list 参数
                                    params['list'] = True
                                elif 'track' in script_file.name.lower():
                                    # 运单追踪脚本，使用默认运单号
                                    params['waybill'] = 'SF1234567890'
                                
                                # 根据脚本名称构建命令
                                cmd = [sys.executable, str(script_file)]
                                
                                # 添加参数
                                if 'quote' in script_file.name.lower() or 'price' in script_file.name.lower():
                                    # 运价查询脚本
                                    origin = params.get('origin', params.get('出发地', ''))
                                    dest = params.get('destination', params.get('目的地', ''))
                                    if origin and dest:
                                        cmd.extend(["--from", origin, "--to", dest])
                                elif 'track' in script_file.name.lower():
                                    # 运单追踪脚本
                                    waybill = params.get('waybill', params.get('运单号', ''))
                                    if waybill:
                                        cmd.extend(["--waybill", waybill])
                                elif 'customer' in script_file.name.lower():
                                    # 客户查询脚本
                                    if params.get('list'):
                                        cmd.extend(["--list"])
                                    else:
                                        customer_id = params.get('customer_id', params.get('客户ID', ''))
                                        if customer_id:
                                            cmd.extend(["--get", customer_id])
                                
                                # 执行脚本
                                try:
                                    # 使用二进制模式执行脚本，避免编码问题
                                    process = subprocess.run(cmd, capture_output=True)
                                    
                                    if process.returncode == 0:
                                        # 尝试使用不同编码解码输出
                                        output = ""
                                        try:
                                            output = process.stdout.decode('utf-8')
                                        except UnicodeDecodeError:
                                            try:
                                                output = process.stdout.decode('gbk')
                                            except UnicodeDecodeError:
                                                output = process.stdout.decode('utf-8', errors='ignore')
                                        
                                        if not output:
                                            output = "执行成功，但无输出"
                                        result += f"✓ 执行 {script_file.name}:\n{output}\n"
                                    else:
                                        # 尝试使用不同编码解码错误信息
                                        error = ""
                                        try:
                                            error = process.stderr.decode('utf-8')
                                        except UnicodeDecodeError:
                                            try:
                                                error = process.stderr.decode('gbk')
                                            except UnicodeDecodeError:
                                                error = process.stderr.decode('utf-8', errors='ignore')
                                        
                                        if not error:
                                            error = "执行失败，但无错误信息"
                                        result += f"⚠️ 执行 {script_file.name} 失败:\n{error}\n"
                                except Exception as e:
                                    result += f"⚠️ 执行 {script_file.name} 失败: {str(e)}\n"
                            except Exception as e:
                                result += f"⚠️ 执行 {script_file.name} 失败: {str(e)}\n"
                
                return result
        
        # 为 DynamicSkill 添加 agent 引用
        DynamicSkill.agent = self
        
        return DynamicSkill()
    
    def run(self, user_input: str):
        """
        运行 Agent，处理用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            执行结果
        """
        # 检查用户是否指定了技能
        if "@" in user_input:
            # 格式: @skill_name 问题
            parts = user_input.split(" ", 1)
            if len(parts) >= 2:
                skill_name = parts[0].strip("@")
                # 直接执行指定的技能，传递用户输入
                return self.agent.skill_manager.execute_skill(skill_name, input=user_input)
        
        # 否则使用大模型自动识别意图
        return self.agent.run(user_input)
    
    def list_skills(self):
        """
        列出所有已加载的技能
        
        Returns:
            技能列表
        """
        return self.agent.skill_manager.get_skill_list()


if __name__ == "__main__":
    # 初始化 OpenClaw Agent
    agent = OpenClawAgent()
    
    print("=" * 60)
    print("    OpenClaw Agent - 自动加载技能系统")
    print("=" * 60)
    print("使用方式:")
    print("1. 直接提问，系统会自动识别意图")
    print("2. 使用 @skill_name 格式指定技能")
    print("3. 输入 'exit' 退出")
    print("=" * 60)
    
    # 显示已加载的技能
    print("\n📋 已加载的技能:")
    for skill in agent.list_skills():
        print(f"  - @{skill['name']}: {skill['desc']}")
    
    print("\n💬 开始对话:")
    
    # 交互式对话
    while True:
        user_input = input("🧑‍💼 你: ")
        
        if user_input.lower() == "exit":
            print("👋 再见！")
            break
        
        result = agent.run(user_input)
        print(f"🤖 AI: {result}")
        print()
