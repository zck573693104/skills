#!/usr/bin/env python3
"""
物流报价查询工具（增强版）
用法：
  python quote.py --from 上海 --to 北京 --type both --weight 300
  python quote.py --from 上海 --to 北京 --type ftl --monthly-volume 100000
  python quote.py --generate-quote --customer C001 --route 上海-北京 --weight 500
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

# 模拟运价数据库
# 整车车型详细规格
VEHICLE_SPECS = {
    "4.2米厢车": {
        "length": "4.2米",
        "width": "2.1米",
        "height": "2.1米",
        "volume": "18立方米",
        "max_weight": "3吨",
        "suitable_for": "小批量货物、城市配送"
    },
    "9.6米厢车": {
        "length": "9.6米",
        "width": "2.4米",
        "height": "2.6米",
        "volume": "60立方米",
        "max_weight": "10吨",
        "suitable_for": "中等批量货物、跨城运输"
    },
    "17.5米平板": {
        "length": "17.5米",
        "width": "3米",
        "height": "不限",
        "volume": "不适用（平板）",
        "max_weight": "30吨",
        "suitable_for": "大批量货物、重型设备、超长货物"
    }
}

FREIGHT_RATES = {
    "ftl": {
        ("上海", "北京"): {"4.2米厢车": 3800, "9.6米厢车": 6500, "17.5米平板": 9800},
        ("上海", "广州"): {"4.2米厢车": 3200, "9.6米厢车": 5800, "17.5米平板": 8600},
        ("上海", "成都"): {"4.2米厢车": 4200, "9.6米厢车": 7200, "17.5米平板": 10500},
        ("北京", "广州"): {"4.2米厢车": 3500, "9.6米厢车": 6000},
        ("北京", "成都"): {"9.6米厢车": 6800},
        ("广州", "武汉"): {"4.2米厢车": 2800, "9.6米厢车": 5000},
        ("深圳", "北京"): {"9.6米厢车": 6200},
        ("深圳", "成都"): {"9.6米厢车": 7000},
    },
    "ltl": {
        ("上海", "北京"): {"0-100": 15, "100-500": 12, "500-1000": 10, "1000-3000": 8, "days": "3-4"},
        ("上海", "广州"): {"0-100": 12, "100-500": 10, "500-1000": 8.5, "1000-3000": 7, "days": "3-4"},
        ("上海", "成都"): {"0-100": 16, "100-500": 13, "500-1000": 11, "1000-3000": 9, "days": "4-5"},
        ("上海", "武汉"): {"0-100": 10, "100-500": 8, "500-1000": 7, "1000-3000": 6, "days": "2-3"},
        ("北京", "广州"): {"0-100": 14, "100-500": 11, "500-1000": 9, "1000-3000": 7.5, "days": "4-5"},
        ("广州", "上海"): {"0-100": 12, "100-500": 10, "500-1000": 8.5, "1000-3000": 7, "days": "3-4"},
        ("广州", "北京"): {"0-100": 14, "100-500": 11, "500-1000": 9, "1000-3000": 7.5, "days": "4-5"},
        ("成都", "上海"): {"0-100": 16, "100-500": 13, "500-1000": 11, "1000-3000": 9, "days": "4-5"},
    }
}

FTL_TRANSIT_DAYS = {
    ("上海", "北京"): 2, ("上海", "广州"): 2, ("上海", "成都"): 3,
    ("北京", "广州"): 3, ("北京", "成都"): 3, ("广州", "武汉"): 2,
    ("深圳", "北京"): 2, ("深圳", "成都"): 3,
}

SURCHARGES = {
    "fuel": 0.08,       # 燃油附加费 8%
    "oversized": 0.20,  # 超长附加费 20%
    "overweight": 0.15, # 超重附加费 15%
}

VOLUME_DISCOUNTS = [
    (500000, 0.80),
    (200000, 0.85),
    (100000, 0.90),
    (50000, 0.95),
    (0, 1.00),
]


def get_ltl_rate(origin, dest, weight_kg):
    """查询零担运价（增强版：包含详细说明）"""
    key = (origin, dest)
    if key not in FREIGHT_RATES["ltl"]:
        return None

    rates = FREIGHT_RATES["ltl"][key]
    
    # 确定重量区间和单价
    if weight_kg <= 100:
        rate = rates["0-100"]
        weight_range = "0-100kg"
    elif weight_kg <= 500:
        rate = rates["100-500"]
        weight_range = "100-500kg"
    elif weight_kg <= 1000:
        rate = rates["500-1000"]
        weight_range = "500-1000kg"
    elif weight_kg <= 3000:
        rate = rates["1000-3000"]
        weight_range = "1000-3000kg"
    else:
        return {
            "error": "零担最大承运3吨，超出请使用整车",
            "suggestion": f"建议改用整车运输，{weight_kg}kg可选择9.6米厢车（限重10吨）或17.5米平板（限重30吨）"
        }

    base_cost = weight_kg * rate
    fuel_surcharge = base_cost * SURCHARGES["fuel"]
    total = base_cost + fuel_surcharge

    return {
        "type": "零担(LTL)",
        "origin": origin,
        "destination": dest,
        "weight": f"{weight_kg}kg",
        "weight_range": weight_range,
        "unit_rate": f"{rate}元/kg",
        "base_cost": round(base_cost, 2),
        "fuel_surcharge": round(fuel_surcharge, 2),
        "fuel_rate": f"{SURCHARGES['fuel']*100}%",
        "total": round(total, 2),
        "transit_days": rates["days"],
        "note": "以上为标准价，大客户可申请折扣",
        "advantages": [
            "无需包车，按实际重量计费",
            "适合小批量货物（<3吨）",
            "灵活便捷，随时发货",
            "多点装卸，配送范围广"
        ],
        "limitations": [
            "时效较整车慢1-2天",
            "需要中转分拣，有轻微破损风险",
            "超大/超重货物可能加收附加费"
        ]
    }


def get_ftl_rates(origin, dest):
    """查询整车运价（增强版：包含详细车型规格）"""
    key = (origin, dest)
    if key not in FREIGHT_RATES["ftl"]:
        return None

    rates = FREIGHT_RATES["ftl"][key]
    days = FTL_TRANSIT_DAYS.get(key, "3-5")
    results = []

    for vehicle_type, base_price in rates.items():
        fuel_surcharge = round(base_price * SURCHARGES["fuel"], 0)
        total = base_price + fuel_surcharge
        
        # 获取车型详细规格
        specs = VEHICLE_SPECS.get(vehicle_type, {})
        
        results.append({
            "vehicle_type": vehicle_type,
            "base_price": base_price,
            "fuel_surcharge": int(fuel_surcharge),
            "total": int(total),
            "specs": {
                "length": specs.get("length", "未知"),
                "width": specs.get("width", "未知"),
                "height": specs.get("height", "未知"),
                "volume": specs.get("volume", "未知"),
                "max_weight": specs.get("max_weight", "未知"),
                "suitable_for": specs.get("suitable_for", "通用")
            },
            "price_per_cbm": round(total / float(specs.get("volume", "60").replace("立方米", "").replace("不适用（平板）", "60")), 2) if specs.get("volume") and "不适用" not in specs.get("volume", "") else None,
            "price_per_ton": round(total / float(specs.get("max_weight", "10").replace("吨", "")), 2) if specs.get("max_weight") else None
        })

    return {
        "type": "整车(FTL)",
        "origin": origin,
        "destination": dest,
        "transit_days": days,
        "options": results,
        "note": "整车含燃油附加费，大客户折扣另议",
        "recommendation": _get_vehicle_recommendation(results)
    }


def _get_vehicle_recommendation(options):
    """根据车型选项给出推荐建议"""
    if not options:
        return "无可用车型"
    
    recommendations = []
    for opt in options:
        vehicle = opt["vehicle_type"]
        if "4.2米" in vehicle:
            recommendations.append(f"• {vehicle}：适合小批量货物（≤3吨），灵活便捷，城市配送首选")
        elif "9.6米" in vehicle:
            recommendations.append(f"• {vehicle}：适合中等批量货物（3-10吨），性价比高，跨城运输常用")
        elif "17.5米" in vehicle:
            recommendations.append(f"• {vehicle}：适合大批量货物（10-30吨）或超长货物，单位成本最低")
    
    return "\n".join(recommendations)


def calc_discount(monthly_volume):
    """计算大客户折扣"""
    for threshold, discount in VOLUME_DISCOUNTS:
        if monthly_volume >= threshold:
            return discount
    return 1.0


def generate_quote_document(customer_id, origin, dest, weight, quote_data):
    """生成正式报价单文档"""
    # 加载客户信息
    try:
        from customer import CUSTOMERS
        customer = CUSTOMERS.get(customer_id.upper(), {})
    except:
        customer = {}
    
    customer_name = customer.get("name", "未知客户")
    contact = customer.get("contact", "")
    phone = customer.get("phone", "")
    
    now = datetime.now()
    # 根据季节确定有效期
    current_month = now.month
    if current_month in [1, 6, 7, 11]:  # 旺季
        valid_days = 3
    else:
        valid_days = 7
    
    valid_until = (now + timedelta(days=valid_days)).strftime("%Y年%m月%d日")
    
    quote_doc = f"""
═══════════════════════════════════════
         物流运价报价单
═══════════════════════════════════════

报价单号：QT{now.strftime('%Y%m%d%H%M%S')}
日期：{now.strftime('%Y年%m月%d日')}
有效期至：{valid_until}

───────────────────────────────────────
客户信息
───────────────────────────────────────
客户名称：{customer_name}
联系人：{contact}
联系电话：{phone}

───────────────────────────────────────
运输方案
───────────────────────────────────────
起运地：{origin}
目的地：{dest}
货物重量：{weight}kg
"""
    
    # 添加零担报价
    if "ltl_quote" in quote_data and "error" not in quote_data["ltl_quote"]:
        ltl = quote_data["ltl_quote"]
        quote_doc += f"""
【零担方案 LTL】
  单价：{ltl['unit_rate']}
  基础运费：{ltl['base_cost']:,.2f}元
  燃油附加费：{ltl['fuel_surcharge']:,.2f}元（8%）
"""
        if "discount" in ltl:
            quote_doc += f"  折扣：{ltl['discount']}\n"
            quote_doc += f"  折后总价：{ltl['discounted_total']:,.2f}元\n"
        else:
            quote_doc += f"  ✅ 合计：{ltl['total']:,.2f}元\n"
        
        quote_doc += f"  ⏱ 时效：{ltl['transit_days']}天\n"
    
    # 添加整车报价
    if "ftl_quote" in quote_data and "error" not in quote_data["ftl_quote"]:
        ftl = quote_data["ftl_quote"]
        quote_doc += f"\n【整车方案 FTL】\n"
        for opt in ftl["options"]:
            quote_doc += f"  • {opt['vehicle_type']}：{opt['total']:,}元（含燃油）\n"
        quote_doc += f"  ⏱ 时效：{ftl['transit_days']}天\n"
    
    quote_doc += f"""
───────────────────────────────────────
服务承诺
───────────────────────────────────────
✓ 准时送达率 ≥ 98%
✓ 货物破损率 < 0.1%
✓ 24小时客服支持
✓ 实时轨迹追踪

保价服务：货值×0.3%，最低50元
理赔规则：
  - 未保价：按运费3倍赔偿
  - 已保价：按货值80%赔偿
  - 签收72小时后不受理

───────────────────────────────────────
联系方式
───────────────────────────────────────
销售经理：张经理
电话：400-888-9999
邮箱：sales@logistics.com
地址：上海市浦东新区物流园区A栋

═══════════════════════════════════════
       感谢您的信任，期待合作！
═══════════════════════════════════════
"""
    
    return quote_doc


def main():
    parser = argparse.ArgumentParser(description="物流报价查询工具")
    parser.add_argument("--from", dest="origin", help="出发城市")
    parser.add_argument("--to", dest="dest", help="目的城市")
    parser.add_argument("--type", choices=["ltl", "ftl", "both"], default="both", help="运输类型")
    parser.add_argument("--weight", type=float, default=0, help="货物重量(kg)，零担必填")
    parser.add_argument("--monthly-volume", type=float, default=0, help="月均运费(元)，用于计算折扣")
    parser.add_argument("--generate-quote", action="store_true", help="生成正式报价单文档")
    parser.add_argument("--customer", help="客户ID（生成报价单时使用）")

    args = parser.parse_args()
    
    # 如果是生成报价单模式
    if args.generate_quote:
        if not all([args.customer, args.origin, args.dest, args.weight]):
            print(json.dumps({"error": "生成报价单需要: --customer, --from, --to, --weight"}, ensure_ascii=False))
            return
        
        # 先获取报价数据
        result = {"query": {"origin": args.origin, "dest": args.dest}}
        
        if args.weight > 0:
            ltl = get_ltl_rate(args.origin, args.dest, args.weight)
            if ltl:
                if args.monthly_volume > 0:
                    discount = calc_discount(args.monthly_volume)
                    if discount < 1.0:
                        ltl["discount"] = f"{int(discount*10)}折"
                        ltl["discounted_total"] = round(ltl["total"] * discount, 2)
                result["ltl_quote"] = ltl
        
        ftl = get_ftl_rates(args.origin, args.dest)
        if ftl:
            if args.monthly_volume > 0:
                discount = calc_discount(args.monthly_volume)
                if discount < 1.0:
                    ftl["discount"] = f"{int(discount*10)}折"
                    for opt in ftl["options"]:
                        opt["discounted_total"] = int(opt["total"] * discount)
            result["ftl_quote"] = ftl
        
        # 生成报价单文档
        quote_doc = generate_quote_document(args.customer, args.origin, args.dest, args.weight, result)
        print(json.dumps({
            "type": "quote_document",
            "document": quote_doc,
            "data": result
        }, ensure_ascii=False))
        return
    
    # 普通查询模式
    if not args.origin or not args.dest:
        parser.print_help()
        return
    
    result = {"query": {"origin": args.origin, "dest": args.dest}}

    if args.type in ("ltl", "both") and args.weight > 0:
        ltl = get_ltl_rate(args.origin, args.dest, args.weight)
        if ltl:
            if args.monthly_volume > 0:
                discount = calc_discount(args.monthly_volume)
                if discount < 1.0:
                    ltl["discount"] = f"{int(discount*10)}折"
                    ltl["discounted_total"] = round(ltl["total"] * discount, 2)
            result["ltl_quote"] = ltl
        else:
            result["ltl_quote"] = {"error": f"暂无 {args.origin}→{args.dest} 零担线路，请联系商务"}

    if args.type in ("ftl", "both"):
        ftl = get_ftl_rates(args.origin, args.dest)
        if ftl:
            if args.monthly_volume > 0:
                discount = calc_discount(args.monthly_volume)
                if discount < 1.0:
                    ftl["discount"] = f"{int(discount*10)}折"
                    for opt in ftl["options"]:
                        opt["discounted_total"] = int(opt["total"] * discount)
            result["ftl_quote"] = ftl
        else:
            result["ftl_quote"] = {"error": f"暂无 {args.origin}→{args.dest} 整车线路，请联系商务"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
