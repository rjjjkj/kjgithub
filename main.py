import json
import logging
import sys
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request

# Logstash / SIEM 向け NDJSON フォーマッタ
class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # extra 経由のカスタムパラメータを展開
        if hasattr(record, "props") and isinstance(record.props, dict):
            log_data.update(record.props)

        # スタックトレースの展開
        if record.exc_info:
            log_data["error"] = {
                "traceback": self.formatException(record.exc_info)
            }

        return json.dumps(log_data, ensure_ascii=False)

# 標準出力を JSON フォーマッタへ統一
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONLogFormatter())

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = [handler]

access_logger = logging.getLogger("api.access")
system_logger = logging.getLogger("api.system")

app = FastAPI(title="k2-server API", version="1.0.0")

# 構造化アクセスログ & 処理時間計測ミドルウェア
@app.middleware("http")
async def json_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    # プロキシ・Tailscale 経由のクライアントIP解決
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    status_code = response.status_code

    log_props = {
        "event_type": "http_access",
        "http": {
            "client_ip": client_ip,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_agent": request.headers.get("user-agent", "-"),
        }
    }

    # ステータスコードに応じたログレベルの自動昇格
    msg = f"{request.method} {request.url.path} -> {status_code} ({duration_ms}ms)"
    if status_code >= 500:
        access_logger.error(msg, extra={"props": log_props})
    elif status_code >= 400:
        access_logger.warning(msg, extra={"props": log_props})
    else:
        access_logger.info(msg, extra={"props": log_props})

    response.headers["X-Process-Time"] = f"{duration_ms}ms"
    return response

# audio_router のマウント
try:
    from audio_router import router as audio_router
    app.include_router(audio_router)
    system_logger.info("Mounted router: audio_router")
except Exception as e:
    system_logger.warning(f"Skipped audio_router: {e}")

# tailscale_router のマウント
try:
    from tailscale_router import router as tailscale_router
    app.include_router(tailscale_router)
    system_logger.info("Mounted router: tailscale_router")
except Exception as e:
    system_logger.warning(f"Skipped tailscale_router: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok"}
