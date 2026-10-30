"""Neon Managed Auth — server-side session verification."""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "auth" / "config.public.json"


def auth_url() -> str:
    env = (os.environ.get("NEON_AUTH_URL") or "").strip().rstrip("/")
    if env:
        return env
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return str(cfg.get("authUrl", "")).rstrip("/")
    return ""


def verify_bearer_token(token: str) -> dict:
    base = auth_url()
    if not base or not token:
        raise HTTPException(401, "Neon Auth가 설정되지 않았습니다.")
    try:
        resp = requests.get(
            f"{base}/get-session",
            headers={"Authorization": f"Bearer {token}"},
            timeout=12,
        )
    except requests.RequestException as exc:
        raise HTTPException(502, "Neon Auth 연결 실패") from exc
    if resp.status_code != 200:
        raise HTTPException(401, "Neon Auth 세션이 유효하지 않습니다.")
    payload = resp.json()
    user = payload.get("user")
    if not user and isinstance(payload.get("session"), dict):
        user = payload["session"].get("user")
    if not user or not user.get("email"):
        raise HTTPException(401, "Neon Auth 사용자 정보를 확인할 수 없습니다.")
    return user
