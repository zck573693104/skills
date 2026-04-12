# 报价脚本数据增强说明

## 📋 优化背景

**问题**：之前脚本返回的 JSON 数据不够详细，导致 DeepAgent 在输出时被截断，无法获取完整的车型选项信息（如4.2米、9.6米等具体价格和规格）。

**解决方案**：增强 `quote.py` 脚本，返回更丰富、更结构化的数据。

---

## ✨ 优化内容

### 1. **整车报价增强** (`get_ftl_rates`)

#### 新增字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `specs` | Object | 车型详细规格 | 见下方 |
| `price_per_cbm` | Float | 每立方成本（元/m³） | 68.4 |
| `price_per_ton` | Float | 每吨成本（元/吨） | 410.4 |
| `recommendation` | String | 智能推荐建议 | 多行文本 |

#### specs 对象结构

```json
{
  "length": "4.2米",
  "width": "2.1米",
  "height": "2.1米",
  "volume": "18立方米",
  "max_weight": "3吨",
  "suitable_for": "小批量货物、城市配送"
}
```

#### 完整示例

```json
{
  "ftl_quote": {
    "type": "整车(FTL)",
    "origin": "上海",
    "destination": "北京",
    "transit_days": 2,
    "options": [
      {
        "vehicle_type": "4.2米厢车",
        "base_price": 3800,
        "fuel_surcharge": 304,
        "total": 4104,
        "specs": {
          "length": "4.2米",
          "width": "2.1米",
          "height": "2.1米",
          "volume": "18立方米",
          "max_weight": "3吨",
          "suitable_for": "小批量货物、城市配送"
        },
        "price_per_cbm": 228.0,
        "price_per_ton": 1368.0
      },
      {
        "vehicle_type": "9.6米厢车",
        "base_price": 6500,
        "fuel_surcharge": 520,
        "total": 7020,
        "specs": {
          "length": "9.6米",
          "width": "2.4米",
          "height": "2.6米",
          "volume": "60立方米",
          "max_weight": "10吨",
          "suitable_for": "中等批量货物、跨城运输"
        },
        "price_per_cbm": 117.0,
        "price_per_ton": 702.0
      }
    ],
    "note": "整车含燃油附加费，大客户折扣另议",
    "recommendation": "• 4.2米厢车：适合小批量货物（≤3吨），灵活便捷，城市配送首选\n• 9.6米厢车：适合中等批量货物（3-10吨），性价比高，跨城运输常用"
  }
}
```

---

### 2. **零担报价增强** (`get_ltl_rate`)

#### 新增字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `weight_range` | String | 重量区间 | "100-500kg" |
| `fuel_rate` | String | 燃油费率 | "8%" |
| `advantages` | Array | 优势列表 | 4条 |
| `limitations` | Array | 限制列表 | 3条 |
| `suggestion` | String | 错误时的建议 | 超限提示 |

#### 完整示例

```json
{
  "ltl_quote": {
    "type": "零担(LTL)",
    "origin": "上海",
    "destination": "北京",
    "weight": "300kg",
    "weight_range": "100-500kg",
    "unit_rate": "12元/kg",
    "base_cost": 3600.0,
    "fuel_surcharge": 288.0,
    "fuel_rate": "8%",
    "total": 3888.0,
    "transit_days": "3-4",
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
}
```

#### 超限错误示例

```json
{
  "error": "零担最大承运3吨，超出请使用整车",
  "suggestion": "建议改用整车运输，5000kg可选择9.6米厢车（限重10吨）或17.5米平板（限重30吨）"
}
```

---

## 🎯 使用效果对比

### 优化前

```json
{
  "ftl_quote": {
    "type": "整车(FTL)",
    "options": [
      {"vehicle_type": "4.2米厢车", "total": 4104},
      {"vehicle_type": "9.6米厢车", "total": 7020}
    ]
  }
}
```

**问题**：
- ❌ 缺少车型规格（长宽高、容积、限重）
- ❌ 缺少适用场景说明
- ❌ 缺少价格分析（每吨/每立方成本）
- ❌ 缺少推荐建议

---

### 优化后

```json
{
  "ftl_quote": {
    "type": "整车(FTL)",
    "origin": "上海",
    "destination": "北京",
    "transit_days": 2,
    "options": [
      {
        "vehicle_type": "4.2米厢车",
        "base_price": 3800,
        "fuel_surcharge": 304,
        "total": 4104,
        "specs": {
          "length": "4.2米",
          "width": "2.1米",
          "height": "2.1米",
          "volume": "18立方米",
          "max_weight": "3吨",
          "suitable_for": "小批量货物、城市配送"
        },
        "price_per_cbm": 228.0,
        "price_per_ton": 1368.0
      }
    ],
    "recommendation": "• 4.2米厢车：适合小批量货物（≤3吨），灵活便捷..."
  }
}
```

**改进**：
- ✅ 完整的车型规格（长×宽×高、容积、限重）
- ✅ 明确的适用场景
- ✅ 价格分析（每立方/每吨成本）
- ✅ 智能推荐建议

---

## 💡 DeepAgent 输出示例

### 优化前的输出（被截断）

```
📦 上海→北京 报价单
─────────────────────
【整车方案】
由于系统输出截断，未能获取完整的车型选项（如4.2米、9.6米等具体价格）。
建议直接咨询物流公司获取详细整车报价。
```

### 优化后的输出（完整）

```
📦 上海→北京 报价单
─────────────────────
【零担方案 LTL 300kg】
  单价：12元/kg（100-500kg区间）
  基础运费：3,600元
  燃油附加费：288元（8%）
  ✅ 合计：3,888元
  ⏱ 时效：3-4天
  
  优势：
  • 无需包车，按实际重量计费
  • 适合小批量货物（<3吨）
  • 灵活便捷，随时发货
  
  限制：
  • 时效较整车慢1-2天
  • 需要中转分拣，有轻微破损风险

【整车方案 FTL】
  时效：2天
  
  车型选项：
  
  1️⃣ 4.2米厢车
     尺寸：4.2米×2.1米×2.1米
     容积：18立方米
     限重：3吨
     总价：4,104元（含燃油）
     每吨成本：1,368元/吨
     适用：小批量货物、城市配送
  
  2️⃣ 9.6米厢车
     尺寸：9.6米×2.4米×2.6米
     容积：60立方米
     限重：10吨
     总价：7,020元（含燃油）
     每立方成本：117元/m³
     每吨成本：702元/吨
     适用：中等批量货物、跨城运输
  
  3️⃣ 17.5米平板
     尺寸：17.5米×3米×不限
     限重：30吨
     总价：10,584元（含燃油）
     每吨成本：353元/吨
     适用：大批量货物、重型设备、超长货物
  
  💡 选择建议：
  • 4.2米厢车：适合小批量货物（≤3吨），灵活便捷，城市配送首选
  • 9.6米厢车：适合中等批量货物（3-10吨），性价比高，跨城运输常用
  • 17.5米平板：适合大批量货物（10-30吨）或超长货物，单位成本最低

─────────────────────
💡 月运费超10万可享9折优惠，欢迎询问框架合同
```

---

## 🔧 技术实现

### 1. 车型规格数据库

```python
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
```

### 2. 智能推荐算法

```python
def _get_vehicle_recommendation(options):
    """根据车型选项给出推荐建议"""
    recommendations = []
    for opt in options:
        vehicle = opt["vehicle_type"]
        if "4.2米" in vehicle:
            recommendations.append(
                f"• {vehicle}：适合小批量货物（≤3吨），灵活便捷，城市配送首选"
            )
        elif "9.6米" in vehicle:
            recommendations.append(
                f"• {vehicle}：适合中等批量货物（3-10吨），性价比高，跨城运输常用"
            )
        elif "17.5米" in vehicle:
            recommendations.append(
                f"• {vehicle}：适合大批量货物（10-30吨）或超长货物，单位成本最低"
            )
    return "\n".join(recommendations)
```

### 3. 价格分析计算

```python
# 每立方成本
price_per_cbm = round(
    total / float(specs.get("volume", "60").replace("立方米", "")), 
    2
)

# 每吨成本
price_per_ton = round(
    total / float(specs.get("max_weight", "10").replace("吨", "")), 
    2
)
```

---

## 📊 数据量对比

| 指标 | 优化前 | 优化后 | 增长 |
|------|--------|--------|------|
| 整车报价字段数 | 4 | 12 | **+200%** |
| 零担报价字段数 | 8 | 14 | **+75%** |
| JSON 大小（单车型） | ~100B | ~500B | **+400%** |
| 信息密度 | 低 | 高 | **显著提升** |

---

## ✅ 测试方法

### 1. 运行测试脚本

```bash
cd skills/logistics-sales-agent
python test_enhanced_quote.py
```

### 2. 手动测试

```bash
# 基础查询
python scripts/quote.py --from 上海 --to 北京 --weight 300

# 查看完整 JSON 输出
python scripts/quote.py --from 上海 --to 北京 --weight 300 | python -m json.tool
```

### 3. DeepAgent 集成测试

```python
from deep_agent import DeepAgent

agent = DeepAgent("./skills")
response = agent.chat("帮我查一下从上海到北京的运价，300kg")
print(response)
```

---

## 🎓 最佳实践

### 1. 数据完整性检查

DeepAgent 在处理报价数据时，应该：

```python
# 检查是否有完整的车型信息
if "ftl_quote" in data and "options" in data["ftl_quote"]:
    for opt in data["ftl_quote"]["options"]:
        # 确保有规格信息
        assert "specs" in opt, "缺少车型规格"
        assert "suitable_for" in opt["specs"], "缺少适用场景"
```

### 2. 友好展示

向用户展示时，应该：

- ✅ 格式化数字（千分位分隔符）
- ✅ 突出关键信息（价格、时效）
- ✅ 提供选择建议
- ✅ 说明优劣势

### 3. 错误处理

当数据不完整时：

```python
if "error" in data:
    # 显示错误信息
    print(f"❌ {data['error']}")
    
    # 如果有建议，也显示
    if "suggestion" in data:
        print(f"💡 {data['suggestion']}")
```

---

## 🚀 未来优化方向

1. **实时运价接口**：对接真实物流系统，获取实时价格
2. **历史价格趋势**：展示近30天价格变化曲线
3. **竞品对比**：自动对比其他物流公司价格
4. **最优方案推荐**：基于货物特性自动推荐最佳运输方式
5. **多语言支持**：支持英文、日文等多语言输出

---

**最后更新**：2026-04-11  
**版本**：v2.1  
**维护者**：物流销售部 & 技术部
