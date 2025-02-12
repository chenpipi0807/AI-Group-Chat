from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import requests
import os
from volcenginesdkarkruntime import Ark
import httpx
from collections import deque

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 允许所有来源的 CORS
socketio = SocketIO(app, cors_allowed_origins="*")

# 配置 API 详细信息
DEEPSEEK_API_KEY = "自己去买"
KIMICHAT_API_URL = "https://api.moonshot.cn/v1/chat/completions"
KIMICHAT_API_KEY = "自己去买"

# 初始化 Ark 客户端
client = Ark(
    api_key=DEEPSEEK_API_KEY,
    timeout=httpx.Timeout(timeout=1800)
)

# 用于存储对话上下文
chat_context = deque(maxlen=6)

def handle_kimichat_message(prompt):
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_context])
    full_prompt = f"你是一个群聊智能体，需要你和deepseek智能体互相协助用户解决问题。用户输入的是：{prompt}。\n{context}\nDeepSeek你怎么看？"
    headers = {
        "Authorization": f"Bearer {KIMICHAT_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "moonshot-v1-128k",
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.3
    }
    try:
        response = requests.post(KIMICHAT_API_URL, headers=headers, json=data)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        print(f"Kimi 回复: {content}")  # 打印 Kimi 的回复
        return content
    except Exception as e:
        return f"Kimi请求失败：{str(e)}"

def handle_deepseek_message(prompt):
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_context])
    full_prompt = f"你是一个群聊智能体，需要你和kimi智能体互相协助用户解决问题，需要对kimi的回复内容做出判断再回复。用户输入的是：{prompt}。\n{context}"
    try:
        # 使用流式请求
        stream = client.chat.completions.create(
            model="自己去买我买的是飞舟的deepseek不崩",  # 使用正确的模型 ID
            messages=[{"role": "user", "content": full_prompt}],
            stream=True
        )
        response_content = ""
        for chunk in stream:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.reasoning_content:
                emit('chat_response', {"role": "DeepSeek", "content": chunk.choices[0].delta.reasoning_content}, broadcast=True)
                response_content += chunk.choices[0].delta.reasoning_content
                print(chunk.choices[0].delta.reasoning_content, end="")  # 实时打印 DeepSeek 的回复
            else:
                emit('chat_response', {"role": "DeepSeek", "content": chunk.choices[0].delta.content}, broadcast=True)
                response_content += chunk.choices[0].delta.content
                print(chunk.choices[0].delta.content, end="")  # 实时打印 DeepSeek 的回复
        print()  # 换行
        return response_content
    except Exception as e:
        return f"DeepSeek请求失败：{str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('send_message')
def handle_message(data):
    user_input = data['input']
    chat_history = []

    # 添加用户的最新消息
    chat_history.append({"role": "您", "content": user_input})
    chat_context.append({"role": "您", "content": user_input})
    
    # 处理 Kimichat 的响应
    kimichat_response = handle_kimichat_message(user_input)
    chat_history.append({"role": "Kimi", "content": kimichat_response})
    chat_context.append({"role": "Kimi", "content": kimichat_response})
    
    # 处理 DeepSeek 的响应
    deepseek_response = handle_deepseek_message(user_input)
    chat_history.append({"role": "DeepSeek", "content": deepseek_response})
    chat_context.append({"role": "DeepSeek", "content": deepseek_response})
    
    emit('chat_response', chat_history, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
