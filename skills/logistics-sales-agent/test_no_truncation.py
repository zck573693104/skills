#!/usr/bin/env python3
"""
测试数据截断修复 - 验证完整数据是否能正确传递
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_agent import DeepAgent


def test_no_truncation():
    """测试报价数据是否完整返回"""
    
    print("="*70)
    print("🧪 测试数据截断修复")
    print("="*70)
    
    # 初始化 Agent
    agent = DeepAgent("./skills")
    
    # 测试场景：查询整车报价（数据量大）
    print("\n💬 用户: 帮我查一下从上海到北京的整车报价")
    print("-"*70)
    
    response = agent.chat("帮我查一下从上海到北京的整车报价")
    
    print(f"\n🤖 Agent 回复长度: {len(response)} 字符")
    print(f"\n📊 回复内容预览:")
    print("-"*70)
    
    # 检查是否包含关键信息
    checks = {
        "4.2米厢车": "4.2米厢车" in response,
        "9.6米厢车": "9.6米厢车" in response,
        "17.5米平板": "17.5米平板" in response,
        "尺寸信息": "米×" in response or "长" in response,
        "容积信息": "立方米" in response or "容积" in response,
        "限重信息": "吨" in response or "限重" in response,
        "价格信息": "元" in response,
    }
    
    print("\n✅ 数据完整性检查:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}: {'通过' if passed else '失败'}")
        if not passed:
            all_passed = False
    
    print(f"\n📝 完整回复:")
    print("-"*70)
    print(response)
    print("-"*70)
    
    if all_passed:
        print("\n🎉 测试通过！数据完整，无截断。")
    else:
        print("\n⚠️  测试警告：部分数据可能缺失。")
    
    print("\n" + "="*70)
    
    return all_passed


if __name__ == "__main__":
    success = test_no_truncation()
    sys.exit(0 if success else 1)
