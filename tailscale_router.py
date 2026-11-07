import asyncio
import json
import time
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/tailscale", tags=["tailscale"])

# キャッシュ変数（CLI過密実行防止）
_STATUS_CACHE: Dict[str, Any] = {}
_LAST_FETCH_TIME: float = 0.0
CACHE_TTL_SEC: float = 3.0


@router.get("/status")
async def get_tailscale_status():
    global _STATUS_CACHE, _LAST_FETCH_TIME

    now = time.time()
    if _STATUS_CACHE and (now - _LAST_FETCH_TIME) < CACHE_TTL_SEC:
        return _STATUS_CACHE

    try:
        proc = await asyncio.create_subprocess_exec(
            "tailscale",
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"Tailscale error: {stderr.decode()}"
            )

        raw_data = json.loads(stdout.decode())

        # 自ノード情報の抽出
        self_node = raw_data.get("Self", {})
        self_ip = self_node.get("TailscaleIPs", [""])[0]
        self_name = self_node.get("HostName", "k2-server")
        exit_node_active = raw_data.get("ExitNodeStatus") is not None

        # ピア一覧の整形
        peers = []
        for _, peer in raw_data.get("Peer", {}).items():
            cur_addr = peer.get("CurAddr", "")
            relay = peer.get("Relay", "")

            # 接続方式の判定: CurAddrがあればDirect P2P、無くてRelayがあればDERP中継
            connection_type = "Offline"
            if peer.get("Active", False) or cur_addr:
                connection_type = "Direct (P2P)" if cur_addr else f"DERP ({relay})"

            peers.append(
                {
                    "hostname": peer.get("HostName", "Unknown"),
                    "ip": peer.get("TailscaleIPs", [""])[0],
                    "os": peer.get("OS", "Unknown"),
                    "active": peer.get("Active", False),
                    "connection": connection_type,
                    "cur_addr": cur_addr,
                    "rx_bytes": peer.get("RxBytes", 0),
                    "tx_bytes": peer.get("TxBytes", 0),
                    "last_handshake": peer.get("LastHandshake", ""),
                }
            )

        payload = {
            "status": "online" if self_node.get("Online", False) else "offline",
            "node_name": self_name,
            "ip": self_ip,
            "exit_node": exit_node_active,
            "health": raw_data.get("Health", []),
            "peer_count": len(peers),
            "peers": peers,
            "updated_at": int(now),
        }

        _STATUS_CACHE = payload
        _LAST_FETCH_TIME = now
        return payload

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Tailscale command timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
