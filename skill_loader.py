"""
DeepAgent Skill 加载器 - 动态加载和管理 Skills (v2.0)
基于 LangChain DeepAgents 框架的 Skill 系统实现

注意: 此模块已与 workbuddy.py 中的 SkillRegistry 合并
      保留此文件仅为兼容性考虑，建议使用 workbuddy.SkillRegistry
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import yaml


@dataclass
class SkillMetadata:
    """Skill 元数据"""
    name: str
    description: str
    path: str
    tags: List[str] = field(default_factory=list)
    owner: str = ""
    version: str = "1.0.0"
    inputs: List[Dict] = field(default_factory=list)
    outputs: List[Dict] = field(default_factory=list)
    requires: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "tags": self.tags,
            "owner": self.owner,
            "version": self.version,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "requires": self.requires
        }


class SkillParser:
    """SKILL.md 文件解析器"""
    
    @staticmethod
    def parse_skill_file(file_path: str) -> Optional[SkillMetadata]:
        """
        解析 SKILL.md 文件，提取元数据和指令
        
        Args:
            file_path: SKILL.md 文件的完整路径
            
        Returns:
            SkillMetadata 对象，如果解析失败则返回 None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否以 --- 开头（YAML frontmatter）
            if not content.startswith('---'):
                print(f"警告: {file_path} 不是有效的 SKILL.md 文件格式")
                return None
            
            # 提取 YAML frontmatter
            match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
            if not match:
                print(f"警告: {file_path} YAML frontmatter 格式错误")
                return None
            
            yaml_content = match.group(1)
            markdown_content = match.group(2)
            
            # 解析 YAML
            metadata_dict = yaml.safe_load(yaml_content)
            
            # 提取基本信息
            skill_path = Path(file_path).parent
            metadata = SkillMetadata(
                name=metadata_dict.get('name', skill_path.name),
                description=metadata_dict.get('description', ''),
                path=str(skill_path),
                tags=metadata_dict.get('tags', []),
                owner=metadata_dict.get('owner', ''),
                version=metadata_dict.get('version', '1.0.0'),
                inputs=metadata_dict.get('inputs', []),
                outputs=metadata_dict.get('outputs', []),
                requires=metadata_dict.get('metadata', {}).get('openclaw', {}).get('requires', {})
            )
            
            return metadata
            
        except Exception as e:
            print(f"解析 SKILL.md 文件失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def get_full_content(file_path: str) -> Optional[str]:
        """
        获取 SKILL.md 的完整内容（用于渐进式披露 Level 2）
        
        Args:
            file_path: SKILL.md 文件的完整路径
            
        Returns:
            完整的 Markdown 内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"读取 SKILL.md 文件失败 {file_path}: {e}")
            return None


class SkillLoader:
    """
    Skill 加载器 - 负责扫描、发现和加载 Skills
    
    支持多层次渐进式上下文加载:
    - Level 1: 仅加载元数据（名称、描述），用于快速匹配
    - Level 2: 加载完整的 SKILL.md 内容
    - Level 3: 加载参考资料和资源文件
    - Level 4: 分析上下文并准备执行脚本
    
    注意: 此类已废弃，请使用 workbuddy.SkillRegistry + SkillDisclosure
    """
    
    def __init__(self, skills_root_dir: str):
        """
        初始化 Skill 加载器
        
        Args:
            skills_root_dir: Skills 根目录路径
        """
        self.skills_root = Path(skills_root_dir)
        self.skills_metadata: Dict[str, SkillMetadata] = {}
        self._scan_skills()
    
    def _scan_skills(self):
        """扫描技能目录，发现所有可用的 Skills"""
        if not self.skills_root.exists():
            print(f"警告: Skills 目录不存在: {self.skills_root}")
            return
        
        # 遍历所有子目录
        for skill_dir in self.skills_root.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md_path = skill_dir / "SKILL.md"
            if skill_md_path.exists():
                metadata = SkillParser.parse_skill_file(str(skill_md_path))
                if metadata:
                    self.skills_metadata[metadata.name] = metadata
                    print(f"✓ 发现 Skill: {metadata.name} ({metadata.description[:50]}...)")
    
    def list_skills(self) -> List[SkillMetadata]:
        """
        列出所有已加载的 Skills
        
        Returns:
            SkillMetadata 列表
        """
        return list(self.skills_metadata.values())
    
    def get_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """
        获取指定 Skill 的元数据（Level 1 加载）
        
        Args:
            skill_name: Skill 名称
            
        Returns:
            SkillMetadata 对象，如果不存在则返回 None
        """
        return self.skills_metadata.get(skill_name)
    
    def get_skill_content(self, skill_name: str) -> Optional[str]:
        """
        获取指定 Skill 的完整内容（Level 2 加载）
        
        Args:
            skill_name: Skill 名称
            
        Returns:
            完整的 SKILL.md 内容
        """
        metadata = self.skills_metadata.get(skill_name)
        if not metadata:
            return None
        
        skill_md_path = Path(metadata.path) / "SKILL.md"
        return SkillParser.get_full_content(str(skill_md_path))
    
    def search_skills(self, query: str) -> List[SkillMetadata]:
        """
        根据关键词搜索 Skills
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的 SkillMetadata 列表
        """
        query_lower = query.lower()
        matched_skills = []
        
        for skill in self.skills_metadata.values():
            # 在名称、描述、标签中搜索
            if (query_lower in skill.name.lower() or 
                query_lower in skill.description.lower() or
                any(query_lower in tag.lower() for tag in skill.tags)):
                matched_skills.append(skill)
        
        return matched_skills
    
    def check_skill_requirements(self, skill_name: str) -> Dict[str, bool]:
        """
        检查 Skill 的运行依赖是否满足
        
        Args:
            skill_name: Skill 名称
            
        Returns:
            依赖检查结果字典
        """
        metadata = self.skills_metadata.get(skill_name)
        if not metadata:
            return {"valid": False, "message": f"Skill '{skill_name}' 不存在"}
        
        results = {
            "valid": True,
            "bins": {},
            "env": {}
        }
        
        requires = metadata.requires
        
        # 检查二进制文件/命令是否存在
        if "bins" in requires:
            for bin_name in requires["bins"]:
                # 简单检查：尝试在 PATH 中查找
                import shutil
                exists = shutil.which(bin_name) is not None
                results["bins"][bin_name] = exists
                if not exists:
                    results["valid"] = False
        
        # 检查环境变量
        if "env" in requires:
            for env_var in requires["env"]:
                exists = env_var in os.environ
                results["env"][env_var] = exists
                if not exists:
                    results["valid"] = False
        
        return results
    
    def get_skill_resources(self, skill_name: str) -> Dict[str, List[str]]:
        """
        获取 Skill 的资源文件列表（Level 3 加载）
        
        Args:
            skill_name: Skill 名称
            
        Returns:
            资源文件字典，包含 scripts、references、assets 等
        """
        metadata = self.skills_metadata.get(skill_name)
        if not metadata:
            return {}
        
        skill_path = Path(metadata.path)
        resources = {
            "scripts": [],
            "references": [],
            "assets": []
        }
        
        # 扫描 scripts 目录
        scripts_dir = skill_path / "scripts"
        if scripts_dir.exists():
            resources["scripts"] = [str(f) for f in scripts_dir.rglob("*") if f.is_file()]
        
        # 扫描 references 目录
        refs_dir = skill_path / "references"
        if refs_dir.exists():
            resources["references"] = [str(f) for f in refs_dir.rglob("*") if f.is_file()]
        
        # 扫描 assets 目录
        assets_dir = skill_path / "assets"
        if assets_dir.exists():
            resources["assets"] = [str(f) for f in assets_dir.rglob("*") if f.is_file()]
        
        return resources


if __name__ == "__main__":
    # 测试代码
    import json
    
    # 初始化加载器
    loader = SkillLoader("./skills")
    
    print("\n" + "="*60)
    print("已加载的 Skills:")
    print("="*60)
    
    for skill in loader.list_skills():
        print(f"\n📦 {skill.name}")
        print(f"   描述: {skill.description}")
        print(f"   路径: {skill.path}")
        print(f"   版本: {skill.version}")
        
        # 检查依赖
        req_check = loader.check_skill_requirements(skill.name)
        if not req_check["valid"]:
            print(f"   ⚠️  依赖检查失败:")
            if req_check["bins"]:
                for bin_name, exists in req_check["bins"].items():
                    if not exists:
                        print(f"      - 缺少命令: {bin_name}")
            if req_check["env"]:
                for env_name, exists in req_check["env"].items():
                    if not exists:
                        print(f"      - 缺少环境变量: {env_name}")
    
    print("\n" + "="*60)
    print("搜索示例: 'search'")
    print("="*60)
    search_results = loader.search_skills("search")
    for skill in search_results:
        print(f"  - {skill.name}: {skill.description}")
