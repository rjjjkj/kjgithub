#!/usr/bin/env python3
import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("/var/log/api-server/access.log")

def get_system_specs():
    cpu_cores = os.cpu_count() or 2
    
    # メモリ情報の取得 (/proc/meminfo)
    mem_total_kb = 0
    mem_avail_kb = 0
    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_avail_kb = int(line.split()[1])
    
    mem_total_mb = mem_total_kb // 1024
    mem_avail_mb = mem_avail_kb // 1024
    return cpu_cores, mem_total_mb, mem_avail_mb

def analyze_logs(log_path: Path):
    if not log_path.exists():
        return {"samples": 0, "avg_duration_ms": 1.0, "p95_duration_ms": 2.0, "error_rate": 0.0, "qps": 0.1}

    records = []
    status_codes = []
    durations = []
    
    # 末尾 2000 行を抽出
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-2000:]
            for line in lines:
                try:
                    data = json.loads(line)
                    http = data.get("http", {})
                    path = http.get("path", "")
                    if path == "/health":
                        continue
                    durations.append(float(http.get("duration_ms", 1.0)))
                    status_codes.append(int(http.get("status_code", 200)))
                    records.append(data)
                except Exception:
                    continue
    except Exception:
        pass

    samples = len(durations)
    if samples == 0:
        return {"samples": 0, "avg_duration_ms": 1.0, "p95_duration_ms": 2.0, "error_rate": 0.0, "qps": 0.1}

    durations.sort()
    avg_dur = round(sum(durations) / samples, 2)
    p95_dur = round(durations[int(samples * 0.95)], 2)
    errors = sum(1 for c in status_codes if c >= 400)
    error_rate = round((errors / samples) * 100, 2)

    return {
        "samples": samples,
        "avg_duration_ms": avg_dur,
        "p95_duration_ms": p95_dur,
        "error_rate": error_rate,
        "qps": max(0.5, round(samples / 300, 2))  # 簡易推定
    }

def calculate_optimal_config(cpu_cores, mem_total_mb, mem_avail_mb, metrics):
    # Ollama / DSP 同居考慮: CPU を奪い合わないようワーカーは 1 推奨
    workers = 1

    # AnyIO スレッドプール (同期エンドポイント処理用)
    thread_pool_limit = min(32, max(8, cpu_cores * 4))

    # バックログ & 同時接続上限
    # 1接続あたりメモリ消費を 0.5MB と仮定し、利用可能メモリの 25% を上限とする
    safe_mem_mb = mem_avail_mb * 0.25
    limit_concurrency = max(50, min(1000, int((safe_mem_mb * 1024) / 512)))
    backlog = min(512, limit_concurrency * 2)

    # タイムアウト
    # AI プロキシ (Ollama) があるため、タイムアウトは少し長めに設定
    timeout_keep_alive = 15
    timeout_graceful_shutdown = 10

    # systemd 向け制限
    mem_max_mb = min(1536, max(512, int(mem_total_mb * 0.20)))

    return {
        "uvicorn": {
            "workers": workers,
            "limit_concurrency": limit_concurrency,
            "backlog": backlog,
            "timeout_keep_alive": timeout_keep_alive,
            "timeout_graceful_shutdown": timeout_graceful_shutdown,
        },
        "fastapi_internal": {
            "anyio_thread_pool_tokens": thread_pool_limit,
            "docs_url_enabled": True
        },
        "systemd": {
            "MemoryMax": f"{mem_max_mb}M",
            "CPUQuota": "150%" if cpu_cores >= 4 else "100%"
        }
    }

def main():
    cpu, mem_total, mem_avail = get_system_specs()
    metrics = analyze_logs(LOG_PATH)
    config = calculate_optimal_config(cpu, mem_total, mem_avail, metrics)

    output = {
        "target": "k2-server FastAPI",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hardware_profile": {
            "cpu_cores": cpu,
            "total_ram_mb": mem_total,
            "available_ram_mb": mem_avail
        },
        "traffic_metrics": metrics,
        "calculated_recommendations": config,
        "generated_cli_command": (
            f"/opt/api-server/venv/bin/uvicorn main:app "
            f"--host 0.0.0.0 --port 8000 "
            f"--workers {config['uvicorn']['workers']} "
            f"--limit-concurrency {config['uvicorn']['limit_concurrency']} "
            f"--backlog {config['uvicorn']['backlog']} "
            f"--timeout-keep-alive {config['uvicorn']['timeout_keep_alive']} "
            f"--no-access-log"
        )
    }

    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(output, indent=2))
    else:
        print(f"=== FastAPI 自動サイジング分析レポート ===")
        print(f"CPU: {cpu} コア | 総RAM: {mem_total} MB | 空きRAM: {mem_avail} MB")
        print(f"解析ログ数: {metrics['samples']} | 平均レイテンシ: {metrics['avg_duration_ms']}ms | p95: {metrics['p95_duration_ms']}ms | エラー率: {metrics['error_rate']}%")
        print(f"\n[推奨 Uvicorn パラメータ]")
        for k, v in config["uvicorn"].items():
            print(f"  --{k.replace('_', '-')}: {v}")
        print(f"\n[推奨 systemd リソース制限]")
        print(f"  MemoryMax={config['systemd']['MemoryMax']}")
        print(f"  CPUQuota={config['systemd']['CPUQuota']}")
        print(f"\n[最適化起動コマンド]:\n  {output['generated_cli_command']}")

if __name__ == "__main__":
    main()
