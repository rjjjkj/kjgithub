import os, time, json, requests

K2_IP = os.getenv("K2_IP", "100.75.94.51")
OLLAMA_URL = f"http://{K2_IP}:11434"
FASTAPI_URL = f"http://{K2_IP}:8000"

session = requests.Session()
try:
    session.get(f"{OLLAMA_URL}/api/tags", timeout=2)
except requests.exceptions.RequestException:
    try:
        OLLAMA_URL = "http://127.0.0.1:11434"
        FASTAPI_URL = "http://127.0.0.1:8000"
        session.get(f"{OLLAMA_URL}/api/tags", timeout=2)
    except requests.exceptions.RequestException:
        OLLAMA_URL = f"http://{K2_IP}:11434"
        FASTAPI_URL = f"http://{K2_IP}:8000"
        session.proxies = {"http": "http://localhost:1055", "https": "http://localhost:1055"}

def analyze_and_repair():
    report = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "target": FASTAPI_URL, "services": {}, "recommendation": {}, "auto_repair": []}

    t0 = time.time()
    try:
        r = session.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        latency_ms = round((time.time() - t0) * 1000, 1)
        models = [m["name"] for m in r.json().get("models", [])]
        report["services"]["ollama"] = {"status": "ONLINE" if r.status_code == 200 else f"HTTP_{r.status_code}", "latency_ms": latency_ms, "models": models}
    except Exception as e:
        report["services"]["ollama"] = {"status": "OFFLINE", "error": str(e), "models": []}

    for ep in ["/docs", "/openapi.json"]:
        try:
            r = session.get(f"{FASTAPI_URL}{ep}", timeout=3)
            report["services"][f"fastapi_{ep}"] = r.status_code
            if ep == "/openapi.json" and r.status_code == 200:
                report["services"]["registered_routes"] = list(r.json().get("paths", {}).keys())
        except Exception as e:
            report["services"][f"fastapi_{ep}"] = f"UNREACHABLE ({type(e).__name__})"

    routes = report["services"].get("registered_routes", [])
    if "/api/system/tune" in routes:
        try:
            rt = session.post(f"{FASTAPI_URL}/api/system/tune", timeout=5)
            if rt.status_code == 405:
                rt = session.get(f"{FASTAPI_URL}/api/system/tune", timeout=5)
            report["services"]["fastapi_/api/system/tune"] = rt.status_code
            report["auto_repair"].append(f"Triggered /api/system/tune -> HTTP {rt.status_code}")
        except Exception as e:
            report["services"]["fastapi_/api/system/tune"] = str(e)

    models = report["services"]["ollama"].get("models", [])
    latency = report["services"]["ollama"].get("latency_ms", 999)
    best_model = "qwen2.5:1.5b" if ("qwen2.5:1.5b" in models and latency < 300) else ("qwen2.5:0.5b" if "qwen2.5:0.5b" in models else (models[0] if models else "NONE"))

    report["recommendation"] = {
        "optimal_model": best_model,
        "recommended_timeout_sec": 30 if best_model == "qwen2.5:1.5b" else 15,
        "ai_router_mounted": any("ai" in p for p in routes),
        "audio_router_mounted": any("audio" in p for p in routes)
    }
    return report

def run_ai_config_diagnosis(report):
    model = report["recommendation"]["optimal_model"]
    if model == "NONE":
        print("エラー: 利用可能なOllamaモデルが見つかりません。")
        return
    prompt = f"以下のサーバー診断JSONを分析し、日本語の箇条書き3点（1.稼働状態 2.ボトルネック 3.推奨アクション）で簡潔に出力せよ:\n{json.dumps(report, ensure_ascii=False)}"
    print(f"\n=== [{model}] による自動設定診断 ===")
    try:
        res = session.post(f"{OLLAMA_URL}/api/generate", json={"model": model, "prompt": prompt, "stream": False}, timeout=45)
        res.raise_for_status()
        print(res.json().get("response", ""))
    except Exception as e:
        print("AI診断エラー:", e)

if __name__ == "__main__":
    result = analyze_and_repair()
    print("=== [k2-server 設定分析・自動修復レポート] ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    run_ai_config_diagnosis(result)
