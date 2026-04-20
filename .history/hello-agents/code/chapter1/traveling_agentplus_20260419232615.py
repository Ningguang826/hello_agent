AGENT_SYSTEM_PROMPT = """
你是一个智能旅行助手。你的任务是分析用户请求，并结合“用户记忆”和“会话状态”一步步解决问题。

# 你的核心目标
1. 根据用户需求推荐合适的旅行/游玩方案
2. 记住用户偏好（如预算、喜欢/不喜欢的景点类型）
3. 如果推荐景点门票售罄，自动推荐备选方案
4. 如果用户连续拒绝了3个推荐，必须先反思被拒绝的共同原因，再调整推荐策略
5. 与用户持续交互，而不是一次性结束整个程序

# 可用工具
- get_weather(city: str): 查询城市天气
- get_attraction(city: str, weather: str, preference: str="", budget: str="", exclude: str=""): 推荐候选景点
- check_ticket_status(attraction: str, city: str="", date: str=""): 查询门票是否售罄
- get_alternative_attractions(city: str, weather: str, preference: str="", budget: str="", exclude: str=""): 获取备选景点

# 输出格式要求
你的每次回复必须严格遵循以下格式，只能包含一对 Thought 和 Action：

Thought: [你的思考过程和下一步计划]
Action: [一个JSON对象]

# Action JSON 只能是以下几种之一：

1. 调用工具
{"type":"tool","name":"工具名","args":{"参数名":"参数值"}}

2. 询问用户
{"type":"ask_user","question":"你要问用户的话"}

3. 回复用户并等待反馈
{"type":"reply","content":"你要回复用户的话"}

4. 反思策略
{"type":"reflect","content":"你的反思内容"}

5. 结束当前任务
{"type":"finish","content":"最终答案"}

# 重要约束
- 每次只输出一对 Thought-Action
- Action 必须是合法 JSON
- 不要输出 Markdown 代码块
- 如果信息不足，优先 ask_user
- 如果已经有了推荐但需要等用户反馈，优先 reply，不要直接 finish
- 如果门票售罄，必须自动改推备选方案
- 如果用户连续拒绝次数 >= 3，下一步必须先 reflect，再继续推荐
- 推荐时必须参考用户记忆和会话状态
- 不要重复推荐已被用户明确拒绝的方向
"""

import os
import re
import json
import requests
from tavily import TavilyClient
from openai import OpenAI
from collections import deque


# =========================
# 1. 工具函数
# =========================

def get_weather(city: str) -> str:
    """
    通过 wttr.in API 查询天气。
    """
    url = f"https://wttr.in/{city}?format=j1"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        current_condition = data["current_condition"][0]
        weather_desc = current_condition["weatherDesc"][0]["value"]
        temp_c = current_condition["temp_C"]

        return f"{city}当前天气：{weather_desc}，气温{temp_c}摄氏度"
    except requests.exceptions.RequestException as e:
        return f"错误：查询天气时遇到网络问题 - {e}"
    except (KeyError, IndexError) as e:
        return f"错误：解析天气数据失败，可能是城市名称无效 - {e}"


def _get_tavily_client():
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key or api_key == "YOUR_TAVILY_API_KEY":
        return None
    return TavilyClient(api_key=api_key)


def _format_tavily_results(response: dict) -> str:
    if response.get("answer"):
        return response["answer"]

    formatted_results = []
    for result in response.get("results", []):
        title = result.get("title", "无标题")
        content = result.get("content", "")
        formatted_results.append(f"- {title}: {content}")

    if not formatted_results:
        return "抱歉，没有找到相关信息。"

    return "搜索结果如下：\n" + "\n".join(formatted_results)


def get_attraction(city: str, weather: str, preference: str = "", budget: str = "", exclude: str = "") -> str:
    """
    使用 Tavily 搜索符合条件的景点推荐。
    """
    tavily = _get_tavily_client()
    if not tavily:
        return "错误：未配置有效的 TAVILY_API_KEY。"

    query_parts = [
        f"{city}",
        f"{weather}天气下适合游玩的旅游景点推荐",
        "请给出具体景点名、门票大致价格、推荐理由"
    ]
    if preference:
        query_parts.append(f"用户偏好：{preference}")
    if budget:
        query_parts.append(f"预算限制：{budget}")
    if exclude:
        query_parts.append(f"不要推荐这些方向或景点：{exclude}")

    query = "，".join(query_parts)

    try:
        response = tavily.search(
            query=query,
            search_depth="basic",
            include_answer=True,
            max_results=5
        )
        return _format_tavily_results(response)
    except Exception as e:
        return f"错误：执行景点搜索时出现问题 - {e}"


def get_alternative_attractions(city: str, weather: str, preference: str = "", budget: str = "", exclude: str = "") -> str:
    """
    获取备选景点。
    """
    tavily = _get_tavily_client()
    if not tavily:
        return "错误：未配置有效的 TAVILY_API_KEY。"

    query_parts = [
        f"{city}",
        f"{weather}天气下的备选旅游景点",
        "请推荐2到3个备选方案，避免重复主推荐",
        "请给出景点名、门票价格、适合原因"
    ]
    if preference:
        query_parts.append(f"用户偏好：{preference}")
    if budget:
        query_parts.append(f"预算限制：{budget}")
    if exclude:
        query_parts.append(f"排除：{exclude}")

    query = "，".join(query_parts)

    try:
        response = tavily.search(
            query=query,
            search_depth="basic",
            include_answer=True,
            max_results=5
        )
        return _format_tavily_results(response)
    except Exception as e:
        return f"错误：查询备选景点时出现问题 - {e}"


def check_ticket_status(attraction: str, city: str = "", date: str = "") -> str:
    """
    通过搜索近似判断门票是否售罄。
    后续可替换为真实票务 API。
    """
    tavily = _get_tavily_client()
    if not tavily:
        return "错误：未配置有效的 TAVILY_API_KEY。"

    query = f"{city} {attraction} {date} 门票 是否售罄 是否可预约 余票情况".strip()

    try:
        response = tavily.search(
            query=query,
            search_depth="basic",
            include_answer=True,
            max_results=5
        )

        text = ""
        if response.get("answer"):
            text += response["answer"] + "\n"
        for r in response.get("results", []):
            text += (r.get("title", "") + " " + r.get("content", "") + "\n")

        sold_out_keywords = ["售罄", "约满", "无票", "已满", "不可预约", "门票已售完"]
        available_keywords = ["有票", "可预约", "可购买", "余票", "可订", "在售"]

        if any(k in text for k in sold_out_keywords):
            return f"{attraction}门票状态：sold_out。检索依据：{text[:300]}"
        elif any(k in text for k in available_keywords):
            return f"{attraction}门票状态：available。检索依据：{text[:300]}"
        else:
            return f"{attraction}门票状态：unknown。未能明确判断是否售罄。检索依据：{text[:300]}"
    except Exception as e:
        return f"错误：查询门票状态时出现问题 - {e}"


available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
    "check_ticket_status": check_ticket_status,
    "get_alternative_attractions": get_alternative_attractions,
}


# =========================
# 2. OpenAI 兼容客户端
# =========================

class OpenAICompatibleClient:
    """
    一个用于调用兼容 OpenAI 接口的 LLM 服务客户端。
    """
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        print("正在调用大语言模型...")
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            answer = response.choices[0].message.content
            print("大语言模型响应成功。")
            return answer
        except Exception as e:
            print(f"调用 LLM API 时发生错误: {e}")
            return (
                'Thought: 我无法正常调用语言模型。\n'
                'Action: {"type":"reply","content":"抱歉，我暂时无法调用语言模型服务，请检查 API Key、base_url 或账户权限。"}'
            )


# =========================
# 3. 记忆与会话状态
# =========================

def init_memory():
    return {
        "likes": [],
        "dislikes": [],
        "budget_max": None,
        "budget_min": None,
        "notes": []
    }


def init_session_state():
    return {
        "city": None,
        "date": "",
        "weather": None,
        "last_plan": None,
        "last_recommendation_text": None,
        "reject_streak": 0,
        "recent_rejections": deque(maxlen=3),
        "need_reflect": False
    }


PREFERENCE_MAP = {
    "历史文化": ["历史", "文化", "古迹", "古城", "博物馆", "文物", "人文"],
    "自然风光": ["自然", "风景", "公园", "山", "湖", "森林", "户外", "爬山"],
    "拍照打卡": ["拍照", "出片", "打卡", "摄影", "好看"],
    "亲子休闲": ["亲子", "带孩子", "轻松", "休闲"],
    "美食体验": ["美食", "吃", "小吃", "餐厅"],
    "不想排队": ["不想排队", "别排队", "人少", "清静", "不要拥挤"]
}


def extract_city(user_input: str):
    patterns = [
        r"去([\u4e00-\u9fa5]{2,8})(?:旅游|旅行|玩|游玩|看景点)",
        r"在([\u4e00-\u9fa5]{2,8})(?:旅游|旅行|玩|游玩|看景点|查天气)",
        r"([\u4e00-\u9fa5]{2,8})的天气",
        r"([\u4e00-\u9fa5]{2,8})有什么景点",
        r"推荐([\u4e00-\u9fa5]{2,8})"
    ]
    for p in patterns:
        m = re.search(p, user_input)
        if m:
            return m.group(1)
    return None


def extract_budget(user_input: str):
    patterns = [
        r"(?:预算|花费|价格|门票|消费).{0,8}?(?:不超过|最多|低于|控制在|别超过|以内)?\s*(\d+)\s*元",
        r"(\d+)\s*元(?:以内|以下|上限)?",
        r"预算.{0,4}(\d+)"
    ]
    for p in patterns:
        m = re.search(p, user_input)
        if m:
            return int(m.group(1))
    return None


def update_memory_from_user(user_input: str, memory: dict, session_state: dict, prompt_history: list):
    prompt_history.append(f"用户: {user_input}")

    city = extract_city(user_input)
    if city:
        session_state["city"] = city
        prompt_history.append(f"Observation: 已更新会话状态：city={city}")

    budget = extract_budget(user_input)
    if budget is not None:
        memory["budget_max"] = budget
        prompt_history.append(f"Observation: 已更新用户记忆：budget_max={budget}")

    for pref_name, keywords in PREFERENCE_MAP.items():
        for kw in keywords:
            if kw in user_input:
                if "不喜欢" in user_input or "不要" in user_input or "别" in user_input:
                    if pref_name not in memory["dislikes"]:
                        memory["dislikes"].append(pref_name)
                        prompt_history.append(f"Observation: 已更新用户记忆：dislikes += ['{pref_name}']")
                    break
                elif "喜欢" in user_input or "想去" in user_input or "偏好" in user_input:
                    if pref_name not in memory["likes"]:
                        memory["likes"].append(pref_name)
                        prompt_history.append(f"Observation: 已更新用户记忆：likes += ['{pref_name}']")
                    break

    note_keywords = ["不想排队", "人少一点", "轻松一点", "省钱", "适合拍照", "不要太累"]
    for note in note_keywords:
        if note in user_input and note not in memory["notes"]:
            memory["notes"].append(note)
            prompt_history.append(f"Observation: 已更新用户记忆：notes += ['{note}']")

    reject_keywords = ["不喜欢", "不要", "不想", "太贵", "预算不够", "拒绝", "换一个", "不行", "不好", "不合适"]
    accept_keywords = ["可以", "行", "不错", "就这个", "接受", "喜欢", "挺好"]

    is_reject = any(k in user_input for k in reject_keywords)
    is_accept = any(k in user_input for k in accept_keywords)

    if is_reject:
        session_state["reject_streak"] += 1
        session_state["recent_rejections"].append(user_input)
        prompt_history.append(f"Observation: 用户拒绝了上一条推荐。原因：{user_input}")
        prompt_history.append(f"Observation: 连续拒绝次数已更新为 {session_state['reject_streak']}")
    elif is_accept:
        session_state["reject_streak"] = 0
        session_state["need_reflect"] = False
        prompt_history.append("Observation: 用户接受了当前推荐，连续拒绝次数已清零。")

    if session_state["reject_streak"] >= 3:
        session_state["need_reflect"] = True
        reasons = " | ".join(session_state["recent_rejections"])
        prompt_history.append(f"Observation: 用户已连续拒绝3次推荐。最近拒绝原因：{reasons}")
        prompt_history.append("Observation: 你必须先 Reflect 再继续推荐。")


def format_memory(memory: dict) -> str:
    return (
        "【用户记忆】\n"
        f"- 喜欢: {memory['likes']}\n"
        f"- 不喜欢: {memory['dislikes']}\n"
        f"- 预算下限: {memory['budget_min']}\n"
        f"- 预算上限: {memory['budget_max']}\n"
        f"- 备注: {memory['notes']}\n"
    )


def format_session_state(session_state: dict) -> str:
    return (
        "【会话状态】\n"
        f"- 当前城市: {session_state['city']}\n"
        f"- 当前日期: {session_state['date']}\n"
        f"- 已知天气: {session_state['weather']}\n"
        f"- 上一次方案: {session_state['last_plan']}\n"
        f"- 连续拒绝次数: {session_state['reject_streak']}\n"
        f"- 是否必须反思: {session_state['need_reflect']}\n"
    )


def build_full_prompt(memory: dict, session_state: dict, prompt_history: list) -> str:
    recent_history = prompt_history[-20:]
    return (
        format_memory(memory) + "\n" +
        format_session_state(session_state) + "\n" +
        "【最近对话与观察】\n" +
        "\n".join(recent_history)
    )


# =========================
# 4. 截断 Thought-Action 与 JSON Action 解析
# =========================

def truncate_first_thought_action(llm_output: str) -> str:
    """
    只保留第一对 Thought-Action。
    """
    match = re.search(
        r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)',
        llm_output,
        re.DOTALL
    )
    if match:
        truncated = match.group(1).strip()
        if truncated != llm_output.strip():
            print("已截断多余的 Thought-Action 对")
        return truncated
    return llm_output.strip()


def parse_action_json(llm_output: str):
    """
    从模型输出中提取 Action 后面的 JSON。
    """
    match = re.search(r"Action:\s*(\{.*\})", llm_output, re.DOTALL)
    if not match:
        return None

    json_text = match.group(1).strip()

    json_text = re.sub(r"^```json\s*", "", json_text)
    json_text = re.sub(r"^```\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"Action JSON 解析失败: {e}")
        return None


# =========================
# 5. 执行动作
# =========================

def execute_action(action: dict, memory: dict, session_state: dict, prompt_history: list):
    """
    返回：
    - CONTINUE: 继续内层推理
    - WAIT_USER: 暂停并等待用户输入
    """
    if not isinstance(action, dict):
        observation = "错误：Action 不是合法的 JSON 对象。"
        prompt_history.append(f"Observation: {observation}")
        print(f"Observation: {observation}\n" + "=" * 40)
        return "CONTINUE"

    action_type = action.get("type")

    if action_type == "ask_user":
        question = str(action.get("question", "")).strip() or "请补充更多信息。"
        print(f"助手: {question}\n")
        session_state["last_plan"] = question
        return "WAIT_USER"

    if action_type == "reply":
        content = str(action.get("content", "")).strip() or "这是我目前的建议。"
        print(f"助手: {content}\n")
        session_state["last_plan"] = content
        session_state["last_recommendation_text"] = content
        return "WAIT_USER"

    if action_type == "reflect":
        content = str(action.get("content", "")).strip() or "需要重新评估用户偏好并调整策略。"
        observation = f"反思结果：{content}"
        prompt_history.append(f"Observation: {observation}")
        print(f"Observation: {observation}\n" + "=" * 40)
        session_state["need_reflect"] = False
        return "CONTINUE"

    if action_type == "finish":
        content = str(action.get("content", "")).strip() or "本轮任务已完成。"
        print(f"助手: {content}\n")
        session_state["last_plan"] = content
        return "WAIT_USER"

    if action_type == "tool":
        tool_name = action.get("name")
        args = action.get("args", {})

        if not tool_name:
            observation = "错误：tool 类型 Action 缺少 name 字段。"
            prompt_history.append(f"Observation: {observation}")
            print(f"Observation: {observation}\n" + "=" * 40)
            return "CONTINUE"

        if not isinstance(args, dict):
            observation = "错误：tool 类型 Action 的 args 必须是 JSON 对象。"
            prompt_history.append(f"Observation: {observation}")
            print(f"Observation: {observation}\n" + "=" * 40)
            return "CONTINUE"

        if tool_name not in available_tools:
            observation = f"错误：未定义的工具 '{tool_name}'"
            prompt_history.append(f"Observation: {observation}")
            print(f"Observation: {observation}\n" + "=" * 40)
            return "CONTINUE"

        try:
            observation = available_tools[tool_name](**args)
        except TypeError as e:
            observation = f"错误：工具参数不正确 - {e}"
        except Exception as e:
            observation = f"错误：工具执行失败 - {e}"

        if tool_name == "get_weather":
            session_state["weather"] = observation

        if tool_name == "check_ticket_status" and "sold_out" in observation:
            prompt_history.append("Observation: 检测到当前主推荐景点门票已售罄，请自动推荐备选方案。")

        observation_str = f"Observation: {observation}"
        prompt_history.append(observation_str)
        print(f"{observation_str}\n" + "=" * 40)
        return "CONTINUE"

    observation = f"错误：未知的 action type '{action_type}'"
    prompt_history.append(f"Observation: {observation}")
    print(f"Observation: {observation}\n" + "=" * 40)
    return "CONTINUE"


# =========================
# 6. 内层 agent 循环
# =========================

def run_agent_turn(llm, memory: dict, session_state: dict, prompt_history: list, max_steps: int = 8):
    """
    每次用户输入后，agent 最多思考 max_steps 步。
    """
    for i in range(max_steps):
        print(f"--- Agent 内层循环 {i + 1} ---")

        full_prompt = build_full_prompt(memory, session_state, prompt_history)
        llm_output = llm.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)
        llm_output = truncate_first_thought_action(llm_output)

        print(f"模型输出:\n{llm_output}\n")
        prompt_history.append(llm_output)

        action = parse_action_json(llm_output)
        if not action:
            observation = "错误：未能解析到合法的 Action JSON。请确保输出格式为 Action: {...}"
            prompt_history.append(f"Observation: {observation}")
            print(f"Observation: {observation}\n" + "=" * 40)
            continue

        status = execute_action(action, memory, session_state, prompt_history)
        if status == "WAIT_USER":
            break


# =========================
# 7. 主程序：外层用户交互循环
# =========================

if __name__ == "__main__":
    API_KEY = os.getenv("MODELSCOPE_API_KEY", "YOUR_MODELSCOPE_API_KEY")
    BASE_URL = os.getenv("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1")
    MODEL_ID = os.getenv("MODELSCOPE_MODEL_ID", "Qwen/Qwen3.5-397B-A17B")

    os.environ.setdefault("TAVILY_API_KEY", "YOUR_TAVILY_API_KEY")

    llm = OpenAICompatibleClient(
        model=MODEL_ID,
        api_key=API_KEY,
        base_url=BASE_URL
    )

    memory = init_memory()
    session_state = init_session_state()
    prompt_history = []

    print("智能旅行助手已启动。输入“退出”可结束对话。\n")
    print("示例：")
    print("  帮我推荐今天北京适合去的景点")
    print("  我不喜欢历史景点，而且预算别超过50")
    print("  这个太贵了，换一个人少一点的")
    print()

    while True:
        user_input = input("你: ").strip()

        if not user_input:
            continue

        if user_input in {"退出", "exit", "quit"}:
            print("助手: 再见，祝你旅途愉快！")
            break

        update_memory_from_user(user_input, memory, session_state, prompt_history)
        run_agent_turn(llm, memory, session_state, prompt_history, max_steps=8)