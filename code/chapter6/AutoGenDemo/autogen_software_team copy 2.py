"""
AutoGen 软件开发团队协作案例
"""

import os
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 先测试一个版本，使用 OpenAI 客户端
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient


import os
import asyncio
import random
from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()


class RobustOpenAIChatCompletionClient(OpenAIChatCompletionClient):
    async def create(self, *args, **kwargs):
        last_err = None

        for attempt in range(6):
            try:
                result = await super().create(*args, **kwargs)

                # 额外兜底：AutoGen 正常情况下不会返回 None，这里只是防守式校验
                if result is None:
                    raise RuntimeError("model result is None")

                # 有些兼容服务会返回空内容，也当作可重试异常
                content = getattr(result, "content", None)
                if content is None or (isinstance(content, str) and not content.strip()):
                    raise RuntimeError("empty model content")

                return result

            except Exception as e:
                last_err = e
                text = f"{type(e).__name__}: {e}".lower()

                retryable = (
                    ("nonetype" in text and "subscriptable" in text)
                    or "timeout" in text
                    or "rate" in text
                    or "429" in text
                    or "500" in text
                    or "502" in text
                    or "503" in text
                    or "504" in text
                    or "connection" in text
                    or "empty model content" in text
                    or "model result is none" in text
                )

                if not retryable or attempt == 5:
                    raise RuntimeError(
                        f"模型提供方返回异常或非标准响应，重试 {attempt + 1} 次后仍失败：{type(e).__name__}: {e}"
                    ) from e

                # 指数退避 + 抖动
                await asyncio.sleep(min(2 ** attempt, 8) + random.random() * 0.5)


def create_openai_model_client():
    return RobustOpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
        timeout=float(os.getenv("LLM_TIMEOUT", "60")),
        max_retries=1,                  # 让底层少重试，主要靠外层兜底
        include_name_in_message=False,
        add_name_prefixes=True,
        model_info={
            "vision": False,
            "function_calling": False,
            "json_output": False,
            "family": "unknown",
            "structured_output": False,
        },
        temperature=0.2,
        max_tokens=800,                 # 先保守一点，降低长响应风险
    )



import asyncio
from autogen_core.models import UserMessage

async def smoke_test():
    client = create_openai_model_client()
    try:
        result = await client.create([
            UserMessage(content="只回复 OK", source="user")
        ])
        print("AutoGen create 成功：")
        print(result)
    finally:
        await client.close()

asyncio.run(smoke_test())


from autogen_core.model_context import BufferedChatCompletionContext


def create_product_manager(model_client):
    """创建产品经理智能体"""
    system_message = """你是一位经验丰富的产品经理，专门负责软件产品的需求分析和项目规划。

你的核心职责包括：
1. **需求分析**：深入理解用户需求，识别核心功能和边界条件
2. **技术规划**：基于需求制定清晰的技术实现路径
3. **风险评估**：识别潜在的技术风险和用户体验问题
4. **协调沟通**：与工程师和其他团队成员进行有效沟通

当接到开发任务时，请按以下结构进行分析：
1. 需求理解与分析
2. 功能模块划分
3. 技术选型建议
4. 实现优先级排序
5. 验收标准定义

请简洁明了地回应，并在分析完成后说"请工程师开始实现"。"""

    return AssistantAgent(
        name="ProductManager",
        model_client=model_client,
        model_context=BufferedChatCompletionContext(buffer_size=5),
        system_message=system_message,
    )

def create_engineer(model_client):
    """创建软件工程师智能体"""
    system_message = """你是一位资深的软件工程师，擅长 Python 开发和 Web 应用构建。

你的技术专长包括：
1. **Python 编程**：熟练掌握 Python 语法和最佳实践
2. **Web 开发**：精通 Streamlit、Flask、Django 等框架
3. **API 集成**：有丰富的第三方 API 集成经验
4. **错误处理**：注重代码的健壮性和异常处理

当收到开发任务时，请：
1. 仔细分析技术需求
2. 选择合适的技术方案
3. 编写完整的代码实现
4. 添加必要的注释和说明
5. 考虑边界情况和异常处理

请提供完整的可运行代码，并在完成后说"请代码审查员检查"。"""

    return AssistantAgent(
        name="Engineer",
        model_client=model_client,
        model_context=BufferedChatCompletionContext(buffer_size=5),
        system_message=system_message,
    )

# def create_code_reviewer(model_client):
#     """创建代码审查员智能体"""
#     system_message = """你是一位经验丰富的代码审查专家，专注于代码质量和最佳实践。

# 你的审查重点包括：
# 1. **代码质量**：检查代码的可读性、可维护性和性能
# 2. **安全性**：识别潜在的安全漏洞和风险点
# 3. **最佳实践**：确保代码遵循行业标准和最佳实践
# 4. **错误处理**：验证异常处理的完整性和合理性

# 审查流程：
# 1. 仔细阅读和理解代码逻辑
# 2. 检查代码规范和最佳实践
# 3. 识别潜在问题和改进点
# 4. 提供具体的修改建议
# 5. 评估代码的整体质量

# 请提供具体的审查意见，完成后说"代码审查完成，请用户代理测试"。"""

#     return AssistantAgent(
#         name="CodeReviewer",
#         model_client=model_client,
#         system_message=system_message,
#     )

# def create_user_proxy():
#     """创建用户代理智能体"""
#     return UserProxyAgent(
#         name="UserProxy",
#         description="""用户代理，负责以下职责：
# 1. 代表用户提出开发需求
# 2. 执行最终的代码实现
# 3. 验证功能是否符合预期
# 4. 提供用户反馈和建议

# 完成测试后请回复 TERMINATE。""",
#     )

from openai import OpenAI
import os
import json
import time

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL").rstrip("/"),
    max_retries=0,
    timeout=float(os.getenv("LLM_TIMEOUT", "60")),
)

for i in range(20):
    try:
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL_ID"),
            messages=[{"role": "user", "content": "只回复 OK"}],
        )
        print(f"[{i}] OK -> choices exists:", bool(getattr(resp, "choices", None)))
        if not getattr(resp, "choices", None):
            print(resp.model_dump_json(indent=2))
            break
    except Exception as e:
        print(f"[{i}] ERROR -> {type(e).__name__}: {e}")
    time.sleep(1.5)





