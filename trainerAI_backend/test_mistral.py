import json
import requests

API_KEY = "tWyi4oWyPNSFNB7d7k6R3C3G4MJEcdgI"
URL = "https://api.mistral.ai/v1/chat/completions"

payload = {
    "model": "mistral-small-latest",
    "messages": [
        {
            "role": "system",
            "content": "You are an AutoCAD training assistant. Give 2-4 sentences of guidance."
        },
        {
            "role": "user",
            "content": "Active tool: LINE\nLast command: LINE 0,0 10,10\nWhat should the user do next?"
        }
    ],
    "temperature": 0.3,
    "max_tokens": 256,
}

response = requests.post(
    URL,
    json=payload,
    headers={"Authorization": f"Bearer {API_KEY}"},
)

print("Status:", response.status_code)
if response.ok:
    print(response.json()["choices"][0]["message"]["content"])
else:
    print(response.text)
