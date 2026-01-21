"""
Lark Receive - Feishu message reception
"""

import json
import logging
import os
import queue
import threading

import lark_oapi as lark
from lark_oapi.api.im.v1 import GetMessageRequest

from .lark_resource import LarkResource
from .lark_richtext import LarkRichText

logger = logging.getLogger(__name__)


class LarkReceive:
    """Feishu message receiver, starts listening on init"""

    def __init__(self):
        app_id = os.environ.get('LARK_APP_ID')
        app_secret = os.environ.get('LARK_APP_SECRET')
        if not app_id or not app_secret:
            raise ValueError("LARK_APP_ID or LARK_APP_SECRET not set")

        self._open_id = os.environ.get('LARK_OPEN_ID')
        self._queue = queue.Queue()
        self._resource = LarkResource()
        self._richtext = LarkRichText()
        self._client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

        # Start WebSocket listener
        handler = lark.EventDispatcherHandler.builder(app_id, app_secret) \
            .register_p2_im_message_receive_v1(self._on_message) \
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(lambda _: None) \
            .build()
        ws = lark.ws.Client(app_id, app_secret, event_handler=handler, log_level=lark.LogLevel.ERROR)
        threading.Thread(target=ws.start, daemon=True).start()

    def _get_message(self, message_id: str) -> tuple[str, dict] | None:
        """Get message by id, return (msg_type, content_data) or None"""
        try:
            req = GetMessageRequest.builder().message_id(message_id).build()
            res = self._client.im.v1.message.get(req)
            if res.success() and res.data.items:
                item = res.data.items[0]
                content = json.loads(item.body.content) if item.body else {}
                return item.msg_type, content
        except Exception as e:
            logger.error(f"Get message failed: {e}")
        return None

    def _on_message(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """WebSocket message callback"""
        if not (data and data.event and (msg := data.event.message)):
            return

        # Check @mention for group chats
        if self._open_id and msg.chat_type != 'p2p':
            if not any(m.id and m.id.open_id == self._open_id for m in (msg.mentions or [])):
                return

        # Parse message content
        content_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
        content = self._parse_content(msg.message_id, msg.message_type, content_data)

        # Prepend parent content if replying
        if (pid := msg.parent_id) and (parent := self._get_message(pid)):
            parent_content = self._parse_content(pid, parent[0], parent[1])
            content = parent_content + content

        if not content:
            return

        # Log and queue
        logger.info(f"{msg.message_id} {msg.message_type} {content[0].get('text', '[image]')[:100]}")
        self._queue.put((msg.message_id, content))

    def _parse_content(self, message_id: str, message_type: str, data: dict) -> list:
        """Parse message content to Claude format, fallback to raw data on failure"""
        match message_type:
            case 'text':
                if text := data.get('text', '').strip():
                    return [{"type": "text", "text": text}]

            case 'post':
                if result := self._richtext.parse(message_id, data):
                    return result

            case 'image':
                if key := data.get('image_key'):
                    if src := self._resource.download_image_base64(message_id, key):
                        return [{"type": "image", "source": src}]

            case 'file':
                if key := data.get('file_key'):
                    name = data.get('file_name', '')
                    if path := self._resource.download_file(message_id, key, name):
                        return [{"type": "text", "text": f"[File: {name}, Path: {path}]"}]

        return [{"type": "text", "text": f"[{message_type}] {data}"}]

    def get(self) -> tuple[str, list] | None:
        """Get message from queue, returns (message_id, content) or None"""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None
