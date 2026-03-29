import os
import requests
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent

# ─────────────────────────────────────────────
# 1. 百度搜索工具函数
# ─────────────────────────────────────────────

def baidu_search_api(query: str, count: int = 10, freshness: str = None) -> list:
    """
    调用百度搜索 API

    Args:
        query: 搜索关键词
        count: 返回结果数量 (1-50)
        freshness: 时间范围 (pd=1 天，pw=1 周，pm=1 月，py=1 年，或自定义日期范围)

    Returns:
        搜索结果列表
    """
    url = "https://qianfan.baidubce.com/v2/ai_search/web_search"

    # 从环境变量获取 API Key
    api_key = os.getenv("BAIDU_API_KEY")
    if not api_key:
        raise ValueError("BAIDU_API_KEY 环境变量未设置")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Appbuilder-From": "openclaw",
        "Content-Type": "application/json"
    }

    # 构建时间过滤条件
    search_filter = {}
    if freshness:
        current_time = datetime.now()
        end_date = (current_time + timedelta(days=1)).strftime("%Y-%m-%d")

        if freshness in ["pd", "pw", "pm", "py"]:
            if freshness == "pd":
                start_date = (current_time - timedelta(days=1)).strftime("%Y-%m-%d")
            elif freshness == "pw":
                start_date = (current_time - timedelta(days=6)).strftime("%Y-%m-%d")
            elif freshness == "pm":
                start_date = (current_time - timedelta(days=30)).strftime("%Y-%m-%d")
            elif freshness == "py":
                start_date = (current_time - timedelta(days=364)).strftime("%Y-%m-%d")

            search_filter = {
                "range": {
                    "page_time": {"gte": start_date, "lt": end_date}
                }
            }
        elif "to" in freshness:
            # 自定义日期范围：2024-01-01to2024-12-31
            try:
                start_date, end_date = freshness.split("to")
                search_filter = {
                    "range": {
                        "page_time": {"gte": start_date, "lt": end_date}
                    }
                }
            except:
                pass

    # 限制 count 范围
    count = max(1, min(count, 50))

    request_body = {
        "messages": [
            {
                "content": query,
                "role": "user"
            }
        ],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": count}],
        "search_filter": search_filter
    }

    response = requests.post(url, json=request_body, headers=headers)
    response.raise_for_status()
    results = response.json()

    if "code" in results:
        raise Exception(f"百度搜索 API 错误：{results.get('message', '未知错误')}")

    # 提取并格式化结果
    datas = results.get("references", [])

    # 移除 snippet 字段，保留关键信息
    formatted_results = []
    for item in datas:
        formatted_item = {k: v for k, v in item.items() if k != "snippet"}
        formatted_results.append(formatted_item)

    return formatted_results


# ─────────────────────────────────────────────
# 2. 定义 LangChain 工具
# ─────────────────────────────────────────────

@tool
def baidu_search(query: str) -> str:
    """
    百度搜索工具。用于查询实时信息、新闻、事实、最新事件等。
    适用于需要获取中文互联网信息的场景。

    参数：query - 搜索关键词
    返回：格式化的搜索结果摘要
    """
    print(f"🔍 百度搜索：{query}")

    try:
        results = baidu_search_api(query, count=10)

        if not results:
            return "未找到相关信息"

        # 格式化输出前 5 条结果
        output = []
        for i, item in enumerate(results[:5], 1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            summary = item.get("summary", "")

            output.append(f"{i}. [{title}]({url})\n   {summary}")

        return "\n\n".join(output)

    except Exception as e:
        return f"搜索失败：{str(e)}"


@tool
def calculate(expression: str) -> str:
    """
    数学计算工具。用于执行加减乘除、复杂表达式计算。
    输入应为数学表达式，如 '(123 + 456) * 789'
    """
    print(f"🧮 计算：{expression}")

    try:
        # 安全的表达式求值
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"计算错误：{e}"


@tool
def get_current_time(_: str = "") -> str:
    """
    获取当前时间工具。当用户询问时间或日期时使用。
    返回格式：YYYY-MM-DD HH:MM:SS
    """
    from datetime import datetime
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────
# 3. 配置模型（⭐ 已替换为 OpenRouter Free）
# ─────────────────────────────────────────────

# 方案 A：使用标准 ChatOpenAI（推荐）
llm = ChatOpenAI(
    model="MiniMax-M2.5",
    api_key="sk-NDY0LTIxMjcwOTMzNzQyLTE3NzQ1MzE4NDAxMjg=",
    base_url="https://api.scnet.cn/api/llm/v1",
    temperature=0.7,
    # ⭐ 关键：添加自定义请求头
    # default_headers={
    #     "HTTP-Referer": "openrouter/free",
    #     "X-OpenRouter-Title": "OpenClaw Agent",
    # },
)

# ─────────────────────────────────────────────
# 4. 创建 Agent
# ─────────────────────────────────────────────

tools = [baidu_search, calculate, get_current_time]
agent = create_agent(model=llm, tools=tools)

# ─────────────────────────────────────────────
# 5. 主程序
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 LangChain Agent - OpenRouter Free 模型版")
    print("=" * 60)
    print("\n模型配置:")
    print("  • 提供商：OpenRouter (免费模型)")
    print("  • 模型：openrouter/free")
    print("  • 请求头：已配置 HTTP-Referer + X-OpenRouter-Title")
    print("\n可用工具:")
    print("  🔍 baidu_search - 百度搜索（查询实时信息）")
    print("  🧮 calculate - 数学计算")
    print("  ⏰ get_current_time - 获取当前时间")
    print("\n示例问题:")
    print("  • 今天北京的天气怎么样？")
    print("  • 最新的 AI 技术突破有哪些？")
    print("  • 计算 (123 + 456) * 789")
    print("  • 现在几点了？")
    print("\n输入 'quit' 退出")
    print("=" * 60)

    while True:
        user_input = input("\n👤 你：").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n再见！👋")
            break

        if not user_input:
            continue

        print("\n🤖 Agent 思考中...\n")

        try:
            result = agent.invoke({"messages": [("user", user_input)]})

            # 统计工具调用次数
            tool_calls = [m for m in result["messages"] if hasattr(m, 'tool_calls')]
            print(f"📊 工具调用次数：{len(tool_calls)}")

            # 获取最终答案
            answer = result["messages"][-1].content
            print(f"\n🤖 Agent: {answer}")
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ 执行失败：{error_msg}")
