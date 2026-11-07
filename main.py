import logging
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-server")

app = FastAPI(title="k2-server API", version="1.0.0")

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
