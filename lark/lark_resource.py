"""Lark Resource - Download images and files"""

import base64
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import GetMessageResourceRequest

logger = logging.getLogger(__name__)

# Temp directory for downloaded files
TEMP_DIR = Path(__file__).parent / "temp"


class LarkResource:
    """Download Lark message resources (images, files)"""

    def __init__(self):
        app_id = os.environ.get('LARK_APP_ID')
        app_secret = os.environ.get('LARK_APP_SECRET')

        if not app_id or not app_secret:
            raise ValueError("LARK_APP_ID or LARK_APP_SECRET not set")

        self._client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

    def download(self, message_id: str, file_key: str, type: str) -> tuple[bytes, str] | None:
        """Download resource, return (bytes, filename). type: 'image' or 'file'"""
        try:
            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(file_key) \
                .type(type) \
                .build()

            response = self._client.im.v1.message_resource.get(request)

            if not response.success():
                logger.error(f"Download failed: {response.code} {response.msg}")
                return None

            return response.file.read(), response.file_name or ""
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

    def _get_media_type(self, filename: str) -> str:
        """Get media type from filename"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
        }.get(ext, 'image/png')

    def download_image_base64(self, message_id: str, image_key: str) -> dict | None:
        """Download image and return as base64 dict"""
        result = self.download(message_id, image_key, "image")
        if not result:
            return None

        data, filename = result
        return {
            "type": "base64",
            "media_type": self._get_media_type(filename),
            "data": base64.b64encode(data).decode()
        }

    def _cleanup_old_temp(self, days: int = 7) -> None:
        """Delete temp folders older than specified days"""
        if not TEMP_DIR.exists():
            return

        cutoff = datetime.now() - timedelta(days=days)
        for folder in TEMP_DIR.iterdir():
            if folder.is_dir():
                try:
                    # Parse folder name as date (YYYYMMDD)
                    folder_date = datetime.strptime(folder.name, "%Y%m%d")
                    if folder_date < cutoff:
                        shutil.rmtree(folder)
                        logger.info(f"Deleted old temp folder: {folder}")
                except ValueError:
                    pass  # Skip folders with invalid date names

    def download_file(self, message_id: str, file_key: str, filename: str = "") -> str | None:
        """Download file to temp folder and return absolute path"""
        # Cleanup old folders first
        self._cleanup_old_temp()

        result = self.download(message_id, file_key, "file")
        if not result:
            return None

        data, original_name = result
        filename = filename or original_name or file_key

        # Create date-based folder
        date_folder = TEMP_DIR / datetime.now().strftime("%Y%m%d")
        date_folder.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = date_folder / filename
        file_path.write_bytes(data)

        return str(file_path.absolute())
