from dotenv import load_dotenv
from my_llm import MyLLM # 注意：这里导入我们自己的类

# 加载环境变量
load_dotenv()

# 实例化我们重写的客户端，并指定provider
llm = MyLLM(provider="modelscope") 

# 准备消息
messages = [{"role": "user", "content": "你好，请介绍一下你自己。"}]

# 发起调用，think等方法都已从父类继承，无需重写.think() 是生成器函数（含 yield）
response_stream = llm.think(messages)

# 打印响应
print("ModelScope Response:")
'''
必须触发生成器迭代”
think() 是生成器函数（含 yield），
调用它只会返回一个 “生成器对象”（可理解为 “待执行的代码容器”），
必须通过 “迭代操作” 触发生成器内部代码执行
'''
for chunk in response_stream:
    # chunk在llm.py中已经打印过一遍，这里只需要pass即可
    # print(chunk, end="", flush=True)
    pass