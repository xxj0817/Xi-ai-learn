"""头像文件存储：base64 输入 → 本地 static/avatars 目录。"""

from __future__ import annotations

import base64
import binascii
import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings
from app.core.exceptions import InvalidInput
from app.models.user import AvatarUploadRequest

logger = logging.getLogger(__name__)

AVATAR_SUBDIR = "avatars"
STATIC_PATH_PREFIX = f"/static/{AVATAR_SUBDIR}"

_CONTENT_TYPE_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}


def _detect_extension(raw: bytes) -> str | None:
    """按文件头判断真实格式，避免仅信任客户端声明的 content_type。"""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


class AvatarService:
    def __init__(self, settings: Settings, static_root: Path) -> None:
        self._settings = settings
        self._static_root = static_root

    def store(
        self, *, user_id: int, payload: AvatarUploadRequest, previous_url: str = ""
    ) -> str:
        """保存头像文件并返回可直接拼接域名的静态路径。"""
        declared = payload.content_type.strip().lower()
        if declared not in _CONTENT_TYPE_EXTENSIONS:
            raise InvalidInput("头像仅支持 PNG / JPEG / WebP 格式")

        try:
            raw = base64.b64decode(payload.data, validate=True)
        except (binascii.Error, ValueError, TypeError) as exc:
            raise InvalidInput("头像数据解析失败，请重新选择图片") from exc

        if not raw:
            raise InvalidInput("头像数据为空，请重新选择图片")
        if len(raw) > self._settings.avatar_max_bytes:
            limit_mb = self._settings.avatar_max_bytes / (1024 * 1024)
            raise InvalidInput(f"头像图片过大，请选择 {limit_mb:.0f}MB 以内的图片")

        extension = _detect_extension(raw)
        if extension is None:
            raise InvalidInput("头像内容不是有效的图片")

        directory = self._static_root / AVATAR_SUBDIR
        directory.mkdir(parents=True, exist_ok=True)

        filename = f"u{user_id}_{uuid.uuid4().hex[:12]}.{extension}"
        target = directory / filename
        target.write_bytes(raw)

        self._remove_previous(previous_url, keep=filename)
        return f"{STATIC_PATH_PREFIX}/{filename}"

    def _remove_previous(self, previous_url: str, *, keep: str) -> None:
        if not previous_url:
            return
        path = urlparse(previous_url).path
        if not path.startswith(f"{STATIC_PATH_PREFIX}/"):
            return
        name = path.rsplit("/", 1)[-1]
        if not name or name == keep or "/" in name or "\\" in name:
            return
        stale = self._static_root / AVATAR_SUBDIR / name
        try:
            if stale.is_file():
                stale.unlink()
        except OSError as exc:  # noqa: BLE001 - 清理失败不影响上传
            logger.warning("旧头像清理失败 file=%s error=%s", name, type(exc).__name__)
