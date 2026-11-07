import json
import requests

url = "http://100.75.94.51:11434/api/generate"
payload = {"model": "qwen2.5", "prompt": "ping", "stream": True}

try:
    with requests.post(url, json=payload, stream=True, timeout=30) as res:
        res.raise_for_status()
        for line in res.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                print(chunk.get("response", ""), end="", flush=True)
                if chunk.get("done", False):
                    print()
except requests.exceptions.RequestException as e:
    print("\n通信エラー:", e)
