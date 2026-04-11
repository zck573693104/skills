import argparse
import json
import os
from urllib.parse import quote
from urllib.request import urlopen

# 高德 API Key（建议后续通过配置管理）
API_KEY = os.getenv('GAO_DE_API_KEY')


def fetch_json(url: str) -> dict:
    """通用函数：从 URL 获取 JSON 数据"""
    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"请求失败: {e}")
        return {}


def get_coordinates(city: str) -> dict:
    """根据城市名获取坐标和 adcode"""
    encoded_city = quote(city)
    url = f"https://restapi.amap.com/v3/geocode/geo?address={encoded_city}&output=json&key={API_KEY}"
    data = fetch_json(url)
    if data.get("geocodes"):
        loc = data["geocodes"][0]
        return {
            "adcode": loc["adcode"],
            "name": loc["formatted_address"]
        }
    print(f"❌ 未找到城市: {city}")
    return {}


def get_weather(city: str):
    """获取指定城市的实时天气"""
    geo_data = get_coordinates(city)
    if not geo_data:
        return

    adcode = geo_data["adcode"]
    url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={adcode}&key={API_KEY}&extensions=base"
    data = fetch_json(url)

    live = data.get("lives", [{}])[0]
    if not live:
        print("❌ 未获取到天气数据")
        return

    print(f"📍 城市: {live.get('city', city)}")
    print(f"🌤️  天气: {live.get('weather', '未知')}")
    print(f"🌡️  温度: {live.get('temperature', 'N/A')}°C")
    print(f"💧 湿度: {live.get('humidity', 'N/A')}%")
    print(f"💨 风速: {live.get('windpower', 'N/A')} 级")
    print(f"🧭 风向: {live.get('winddirection', '未知')}")
    print(f"🕐 更新时间: {live.get('reporttime', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="获取当前天气（使用高德API）")
    parser.add_argument("location", nargs="?", default="广州", help="城市名称，默认为广州")
    args = parser.parse_args()
    get_weather(args.location)


if __name__ == "__main__":
    main()