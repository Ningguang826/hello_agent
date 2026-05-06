from typing import Optional, Dict
import time

from hello_agents import Agent, HelloAgentsLLM, Config, Message



DEFAULT_PROMPTS = {
    "initial": """
请根据以下要求完成任务:

任务: {task}

请提供一个完整、准确的回答。
""",
    "reflect": """
请仔细审查以下回答，并找出可能的问题或改进空间:

# 原始任务:
{task}

# 当前回答:
{content}

请分析这个回答的质量，指出不足之处，并提出具体的改进建议。
如果回答已经很好，请回答"无需改进"。
""",
    "refine": """
请根据反馈意见改进你的回答:

# 原始任务:
{task}

# 上一轮回答:
{last_attempt}

# 反馈意见:
{feedback}

请提供一个改进后的回答。
"""
}


class MyReflectionAgent(Agent):
    """
    重写的 Reflection Agent - 通过“生成-反思-改进”循环提升回答质量
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        max_iterations: int = 3,
        prompts: Optional[Dict[str, str]] = None,
        sleep_seconds: float = 0
    ):
        super().__init__(name, llm, system_prompt, config)
        self.max_iterations = max_iterations
        self.prompts = prompts if prompts else DEFAULT_PROMPTS
        self.sleep_seconds = sleep_seconds
        self.current_history = []

        print(f"✅ {name} 初始化完成，最大反思轮数: {max_iterations}")

    def run(self, input_text: str, **kwargs) -> str:
        """运行 Reflection Agent"""
        self.current_history = []

        print(f"\n🤖 {self.name} 开始处理任务: {input_text}")

        # 1. 初始回答
        initial_prompt = self.prompts["initial"].format(task=input_text)
        answer = self._call_llm(initial_prompt, **kwargs)
        print("\n--- 初始回答 ---")
        print(answer)

        self.current_history.append({
            "type": "execution",
            "content": answer
        })

        # 2. 反思-改进循环
        for iteration in range(self.max_iterations):
            print(f"\n--- 第 {iteration + 1}/{self.max_iterations} 轮反思 ---")

            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)

            # a. 反思
            reflect_prompt = self.prompts["reflect"].format(
                task=input_text,
                content=answer
            )
            feedback = self._call_llm(reflect_prompt, **kwargs)
            print("\n[反思反馈]")
            print(feedback)

            self.current_history.append({
                "type": "reflection",
                "content": feedback
            })

            # b. 停止条件
            if self._should_stop(feedback):
                print("\n✅ 反思认为当前回答无需改进，任务完成。")
                break

            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)

            # c. 根据反馈优化
            refine_prompt = self.prompts["refine"].format(
                task=input_text,
                last_attempt=answer,
                feedback=feedback
            )
            answer = self._call_llm(refine_prompt, **kwargs)

            print("\n[改进后回答]")
            print(answer)
            self.current_history.append({
                "type": "execution",
                "content": answer
            })

        # 3. 写入 Agent 对话记忆
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(answer, "assistant"))

        return answer

    def _call_llm(self, prompt: str, **kwargs) -> str:
        """调用 LLM 并返回文本结果"""
        messages = [{"role": "user", "content": prompt}]

        if hasattr(self.llm, "invoke"):
            return self.llm.invoke(messages, **kwargs) or ""

        if hasattr(self.llm, "think"):
            return self.llm.think(messages=messages) or ""

        raise AttributeError("当前 llm 对象必须实现 invoke 或 think 方法。")

    def _should_stop(self, feedback: str) -> bool:
        """判断是否停止反思循环"""
        feedback_lower = feedback.lower()
        return (
            "无需改进" in feedback
            or "不需要改进" in feedback
            or "no need for improvement" in feedback_lower
            or "no improvement needed" in feedback_lower
        )