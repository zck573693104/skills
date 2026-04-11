#!/usr/bin/env python3
"""
运单追踪模拟工具
用法：python track.py --waybill SF2026040812345
"""

import argparse
import json
import random
from datetime import datetime, timedelta

# 模拟运单数据库
MOCK_WAYBILLS = {
    "SF2026040101234": {
        "status": "已签收",
        "origin": "上海",
        "destination": "北京",
        "shipper": "蓝鲸电商",
        "receiver": "张先生",
        "weight": "35kg",
        "create_time": "2026-04-01 09:30:00",
        "events": [
            {"time": "2026-04-01 09:30", "location": "上海浦东网点", "event": "揽收完成"},
            {"time": "2026-04-01 14:20", "location": "上海转运中心", "event": "到达分拣中心，正在分拣"},
            {"time": "2026-04-01 20:45", "location": "上海转运中心", "event": "已装车发运，车牌：沪A12345"},
            {"time": "2026-04-02 06:15", "location": "河北保定中转站", "event": "途中中转"},
            {"time": "2026-04-02 11:30", "location": "北京转运中心", "event": "到达目的地转运中心"},
            {"time": "2026-04-02 15:00", "location": "北京朝阳派送站", "event": "派件员李师傅（138xxxx5678）正在派送"},
            {"time": "2026-04-02 17:23", "location": "北京朝阳区", "event": "已签收，签收人：张先生"},
        ]
    },
    "SF2026040512345": {
        "status": "派送中",
        "origin": "上海",
        "destination": "广州",
        "shipper": "鑫达制造",
        "receiver": "广州客户",
        "weight": "280kg",
        "create_time": "2026-04-05 10:15:00",
        "events": [
            {"time": "2026-04-05 10:15", "location": "苏州工业园区", "event": "上门揽收完成"},
            {"time": "2026-04-05 16:00", "location": "上海转运中心", "event": "到达分拣中心"},
            {"time": "2026-04-05 23:30", "location": "上海转运中心", "event": "已发运，预计明日到达"},
            {"time": "2026-04-06 08:45", "location": "杭州中转站", "event": "中转扫描"},
            {"time": "2026-04-06 18:20", "location": "广州白云转运中心", "event": "到达目的地转运中心"},
            {"time": "2026-04-07 09:00", "location": "广州天河派送站", "event": "已安排派件，预计今日上午送达"},
        ]
    },
    "SF2026040712345": {
        "status": "运输中",
        "origin": "深圳",
        "destination": "北京",
        "shipper": "顺和贸易",
        "receiver": "北京收货方",
        "weight": "1200kg",
        "create_time": "2026-04-07 08:00:00",
        "events": [
            {"time": "2026-04-07 08:00", "location": "深圳南山", "event": "揽收完成，整车发运"},
            {"time": "2026-04-07 12:30", "location": "广深高速", "event": "在途中，预计明日下午到达"},
            {"time": "2026-04-07 22:00", "location": "湖南长沙中转站", "event": "中途停靠补给"},
            {"time": "2026-04-08 06:00", "location": "河南郑州", "event": "在途中，继续北上"},
        ]
    },
    "SF2026033012345": {
        "status": "异常",
        "origin": "上海",
        "destination": "成都",
        "shipper": "美好家居",
        "receiver": "成都门店",
        "weight": "560kg",
        "create_time": "2026-03-30 14:00:00",
        "events": [
            {"time": "2026-03-30 14:00", "location": "上海闵行", "event": "揽收完成"},
            {"time": "2026-03-30 20:00", "location": "上海转运中心", "event": "发运"},
            {"time": "2026-03-31 08:00", "location": "安徽合肥", "event": "中转"},
            {"time": "2026-03-31 15:00", "location": "湖北武汉", "event": "⚠️ 异常：因G42高速大雪封路，货物暂存武汉中转站，等待道路恢复"},
            {"time": "2026-04-01 09:00", "location": "湖北武汉", "event": "⚠️ 道路仍未开放，继续等待，预计今日下午恢复"},
            {"time": "2026-04-01 16:00", "location": "湖北武汉", "event": "道路恢复，已发运"},
            {"time": "2026-04-02 14:00", "location": "四川成都转运中心", "event": "到达目的地"},
            {"time": "2026-04-02 16:30", "location": "成都锦江区", "event": "已签收（延误原因：天气因素，不在理赔范围内）"},
        ]
    },
}


def track_waybill(waybill_no):
    """查询运单状态"""
    if waybill_no in MOCK_WAYBILLS:
        data = MOCK_WAYBILLS[waybill_no].copy()
        latest = data["events"][-1]
        data["latest_update"] = latest
        return data

    # 模拟未知单号
    # 生成随机在途状态（演示用）
    now = datetime.now()
    return {
        "waybill_no": waybill_no,
        "status": "运输中",
        "note": "（演示模拟数据）",
        "events": [
            {"time": (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"), "location": "发货城市网点", "event": "揽收完成"},
            {"time": (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"), "location": "发货城市转运中心", "event": "已装车发运"},
            {"time": now.strftime("%Y-%m-%d %H:%M"), "location": "在途中", "event": f"货物正在运输中，预计{(now + timedelta(days=1)).strftime('%m月%d日')}到达"},
        ],
        "latest_update": {"time": now.strftime("%Y-%m-%d %H:%M"), "location": "在途", "event": "运输中"}
    }


def main():
    parser = argparse.ArgumentParser(description="运单追踪工具")
    parser.add_argument("--waybill", required=True, help="运单号")
    args = parser.parse_args()

    result = track_waybill(args.waybill)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
