import urllib.request
import json
url = "https://dns.google/resolve?name=api-inference.huggingface.co"
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(e)
