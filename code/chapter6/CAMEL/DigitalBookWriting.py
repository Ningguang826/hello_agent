from colorama import Fore
from camel.societies import RolePlaying
from camel.utils import print_text_animated
from camel.models import ModelFactory
from camel.types import ModelPlatformType
from dotenv import load_dotenv
import os
'''
CAMEL 实现自主协作的基石是两大核心概念：角色扮演 (Role-Playing) 和 引导性提示 (Inception Prompting)。
“引导性提示”是在对话开始前，分别注入给两个智能体的一段精心设计的、结构化的初始指令（System Prompt）。
这段指令就像是为智能体植入的“行动纲领”，它通常包含以下几个关键部分：
1.明确自身角色：例如，“你是一位资深的股票交易员...”
2.告知协作者角色：例如，“你正在与一位优秀的 Python 程序员合作...”
3.定义共同目标：例如，“你们的共同目标是开发一个股票交易策略分析工具。”
4.设定行为约束和沟通协议：这是最关键的一环。例如，指令会要求 AI 用户“一次只提出一个清晰、具体的步骤”，并要求 AI 助理“在完成上一步之前不要追问更多细节”，同时规定双方需在回复的末尾使用特定标志（如 <SOLUTION>）来标识任务的完成。
'''
load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID")

#创建模型
model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
    model_type=LLM_MODEL_ID,
    url=LLM_BASE_URL,
    api_key=LLM_API_KEY
)

# 定义协作任务
task_prompt = """
创作一本关于"拖延症心理学"的短篇电子书，目标读者是对心理学感兴趣的普通大众。

角色分工：
1.由心理学家负责提供心理学依据、章节要求和修改建议
2.由作家负责创作电子书正文


要求：
1. 作家必须输出正文内容，而不是只给建议
2. 心理学家负责提供理论依据、案例方向和修改意见

要求：
1. 作家必须输出正文内容，而不是只给建议
2. 心理学家负责提供理论依据、案例方向和修改意见
3. 内容科学严谨，基于实证研究
4. 语言通俗易懂，避免过多专业术语
5. 包含实用的改善建议和案例分析
6. 篇幅控制在1000-2000字
7. 结构清晰，包含引言、核心章节和总结 
8. 输出语言为中文
9. 不要继续索要下一步指令，每次只执行一个步骤，直到完成整本电子书的创作。
"""

print(Fore.YELLOW + f"协作任务:\n{task_prompt}\n")

# 初始化角色扮演会话
role_play_session = RolePlaying(
    assistant_role_name="作家", 
    user_role_name="心理学家", 
    task_prompt=task_prompt,
    model=model
)

print(Fore.CYAN + f"具体任务描述:\n{role_play_session.task_prompt}\n")

# 开始协作对话
chat_turn_limit, n = 10, 0
input_msg = role_play_session.init_chat()

while n < chat_turn_limit:
    n += 1
    assistant_response, user_response = role_play_session.step(input_msg)
    
    
    print_text_animated(Fore.BLUE + f"心理学家:\n\n{user_response.msg.content}\n")
    print_text_animated(Fore.GREEN + f"作家:\n\n{assistant_response.msg.content}\n")
    
    # 检查任务完成标志
    if "CAMEL_TASK_DONE" in user_response.msg.content:
        print(Fore.MAGENTA + "✅ 电子书创作完成！")
        break
    
    input_msg = assistant_response.msg

print(Fore.YELLOW + f"总共进行了 {n} 轮协作对话")