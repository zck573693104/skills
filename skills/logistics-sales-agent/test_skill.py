#!/usr/bin/env python3
"""
物流销售 Agent 测试脚本
演示各种使用场景
"""

import subprocess
import json
import sys


def run_command(cmd):
    """执行命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"🔧 执行: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return data
        except:
            print(result.stdout)
            return result.stdout
    else:
        print(f"❌ 错误: {result.stderr}")
        return None


def test_quote():
    """测试报价查询"""
    print("\n" + "="*60)
    print("📦 测试 1: 基础报价查询")
    print("="*60)
    
    # 测试 1.1: 零担报价
    run_command([
        sys.executable, "scripts/quote.py",
        "--from", "上海",
        "--to", "北京",
        "--type", "ltl",
        "--weight", "300"
    ])
    
    # 测试 1.2: 整车报价
    run_command([
        sys.executable, "scripts/quote.py",
        "--from", "上海",
        "--to", "广州",
        "--type", "ftl"
    ])
    
    # 测试 1.3: 大客户折扣
    run_command([
        sys.executable, "scripts/quote.py",
        "--from", "上海",
        "--to", "北京",
        "--type", "both",
        "--weight", "500",
        "--monthly-volume", "100000"
    ])


def test_tracking():
    """测试运单追踪"""
    print("\n" + "="*60)
    print("🚚 测试 2: 运单追踪")
    print("="*60)
    
    # 测试 2.1: 已签收运单
    run_command([
        sys.executable, "scripts/track.py",
        "--waybill", "SF2026040101234"
    ])
    
    # 测试 2.2: 派送中运单
    run_command([
        sys.executable, "scripts/track.py",
        "--waybill", "SF2026040512345"
    ])
    
    # 测试 2.3: 异常运单
    run_command([
        sys.executable, "scripts/track.py",
        "--waybill", "SF2026033012345"
    ])


def test_customer():
    """测试客户管理"""
    print("\n" + "="*60)
    print("👥 测试 3: 客户管理")
    print("="*60)
    
    # 测试 3.1: 列出所有客户
    run_command([
        sys.executable, "scripts/customer.py",
        "--list"
    ])
    
    # 测试 3.2: 查询客户详情
    run_command([
        sys.executable, "scripts/customer.py",
        "--get", "C001"
    ])
    
    # 测试 3.3: 跟进提醒
    run_command([
        sys.executable, "scripts/customer.py",
        "--followup",
        "--days", "3"
    ])
    
    # 测试 3.4: 搜索客户
    run_command([
        sys.executable, "scripts/customer.py",
        "--search", "蓝鲸"
    ])


def test_integration():
    """测试 DeepAgent 集成"""
    print("\n" + "="*60)
    print("🤖 测试 4: DeepAgent 集成（需要安装依赖）")
    print("="*60)
    
    try:
        from deep_agent import DeepAgent
        
        agent = DeepAgent("./skills")
        
        # 测试场景 1: 报价查询
        print("\n💬 用户: 帮我查一下从上海到北京的运价，300kg")
        response = agent.chat("帮我查一下从上海到北京的运价，300kg")
        print(f"🤖 Agent: {response[:200]}...")
        
        # 测试场景 2: 运单追踪
        print("\n💬 用户: 帮我查一下SF2026040512345到哪了")
        response = agent.chat("帮我查一下SF2026040512345到哪了")
        print(f"🤖 Agent: {response[:200]}...")
        
        # 测试场景 3: 客户跟进
        print("\n💬 用户: 今天需要跟进哪些客户？")
        response = agent.chat("今天需要跟进哪些客户？")
        print(f"🤖 Agent: {response[:200]}...")
        
    except ImportError as e:
        print(f"⚠️  跳过集成测试: {e}")
        print("提示: 运行 'pip install langchain-openai pyyaml' 以启用")


def main():
    """运行所有测试"""
    print("="*60)
    print("🧪 物流销售 Agent 测试套件")
    print("="*60)
    
    # 切换到 skill 目录
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 运行测试
    test_quote()
    test_tracking()
    test_customer()
    test_integration()
    
    print("\n" + "="*60)
    print("✅ 测试完成！")
    print("="*60)


if __name__ == "__main__":
    main()
