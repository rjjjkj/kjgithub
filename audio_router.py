import os, subprocess
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

router = APIRouter(prefix="/api/audio", tags=["audio"])
UPLOAD_DIR = "/home/k2/audio_inbox"

@router.post("/upload")
async def receive_audio(file: UploadFile = File(...), apply_camilladsp: str = Form("false")):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    os.chmod(dest, 0o644)
    try:
        os.chown(dest, 1000, 1000)
    except Exception:
        pass
    p_stat = "saved"
    if apply_camilladsp.lower() == "true":
        subprocess.Popen(["aplay", "-D", "plughw:Loopback,0,0", "-q", dest], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p_stat = "playing_via_loopback"
    return {"status": "success", "filename": file.filename, "bytes": len(content), "path": dest, "playback": p_stat}

@router.get("/status")
def audio_status():
    files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
    return {"status": "ready", "cached_files": len(files), "files": files}
