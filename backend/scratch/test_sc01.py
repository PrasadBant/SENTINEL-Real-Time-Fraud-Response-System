import requests

API_URL = "http://127.0.0.1:8000/transaction"

tx = {
    "tx_id": "TEST-SC01-HOP0",
    "timestamp": "2023-10-27T10:00:00Z",
    "sender_account": "ACC-VICTIM-999",
    "receiver_account": "ACC-LAYER1-111",
    "amount": 1000000,
    "currency": "INR",
    "channel": "IMPS",
    "hop_number": 0
}

resp = requests.post(API_URL, json=tx)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
