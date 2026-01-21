"""Lark Reply - Reply to messages"""

import json
import logging
import os

import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

logger = logging.getLogger(__name__)


class LarkReply:
    """Reply to Lark messages"""

    def __init__(self):
        app_id = os.environ.get('LARK_APP_ID')
        app_secret = os.environ.get('LARK_APP_SECRET')

        if not app_id or not app_secret:
            raise ValueError("LARK_APP_ID or LARK_APP_SECRET not set")

        self._client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

    def reply(self, message_id: str, text: str) -> bool:
        """Reply to a message with markdown text"""
        try:
            content = json.dumps({
                "zh_cn": {
                    "content": [[{"tag": "md", "text": text}]]
                }
            }, ensure_ascii=False)

            request = ReplyMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(ReplyMessageRequestBody.builder()
                    .content(content)
                    .msg_type("post")
                    .build()) \
                .build()

            return self._client.im.v1.message.reply(request).success()
        except Exception as e:
            logger.error(f"Reply failed: {e}")
            return False
