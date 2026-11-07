import json
import time
import subprocess
import os
import requests
from websocket import create_connection

CAMILLADSP_WS = "ws://127.0.0.1:1234"

def get_camilladsp_metrics():
    try:
        ws = create_connection(CAMILLADSP_WS, timeout=3)
        
        # 再生側・キャプチャ側のピーク・RMS レベル取得
        ws.send('"GetPlaybackSignalLevels"')
        playback_levels = json.loads(ws.recv())
        
        ws.send('"GetCaptureSignalLevels"')
        capture_levels = json.loads(ws.recv())
        
        ws.send('"GetClippedSamples"')
        clipped = json.loads(ws.recv())
        
        ws.send('"GetVolume"')
        volume = json.loads(ws.recv())
        
        ws.close()
        
        return {
            "volume_db": volume.get("value"),
            "clipped_samples": clipped.get("value", 0),
            "playback_signal_levels": playback_levels.get("value", {}),
            "capture_signal_levels": capture_levels.get("value", {})
        }
    except Exception as e:
        return {"error": f"CamillaDSP WebSocket 接続失敗: {e}"}

def get_current_track():
    try:
        out = subprocess.check_output(
            ["journalctl", "-u", "raspotify", "-n", "15", "--output=cat"],
            stderr=subprocess.DEVNULL, text=True
        )
        tracks = [l for l in out.splitlines() if "Loading <" in l]
        if tracks:
            return tracks[-1].strip()
    except Exception:
        pass
    return "不明または再生停止中"

def run_audio_analysis():
    print("=== [1/2] CamillaDSP リアルタイム内部シグナル取得中... ===")
    dsp_data = get_camilladsp_metrics()
    
    if "error" in dsp_data:
        print(f"[Error] {dsp_data['error']}")
        return

    track_info = get_current_track()
    
    # 現在の DSP モード取得
    mode = "speaker"
    if os.path.exists("/etc/camilladsp/current_mode"):
        try:
            with open("/etc/camilladsp/current_mode") as f:
                mode = f.read().strip()
        except Exception:
            pass

    analysis_payload = {
        "dsp_mode": mode,
        "dac": "Fostex HP-A3 (96kHz / 24bit bit-perfect)",
        "track_info": track_info,
        "dsp_telemetry": dsp_data
    }

    print("=== [2/2] AI 音響工学診断レポート生成 (Ollama) ===")
    prompt = f"""あなたはプロオーディオマスタリングエンジニア兼 CamillaDSP 音響アーキテクトです。
現在稼働中の CamillaDSP リアルタイム音響テレメトリデータを分析し、クリッピング余裕度、ダイナミクス、および音響バランスを専門的に評価してください。

【実測テレメトリ】
{json.dumps(analysis_payload, indent=2, ensure_ascii=False)}

【出力要件】
- 挨拶や前置きは完全に排除し、分析評価から開始すること。
- 入力（Capture）と出力（Playback）のゲイン差から、Preamp (-6.5dB) と Loudness / FIR 畳み込みが安全に機能しているか評価すること。
- クリッピングサンプル数（clipped_samples）に基づく DAC アナログ段の歪みリスクの有無。
- 対象ハードウェア（DENON SC-M37 スピーカー または radius Noir IEM）の特性に合わせた音響的ワンポイント助言。
"""

    try:
        res = subprocess.run(
            ["ollama", "run", "qwen2.5:1.5b"],
            input=prompt,
            text=True,
            capture_output=True,
            check=True
        )
        print("\n--- [音響分析レポート] ---")
        print(res.stdout.strip())
    except Exception as e:
        print(f"[Error] Ollama 推論失敗: {e}")

if __name__ == "__main__":
    run_audio_analysis()
