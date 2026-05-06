import os
from typing import Optional
from openai import OpenAI
from hello_agents import HelloAgentsLLM

llm_client = HelloAgentsLLM(
    provider="vllm",
    model="qwen3.5:4b", # 需与服务启动时指定的模型一致
    base_url="http://localhost:8000/v1",
    api_key="vllm" # 本地服务通常不需要真实API Key，可填任意非空字符串
)
