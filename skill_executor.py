"""
DeepAgent Skill 执行引擎 - 负责执行 Skills (v2.0)
支持多种执行方式：Python 脚本、Shell 命令等

注意: 此模块已与 workbuddy.py 中的 ScriptRunner 合并
      保留此文件仅为兼容性考虑，建议使用 workbuddy.ScriptRunner
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import traceback

from skill_loader import SkillLoader


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SkillExecutor:
    """
    Skill 执行引擎
    
    负责:
    1. 验证 Skill 依赖
    2. 准备执行环境
    3. 执行 Skill 脚本
    4. 处理执行结果
    
    注意: 此类已废弃，请使用 workbuddy.ScriptRunner + ParamExtractor
    """
    
    def __init__(self, skills_root_dir: str):
        """
        初始化执行引擎
        
        Args:
            skills_root_dir: Skills 根目录路径
        """
        self.loader = SkillLoader(skills_root_dir)
        self.execution_history: List[Dict] = []
    
    def execute_skill(self, skill_name: str, arguments: Dict[str, Any] = None, 
                     script_name: str = None) -> ExecutionResult:
        """
        执行指定的 Skill
        
        Args:
            skill_name: Skill 名称
            arguments: 传递给 Skill 的参数
            script_name: 要执行的脚本名称（可选，默认查找主脚本）
            
        Returns:
            ExecutionResult 执行结果对象
        """
        print(f"\n🚀 开始执行 Skill: {skill_name}")
        
        # 1. 检查 Skill 是否存在
        metadata = self.loader.get_skill_metadata(skill_name)
        if not metadata:
            return ExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' 不存在"
            )
        
        # 2. 检查依赖
        req_check = self.loader.check_skill_requirements(skill_name)
        if not req_check["valid"]:
            error_msg = "依赖检查失败:\n"
            for bin_name, exists in req_check.get("bins", {}).items():
                if not exists:
                    error_msg += f"  - 缺少命令: {bin_name}\n"
            for env_name, exists in req_check.get("env", {}).items():
                if not exists:
                    error_msg += f"  - 缺少环境变量: {env_name}\n"
            
            return ExecutionResult(
                success=False,
                error=error_msg
            )
        
        # 3. 获取资源文件
        resources = self.loader.get_skill_resources(skill_name)
        scripts = resources.get("scripts", [])
        
        if not scripts:
            return ExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' 没有可用的脚本文件"
            )
        
        # 4. 确定要执行的脚本
        if script_name:
            # 使用指定的脚本
            target_script = None
            for script_path in scripts:
                if script_path.endswith(script_name):
                    target_script = script_path
                    break
            
            if not target_script:
                return ExecutionResult(
                    success=False,
                    error=f"在 Skill '{skill_name}' 中找不到脚本: {script_name}"
                )
        else:
            # 自动选择第一个 Python 或 Shell 脚本
            target_script = self._select_main_script(scripts)
            if not target_script:
                return ExecutionResult(
                    success=False,
                    error=f"在 Skill '{skill_name}' 中找不到可执行的主脚本"
                )
        
        print(f"   📜 执行脚本: {target_script}")
        
        # 5. 执行脚本
        try:
            result = self._run_script(target_script, arguments, metadata.path)
            
            # 6. 记录执行历史
            self.execution_history.append({
                "skill": skill_name,
                "script": target_script,
                "arguments": arguments,
                "success": result.success,
                "exit_code": result.exit_code
            })
            
            return result
            
        except Exception as e:
            error_traceback = traceback.format_exc()
            return ExecutionResult(
                success=False,
                error=f"执行异常: {str(e)}\n{error_traceback}"
            )
    
    def _select_main_script(self, scripts: List[str]) -> Optional[str]:
        """
        从脚本列表中选择主脚本
        
        优先级:
        1. main.py
        2. search.py (常见命名)
        3. 第一个 .py 文件
        4. 第一个 .sh 文件
        
        Args:
            scripts: 脚本文件路径列表
            
        Returns:
            选中的脚本路径
        """
        # 优先查找常见的主脚本名称
        priority_names = ["main.py", "search.py", "run.py", "execute.py"]
        
        for priority_name in priority_names:
            for script in scripts:
                if script.endswith(priority_name):
                    return script
        
        # 其次选择第一个 Python 脚本
        for script in scripts:
            if script.endswith(".py"):
                return script
        
        # 最后选择第一个 Shell 脚本
        for script in scripts:
            if script.endswith(".sh"):
                return script
        
        return None
    
    def _run_script(self, script_path: str, arguments: Dict[str, Any], 
                   skill_dir: str) -> ExecutionResult:
        """
        运行脚本文件
        
        Args:
            script_path: 脚本文件路径
            arguments: 参数字典
            skill_dir: Skill 目录路径
            
        Returns:
            ExecutionResult 执行结果
        """
        script_ext = Path(script_path).suffix.lower()
        
        if script_ext == ".py":
            return self._run_python_script(script_path, arguments, skill_dir)
        elif script_ext == ".sh":
            return self._run_shell_script(script_path, arguments, skill_dir)
        else:
            return ExecutionResult(
                success=False,
                error=f"不支持的脚本类型: {script_ext}"
            )
    
    def _run_python_script(self, script_path: str, arguments: Dict[str, Any],
                          skill_dir: str) -> ExecutionResult:
        """
        运行 Python 脚本
        
        Args:
            script_path: Python 脚本路径
            arguments: 参数字典
            skill_dir: Skill 目录路径
            
        Returns:
            ExecutionResult 执行结果
        """
        try:
            # 构建命令
            cmd = [sys.executable, script_path]
            
            # 如果有参数，将其转换为 JSON 字符串传递
            if arguments:
                json_args = json.dumps(arguments, ensure_ascii=False)
                cmd.append(json_args)
            
            print(f"   💻 执行命令: {' '.join(cmd)}")
            
            # 设置工作目录为 skill 目录
            env = os.environ.copy()
            env["PYTHONPATH"] = skill_dir + os.pathsep + env.get("PYTHONPATH", "")
            
            # 执行脚本
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',  # 明确指定 UTF-8 编码，避免 Windows GBK 解码错误
                errors='replace',  # 遇到无法解码的字符用替换字符
                timeout=300,  # 5分钟超时
                cwd=skill_dir,
                env=env
            )
            
            # 处理结果
            if process.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=process.stdout,
                    exit_code=process.returncode,
                    metadata={
                        "stderr": process.stderr if process.stderr else ""
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    output=process.stdout,
                    error=process.stderr,
                    exit_code=process.returncode
                )
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error="脚本执行超时 (300秒)"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"执行 Python 脚本失败: {str(e)}"
            )
    
    def _run_shell_script(self, script_path: str, arguments: Dict[str, Any],
                         skill_dir: str) -> ExecutionResult:
        """
        运行 Shell 脚本
        
        Args:
            script_path: Shell 脚本路径
            arguments: 参数字典
            skill_dir: Skill 目录路径
            
        Returns:
            ExecutionResult 执行结果
        """
        try:
            # 构建命令
            cmd = ["bash", script_path]
            
            # 如果有参数，通过环境变量传递
            env = os.environ.copy()
            if arguments:
                for key, value in arguments.items():
                    env[f"SKILL_ARG_{key.upper()}"] = str(value)
            
            print(f"   💻 执行命令: {' '.join(cmd)}")
            
            # 执行脚本
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',  # 明确指定 UTF-8 编码，避免 Windows GBK 解码错误
                errors='replace',  # 遇到无法解码的字符用替换字符
                timeout=300,
                cwd=skill_dir,
                env=env
            )
            
            # 处理结果
            if process.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=process.stdout,
                    exit_code=process.returncode,
                    metadata={
                        "stderr": process.stderr if process.stderr else ""
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    output=process.stdout,
                    error=process.stderr,
                    exit_code=process.returncode
                )
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error="脚本执行超时 (300秒)"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"执行 Shell 脚本失败: {str(e)}"
            )
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            执行统计信息
        """
        total = len(self.execution_history)
        successful = sum(1 for h in self.execution_history if h["success"])
        failed = total - successful
        
        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": f"{(successful/total*100):.1f}%" if total > 0 else "0%",
            "history": self.execution_history[-10:]  # 最近10次执行
        }


def demo_execute():
    """演示执行各种 Skills"""
    
    print("="*70)
    print("DeepAgent Skill 执行引擎演示")
    print("="*70)
    
    # 初始化执行引擎
    executor = SkillExecutor("./skills")
    
    # 示例 1: 执行百度搜索 Skill
    print("\n" + "="*70)
    print("示例 1: 执行百度搜索 Skill")
    print("="*70)
    
    # 注意: 需要设置 BAIDU_API_KEY 环境变量
    if "BAIDU_API_KEY" not in os.environ:
        print("⚠️  跳过: 未设置 BAIDU_API_KEY 环境变量")
    else:
        result = executor.execute_skill(
            skill_name="baidu-search",
            arguments={"query": "人工智能最新发展", "count": 5}
        )
        
        if result.success:
            print("✅ 执行成功!")
            print("输出:")
            print(result.output[:500])  # 只显示前500字符
        else:
            print("❌ 执行失败:")
            print(result.error)
    
    # 示例 2: 执行数据分析 Skill
    print("\n" + "="*70)
    print("示例 2: 执行数据分析 Skill")
    print("="*70)
    
    # 注意: 需要设置数据库相关环境变量
    required_env_vars = ["SR_HOST", "SR_PORT", "SR_USER", "SR_PASSWORD"]
    missing_vars = [var for var in required_env_vars if var not in os.environ]
    
    if missing_vars:
        print(f"⚠️  跳过: 缺少环境变量: {', '.join(missing_vars)}")
    else:
        result = executor.execute_skill(
            skill_name="zck-data-analysis",
            arguments={},
            script_name="search.py"
        )
        
        if result.success:
            print("✅ 执行成功!")
            print("输出:")
            print(result.output[:500])
        else:
            print("❌ 执行失败:")
            print(result.error)
    
    # 打印执行摘要
    print("\n" + "="*70)
    print("执行摘要")
    print("="*70)
    summary = executor.get_execution_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo_execute()
