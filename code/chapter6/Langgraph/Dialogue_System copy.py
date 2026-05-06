"""
智能搜索助手 - 基于 LangGraph + Tavily API 的真实搜索系统
1. 理解用户需求
2. 使用Tavily API真实搜索信息  
3. 生成基于搜索结果的回答
"""

import asyncio
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
import os
from dotenv import load_dotenv
from tavily import TavilyClient

# 加载环境变量
load_dotenv()

# 定义状态结构
class SearchState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str        # 用户查询
    search_query: str      # 优化后的搜索查询
    search_results: str    # Tavily搜索结果
    final_answer: str      # 最终答案
    step: str              # 当前流程步骤（start/understood/searched/search_failed/completed）

# 初始化模型和Tavily客户端
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL_ID"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    temperature=0.7
)

# 初始化Tavily客户端
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# 每个节点是「输入 State → 处理逻辑 → 输出更新后的 State」的纯函数，无副作用，便于调试和扩展。


def understand_query_node(state: SearchState) -> SearchState:
    """节点1：理解用户查询并生成搜索关键词"""

    # 1. 提取最新的用户消息（从 messages 列表倒序找 HumanMessage）
    user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    # 2. 构造提示词，让 LLM 分析需求+生成搜索词
    understand_prompt = f"""
    分析用户的查询："{user_message}"

    请完成两个任务：
    1. 简洁总结用户想要了解什么
    2. 生成最适合搜索的关键词（中英文均可，要精准）

    格式：
    理解：[用户需求总结]
    搜索词：[最佳搜索关键词]"""

    # 3. 调用 LLM 生成结果
    response = llm.invoke([SystemMessage(content=understand_prompt)])
    response_text = response.content

    # 4. 提取搜索关键词（兼容不同输出格式）
    search_query = user_message  # 兜底：若解析失败则用原始查询
    
    if "搜索词：" in response_text:
        search_query = response_text.split("搜索词：")[1].strip()
    elif "关键词：" in response_text:
        search_query = response_text.split("关键词：")[1].strip()
    elif "搜索关键词：" in response_text:
        search_query = response_text.split("搜索关键词：")[1].strip()
    
    return {
        "user_query": response.content,
        "search_query": search_query,
        "step": "understood",
        "messages": [AIMessage(content=f"我理解您的需求：{response.content}")]
        # AIMessage = AI 说的话,是 LangChain 内置的标准消息类型
    }

def tavily_search_node(state: SearchState) -> SearchState:
    """节点2：使用Tavily API进行真实搜索"""

    search_query = state["search_query"]
    
    try:
        print(f"🔍 正在搜索: {search_query}")
        
        # 1.调用Tavily搜索API
        response = tavily_client.search(
            query=search_query,
            search_depth="basic",  # 搜索深度（basic=基础，advanced=深度）
            include_answer=True,   # 要求 Tavily 生成综合答案
            include_raw_content=False,  # 不返回原始网页内容（减少冗余）
            max_results=5               # 最多返回 5 条结果
        )        
        
        # 2. 格式化搜索结果
        search_results = ""
        # 优先使用Tavily的综合答案
        if response.get("answer"):
            search_results = f"综合答案：\n{response['answer']}\n\n"
        
        # 追加具体搜索结果（标题+内容+来源）
        if response.get("results"):
            search_results += "相关信息：\n"
            for i, result in enumerate(response["results"][:3], 1):  # 只取前 3 条
                title = result.get("title", "")
                content = result.get("content", "")
                url = result.get("url", "")
                search_results += f"{i}. {title}\n{content}\n来源：{url}\n\n"
        
        if not search_results:
            search_results = "抱歉，没有找到相关信息。"
        
        return {
            "search_results": search_results,
            "step": "searched",
            "messages": [AIMessage(content=f"✅ 搜索完成！找到了相关信息，正在为您整理答案...")]
        }
        
    except Exception as e:
        error_msg = f"搜索时发生错误: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "search_results": f"搜索失败：{error_msg}",
            "step": "search_failed",
            "messages": [AIMessage(content="❌ 搜索遇到问题，我将基于已有知识为您回答")]
        }

def generate_answer_node(state: SearchState) -> SearchState:
    """节点3：生成最终答案"""
    
    # 1. 搜索失败的降级逻辑，降级为 LLM 自有知识
    if state["step"] == "search_failed":
        fallback_prompt = f"""
        搜索API暂时不可用，请基于您的知识回答用户的问题：

        用户问题：{state['user_query']}

        请提供一个有用的回答，并说明这是基于已有知识的回答。"""
        
        response = llm.invoke([SystemMessage(content=fallback_prompt)])
        
        return {
            "final_answer": response.content,
            "step": "completed",
            "messages": [AIMessage(content=response.content)]
        }
    
    # 2. 搜索成功：基于搜索结果生成回答
    answer_prompt = f"""
    基于以下搜索结果为用户提供完整、准确的答案：

    用户问题：{state['user_query']}

    搜索结果：
    {state['search_results']}

    请要求：
    1. 综合搜索结果，提供准确、有用的回答
    2. 如果是技术问题，提供具体的解决方案或代码
    3. 引用重要信息的来源
    4. 回答要结构清晰、易于理解
    5. 如果搜索结果不够完整，请说明并提供补充建议"""

    response = llm.invoke([SystemMessage(content=answer_prompt)])
    
    return {
        "final_answer": response.content,
        "step": "completed",
        "messages": [AIMessage(content=response.content)]
    }


'''构建LangGraph 搜索工作流'''
def create_search_assistant():
    # 1. 初始化状态图（绑定 SearchState 结构）
    workflow = StateGraph(SearchState)
    
    # 2. 注册节点（节点名 → 节点函数）
    workflow.add_node("understand", understand_query_node)
    workflow.add_node("search", tavily_search_node)
    workflow.add_node("answer", generate_answer_node)
    
    # 3. 定义节点执行顺序（线性边）
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "search")
    workflow.add_edge("search", "answer")
    workflow.add_edge("answer", END)
    
    # 4. 配置记忆（保存会话状态）
    memory = InMemorySaver() # 内存级别的状态存储（重启后丢失，生产环境可替换为 Redis / 数据库）
    app = workflow.compile(checkpointer=memory) # 编译工作流为异步可执行对象，支持 astream 流式执行
    
    return app

async def main():

    # 1.检查API密钥
    if not os.getenv("TAVILY_API_KEY"):
        print("❌ 错误：请在.env文件中配置TAVILY_API_KEY")
        return
    
    # 2. 创建工作流实例
    app = create_search_assistant()
    
    print("🔍 智能搜索助手启动！")
    print("我会使用Tavily API为您搜索最新、最准确的信息,支持各种问题：新闻、技术、知识问答等")
    print("(输入 'quit' 退出)\n")
    session_count = 0 # 会话计数器（用于生成唯一会话 ID）
    
    while True:
        user_input = input("🤔 您想了解什么: ").strip()
        
        if user_input.lower() in ['quit', 'q', '退出', 'exit']:
            print("感谢使用！再见！👋")
            break
        
        if not user_input: # 空输入跳过
            continue

        # 3. 生成唯一会话 ID（保证记忆隔离）
        session_count += 1
        config = {"configurable": {"thread_id": f"search-session-{session_count}"}}

        # 4. 初始化状态（仅传入用户消息，其他字段默认空）
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "user_query": "",
            "search_query": "",
            "search_results": "",
            "final_answer": "",
            "step": "start"
        }
        
        try:
            print("\n" + "="*60)
            # 异步执行工作流   astream 为 LangGraph 工作流的异步流式执行器
            async for output in app.astream(initial_state, config=config):
                for node_name, node_output in output.items(): # node_name 是自定义的节点名，node_output结构就是前面定义的 SearchState 结构
                    '''
                    {
                        "understand": {
                            "messages": [...],
                            "search_query": "...",
                            "step": "understood"
                        }
                    }
                    '''

                    if "messages" in node_output and node_output["messages"]:
                        latest_message = node_output["messages"][-1]
                        # 因为message定义messages: Annotated[list, add_messages]，自动追加新消息
                        # 整个工作流的对话历史
                        # messages = [
                        # HumanMessage(content="什么是拖延症？"),   # 用户输入
                        # AIMessage(content="我理解了你的问题..."), # 理解节点加的
                        # AIMessage(content="搜索完成..."),        # 搜索节点加的
                        # AIMessage(content="最终答案是...")       # 回答节点加的
                        # ]       
                        if isinstance(latest_message, AIMessage):
                            if node_name == "understand":
                                print(f"🧠 理解阶段: {latest_message.content}")
                            elif node_name == "search":
                                print(f"🔍 搜索阶段: {latest_message.content}")

                                '''
                                节点2的search函数中最终返回的AIMessage的内容是 "✅ 搜索完成！找到了相关信息，正在为您整理答案..." 或 "❌ 搜索遇到问题，我将基于已有知识为您回答"
                                但在函数开头就会打印 "🔍 正在搜索: {search_query}"，这部分内容并不属于messages列表中的AIMessage，而是直接在函数内打印的，所以不会跟在🔍搜索阶段:，而是在前面。
                                '''

                            elif node_name == "answer":
                                print(f"\n💡 最终回答:\n{latest_message.content}")
            
            print("\n" + "="*60 + "\n")
        
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            print("请重新输入您的问题。\n")

if __name__ == "__main__":
    asyncio.run(main())