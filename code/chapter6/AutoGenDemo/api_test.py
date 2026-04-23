import openai

client = openai.OpenAI(
  api_key="sk-c98fDI1txkGS8MiE4f95D59248B949C68992Fa9c52F93bEd",  
  base_url="https://aihubmix.com/v1"
)

response = client.chat.completions.create(
  model="gpt-4o-free",
  messages=[
      {"role": "user", "content": "Hello, how are you?"}
  ]
)

print(response.choices[0].message.content)