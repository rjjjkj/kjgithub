import time
import logging
from fastapi import FastAPI, Request

# ログ設定 (systemd / journalctl 向け)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("api-access")

app = FastAPI(title="k2-server API", version="1.0.0")

# アクセスログ & レスポンスタイム計測ミドルウェア
@app.middleware("http")
async def custom_access_log_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    # クライアントIPの取得（プロキシ・Tailscale経由も考慮）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    response = await call_next(request)

    # 処理時間の算出 (ミリ秒)
    process_time = (time.perf_counter() - start_time) * 1000

    # ログ出力: IP - "METHOD PATH" STATUS - TIMEms
    logger.info(
        f'{client_ip} - "{request.method} {request.url.path}" '
        f'{response.status_code} - {process_time:.2f}ms'
    )

    # クライアント側でも確認できるようヘッダーにも付与
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response

# audio_router のマウント
try:
    from audio_router import router as audio_router
    app.include_router(audio_router)
    logger.info("Loaded: audio_router")
except Exception as e:
    logger.warning(f"Skipped audio_router: {e}")

# tailscale_router のマウント
try:
    from tailscale_router import router as tailscale_router
    app.include_router(tailscale_router)
    logger.info("Loaded: tailscale_router")
except Exception as e:
    logger.warning(f"Skipped tailscale_router: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok"}
