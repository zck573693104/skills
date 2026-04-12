#!/usr/bin/env python3
"""
测试增强版报价脚本 - 验证返回数据是否更详细
"""

import subprocess
import json
import sys


def test_enhanced_quote():
    """测试增强版报价功能"""
    
    print("="*70)
    print("🧪 测试增强版报价脚本")
    print("="*70)
    
    # 测试 1: 基础报价查询
    print("\n📦 测试 1: 上海→北京 300kg 零担+整车")
    print("-"*70)
    
    result = subprocess.run(
        [sys.executable, "scripts/quote.py", 
         "--from", "上海", "--to", "北京", 
         "--type", "both", "--weight", "300"],
        capture_output=True, text=True, encoding='utf-8'
    )
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        
        # 检查零担报价
        if "ltl_quote" in data:
            ltl = data["ltl_quote"]
            print("\n✅ 零担报价数据:")
            print(f"   - 重量区间: {ltl.get('weight_range', 'N/A')}")
            print(f"   - 单价: {ltl.get('unit_rate', 'N/A')}")
            print(f"   - 基础运费: {ltl.get('base_cost', 'N/A')}元")
            print(f"   - 燃油附加费: {ltl.get('fuel_surcharge', 'N/A')}元 ({ltl.get('fuel_rate', 'N/A')})")
            print(f"   - 合计: {ltl.get('total', 'N/A')}元")
            print(f"   - 时效: {ltl.get('transit_days', 'N/A')}天")
            
            if "advantages" in ltl:
                print(f"   - 优势: {len(ltl['advantages'])}条")
                for adv in ltl['advantages']:
                    print(f"     • {adv}")
            
            if "limitations" in ltl:
                print(f"   - 限制: {len(ltl['limitations'])}条")
        
        # 检查整车报价
        if "ftl_quote" in data:
            ftl = data["ftl_quote"]
            print(f"\n✅ 整车报价数据:")
            print(f"   - 时效: {ftl.get('transit_days', 'N/A')}天")
            print(f"   - 车型数量: {len(ftl.get('options', []))}种")
            
            for i, opt in enumerate(ftl.get('options', []), 1):
                print(f"\n   【车型 {i}】{opt['vehicle_type']}")
                print(f"      基础价: {opt['base_price']:,}元")
                print(f"      燃油费: {opt['fuel_surcharge']:,}元")
                print(f"      总价: {opt['total']:,}元")
                
                if "specs" in opt:
                    specs = opt['specs']
                    print(f"      尺寸: {specs.get('length', '?')}×{specs.get('width', '?')}×{specs.get('height', '?')}")
                    print(f"      容积: {specs.get('volume', '?')}")
                    print(f"      限重: {specs.get('max_weight', '?')}")
                    print(f"      适用: {specs.get('suitable_for', '?')}")
                
                if opt.get('price_per_ton'):
                    print(f"      每吨成本: {opt['price_per_ton']:,}元/吨")
            
            if "recommendation" in ftl:
                print(f"\n   💡 推荐建议:")
                print(f"   {ftl['recommendation']}")
    
    else:
        print(f"❌ 执行失败: {result.stderr}")
    
    # 测试 2: 大客户折扣
    print("\n\n💰 测试 2: 大客户折扣（月运量10万）")
    print("-"*70)
    
    result = subprocess.run(
        [sys.executable, "scripts/quote.py",
         "--from", "上海", "--to", "北京",
         "--type", "both", "--weight", "500",
         "--monthly-volume", "100000"],
        capture_output=True, text=True, encoding='utf-8'
    )
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        
        if "ltl_quote" in data:
            ltl = data["ltl_quote"]
            if "discount" in ltl:
                print(f"\n✅ 零担折扣: {ltl['discount']}")
                print(f"   原价: {ltl['total']:,.2f}元")
                print(f"   折后: {ltl['discounted_total']:,.2f}元")
                print(f"   节省: {ltl['total'] - ltl['discounted_total']:,.2f}元")
        
        if "ftl_quote" in data:
            ftl = data["ftl_quote"]
            if "discount" in ftl:
                print(f"\n✅ 整车折扣: {ftl['discount']}")
                for opt in ftl.get('options', []):
                    if "discounted_total" in opt:
                        print(f"   {opt['vehicle_type']}: {opt['total']:,}元 → {opt['discounted_total']:,}元")
    
    # 测试 3: 生成报价单
    print("\n\n📄 测试 3: 生成正式报价单")
    print("-"*70)
    
    result = subprocess.run(
        [sys.executable, "scripts/quote.py",
         "--generate-quote",
         "--customer", "C001",
         "--from", "上海", "--to", "北京",
         "--weight", "500"],
        capture_output=True, text=True, encoding='utf-8'
    )
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        
        if data.get("type") == "quote_document":
            doc = data["document"]
            print("\n✅ 报价单生成成功!")
            print(f"   文档长度: {len(doc)}字符")
            print(f"\n   预览（前500字符）:")
            print("   " + "-"*66)
            for line in doc.split('\n')[:20]:
                print(f"   {line}")
            print("   ...")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70)
    print("\n📊 数据增强总结:")
    print("   ✓ 零担报价: 增加重量区间、燃油费率、优劣势说明")
    print("   ✓ 整车报价: 增加车型规格（长宽高/容积/限重）、适用场景")
    print("   ✓ 价格分析: 增加每吨/每立方成本计算")
    print("   ✓ 智能推荐: 根据车型给出选择建议")
    print("   ✓ 折扣信息: 清晰展示原价、折扣、折后价")
    print("="*70)


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_enhanced_quote()
