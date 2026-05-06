import os
from typing import Optional
from openai import OpenAI
from hello_agents import HelloAgentsLLM

llm_client = HelloAgentsLLM(
    provider="ollama",
    model="qwen3.5:4b", # 需与 `ollama run` 指定的模型一致
    base_url="http://localhost:11434/v1",
    api_key="ollama" # 本地服务同样不需要真实 Key
)
