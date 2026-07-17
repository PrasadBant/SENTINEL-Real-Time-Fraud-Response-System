import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

hf_api_key = os.getenv("HF_API_KEY")
print(f"Key loaded: {hf_api_key is not None}")

url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {hf_api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
        {"role": "user", "content": "Test"}
    ],
    "max_tokens": 10
}

try:
    req_obj = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req_obj, timeout=5.0) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(result)
except Exception as e:
    print(f"Error: {e}")
