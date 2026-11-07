import json
import logging
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request

# 構造化 NDJSON フォーマッタ
class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "props") and isinstance(record.props, dict):
            log_data.update(record.props)
        if record.exc_info:
            log_data["error"] = {"traceback": self.formatException(record.exc_info)}
        return json.dumps(log_data, ensure_ascii=False)

# ロガー設定
json_formatter = JSONLogFormatter()

# 1. コンソール出力 (journald 向け)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(json_formatter)

# 2. 直接ファイル出力 (10MB x 5世代ローテーション)
file_handler = RotatingFileHandler(
    "/var/log/api-server/access.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
file_handler.setFormatter(json_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = [stream_handler, file_handler]

access_logger = logging.getLogger("api.access")
system_logger = logging.getLogger("api.system")

app = FastAPI(title="k2-server API", version="1.0.0")

# アクセスログ計測ミドルウェア
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

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

    msg = f"{request.method} {request.url.path} -> {status_code} ({duration_ms}ms)"
    if status_code >= 500:
        access_logger.error(msg, extra={"props": log_props})
    elif status_code >= 400:
        access_logger.warning(msg, extra={"props": log_props})
    else:
        access_logger.info(msg, extra={"props": log_props})

    response.headers["X-Process-Time"] = f"{duration_ms}ms"
    return response

# ルーター登録
for mod_name, attr_name in [("audio_router", "router"), ("tailscale_router", "router"), ("ai_router", "router")]:
    try:
        mod = __import__(mod_name, fromlist=[attr_name])
        app.include_router(getattr(mod, attr_name))
        system_logger.info(f"Mounted router: {mod_name}")
    except Exception as e:
        system_logger.warning(f"Skipped {mod_name}: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok"}
