from typing import Optional, Dict, List
import time
import ast
from hello_agents import Agent, HelloAgentsLLM, Config, Message

# 默认规划器提示词模板
DEFAULT_PLANNER_PROMPT = """
你是一个顶级的AI规划专家。你的任务是将用户提出的复杂问题分解成一个由多个简单步骤组成的行动计划。
请确保计划中的每个步骤都是一个独立的、可执行的子任务，并且严格按照逻辑顺序排列。
你的输出必须是一个Python列表，其中每个元素都是一个描述子任务的字符串。

问题: {question}

请严格按照以下格式输出你的计划:
```python
["步骤1", "步骤2", "步骤3", ...]
```
"""

# 默认执行器提示词模板
DEFAULT_EXECUTOR_PROMPT = """
你是一位顶级的AI执行专家。你的任务是严格按照给定的计划，一步步地解决问题。
你将收到原始问题、完整的计划、以及到目前为止已经完成的步骤和结果。
请你专注于解决"当前步骤"，并仅输出该步骤的最终答案，不要输出任何额外的解释或对话。

# 原始问题:
{question}

# 完整计划:
{plan}

# 历史步骤与结果:
{history}

# 当前步骤:
{current_step}

请仅输出针对"当前步骤"的回答:
"""
class MyPlanAndSolveAgent(Agent):
    """
    Plan-and-Solve Agent
    先规划，再逐步执行
    """
    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        planner_prompt: Optional[str] = None,
        executor_prompt: Optional[str] = None,
        verbose: bool = True
    ):
        super().__init__(name, llm, system_prompt, config)

        self.planner_prompt = (
            planner_prompt
            if planner_prompt
            else DEFAULT_PLANNER_PROMPT
        )

        self.executor_prompt = (
            executor_prompt
            if executor_prompt
            else DEFAULT_EXECUTOR_PROMPT
        )

        self.verbose = verbose

        print(f"✅ {name} 初始化完成")

    def run(self, input_text: str, **kwargs) -> str:
        """
        执行 Plan-and-Solve 流程
        """

        self._log(f"\n🤖 {self.name} 开始处理问题:")
        self._log(input_text)

        # 1. 生成计划
        plan = self._generate_plan(input_text, **kwargs)

        if not plan:
            failed_msg = "无法生成有效计划。"

            self.add_message(Message(input_text, "user"))
            self.add_message(Message(failed_msg, "assistant"))

            return failed_msg

        # 2. 执行计划
        final_answer = self._execute_plan(
            question=input_text,
            plan=plan,
            **kwargs
        )

        # 3. 写入历史
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_answer, "assistant"))

        return final_answer

    def _generate_plan(
        self,
        question: str,
        **kwargs
    ) -> List[str]:
        """
        生成任务计划
        """

        self._log("\n--- 正在生成计划 ---")

        prompt = self.planner_prompt.format(
            question=question
        )

        response_text = self._call_llm(
            prompt,
            **kwargs
        )

        self._log(response_text)

        try:
            plan_str = (
                response_text
                .split("```python")[1]
                .split("```")[0]
                .strip()
            )
            # .split("```python")[1]   → 切掉前面的废话
            # .split("```")[0]        → 切掉后面的废话
            # .strip()                → 去掉空格换行

            plan = ast.literal_eval(plan_str)

            if isinstance(plan, list):
                self._log("\n✅ 计划解析成功")
                return plan

            return []

        except Exception as e:
            self._log(f"\n❌ 计划解析失败: {e}")
            return []

    def _execute_plan(
        self,
        question: str,
        plan: List[str],
        **kwargs
    ) -> str:
        """
        按步骤执行计划
        """

        history = ""
        final_answer = ""

        self._log("\n--- 开始执行计划 ---")

        for i, step in enumerate(plan, 1):

            self._log(
                f"\n-> 正在执行步骤 {i}/{len(plan)}"
            )

            self._log(f"当前步骤: {step}")

            prompt = self.executor_prompt.format(
                question=question,
                plan=plan,
                history=history if history else "无",
                current_step=step
            )

            response_text = self._call_llm(
                prompt,
                **kwargs
            )

            self._log("\n[步骤结果]")
            self._log(response_text)

            history += (
                f"步骤{i}: {step}\n"
                f"结果: {response_text}\n\n"
            )

        final_answer = response_text
        self._log("\n✅ 全部步骤执行完成")

        return final_answer

    def _call_llm(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """
        调用LLM
        """

        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]

        if hasattr(self.llm, "invoke"): # hasattr(self.llm, "invoke")：检测 LLM 实例是否实现invoke方法
            return self.llm.invoke(
                messages,
                **kwargs
            ) or ""

        if hasattr(self.llm, "think"):
            return self.llm.think(
                messages=messages
            ) or ""

        raise AttributeError(
            "llm对象必须实现 invoke 或 think 方法"
        )

    def _log(self, message: str):
        """
        日志输出
        """

        if self.verbose:
            print(message)