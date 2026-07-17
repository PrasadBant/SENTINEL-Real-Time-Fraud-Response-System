import urllib.request
import json
url = "https://cloudflare-dns.com/dns-query?name=api-inference.huggingface.co&type=A"
req = urllib.request.Request(url, headers={'accept': 'application/dns-json'})
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(e)
