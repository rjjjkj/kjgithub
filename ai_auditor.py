import json
import subprocess
import requests

def run_audit():
    try:
        res = requests.get("http://127.0.0.1:8000/metrics", timeout=5)
        metrics_data = res.json()
    except Exception as e:
        print(f"[Error] メトリクス取得失敗: {e}")
        return

    prompt = f"""あなたは k2-server のシステム設計・監視アドバイザーAIです。
以下のシステムメトリクスJSONを分析し、異常の有無、リソースの余裕度、およびオーディオ再生状態について簡潔に評価してください。

【メトリクスデータ】
{json.dumps(metrics_data, indent=2, ensure_ascii=False)}

【出力要件】
- 挨拶や前置きは排除し、分析結果から開始すること。
- CPU、メモリ、ディスク、DSPモードの観点から具体数値を根拠に評価すること。
"""

    print("=== AI 分析中 (Ollama: qwen2.5:1.5b) ===")
    try:
        result = subprocess.run(
            ["ollama", "run", "qwen2.5:1.5b"],
            input=prompt,
            text=True,
            capture_output=True,
            check=True
        )
        print("\n[AI 監査レポート]")
        print(result.stdout.strip())
    except Exception as e:
        print(f"[Error] Ollama 推論失敗: {e}")

if __name__ == "__main__":
    run_audit()
