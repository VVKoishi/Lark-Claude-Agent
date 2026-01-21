"""Lark Streaming Reply - Reply with streaming card"""

import json
import logging
import os
import uuid

import lark_oapi as lark
from lark_oapi.api.cardkit.v1 import (
    CreateCardRequest, CreateCardRequestBody,
    SettingsCardRequest, SettingsCardRequestBody,
    ContentCardElementRequest, ContentCardElementRequestBody
)
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

logger = logging.getLogger(__name__)

# Streaming configuration constants
STREAMING_CONFIG = {
    "print_frequency_ms": {"default": 30, "android": 30, "ios": 30, "pc": 30},
    "print_step": {"default": 1, "android": 1, "ios": 1, "pc": 1},
    "print_strategy": "fast"
}


class LarkStreamingReply:
    """Reply with streaming card to Lark messages"""

    def __init__(self):
        app_id = os.environ.get('LARK_APP_ID')
        app_secret = os.environ.get('LARK_APP_SECRET')
        if not app_id or not app_secret:
            raise ValueError("LARK_APP_ID or LARK_APP_SECRET not set")

        self._client = lark.Client.builder() \
            .app_id(app_id).app_secret(app_secret).build()

    def _create_card(self) -> str | None:
        """Create a streaming card and return card_id"""
        card_data = {
            "schema": "2.0",
            "body": {"elements": [{"tag": "markdown", "element_id": "markdown_1", "content": ""}]}
        }
        request = CreateCardRequest.builder() \
            .request_body(CreateCardRequestBody.builder()
                .type("card_json").data(json.dumps(card_data)).build()).build()
        
        response = self._client.cardkit.v1.card.create(request)
        if not response.success():
            logger.error(f"Create card failed: {response.code}, {response.msg}")
            return None
        return response.data.card_id

    def _set_streaming_mode(self, card_id: str, enabled: bool, seq: int) -> bool:
        """Set streaming mode for the card"""
        config = {"streaming_mode": enabled}
        if enabled:
            config["streaming_config"] = STREAMING_CONFIG
        
        request = SettingsCardRequest.builder().card_id(card_id) \
            .request_body(SettingsCardRequestBody.builder()
                .settings(json.dumps({"config": config}))
                .uuid(str(uuid.uuid4())).sequence(seq).build()).build()
        
        response = self._client.cardkit.v1.card.settings(request)
        if not response.success():
            logger.error(f"Set streaming mode failed: {response.code}, {response.msg}")
            return False
        return True

    def _update_content(self, card_id: str, text: str, seq: int) -> bool:
        """Update card element content with streaming effect"""
        request = ContentCardElementRequest.builder() \
            .card_id(card_id).element_id("markdown_1") \
            .request_body(ContentCardElementRequestBody.builder()
                .uuid(str(uuid.uuid4())).content(text).sequence(seq).build()).build()
        
        response = self._client.cardkit.v1.card_element.content(request)
        if not response.success():
            logger.error(f"Update content failed: {response.code}, {response.msg}")
            return False
        return True

    async def reply(self, message_id: str, chunks) -> bool:
        """Reply to a message with streaming card
        
        Args:
            message_id: The message id to reply to
            chunks: Async generator yielding text chunks
        """
        # Step 1: Create card
        card_id = self._create_card()
        if not card_id:
            return False

        # Step 2: Reply with card message
        content = json.dumps({"type": "card", "data": {"card_id": card_id}})
        request = ReplyMessageRequest.builder().message_id(message_id) \
            .request_body(ReplyMessageRequestBody.builder()
                .content(content).msg_type("interactive").build()).build()
        
        response = self._client.im.v1.message.reply(request)
        if not response.success():
            logger.error(f"Reply card failed: {response.code}, {response.msg}")
            return False

        # Step 3-5: Streaming update
        text = ""
        seq = 1

        if not self._set_streaming_mode(card_id, True, seq):
            return False
        seq += 1

        async for chunk in chunks:
            text += chunk
            self._update_content(card_id, text, seq)
            seq += 1

        if not self._set_streaming_mode(card_id, False, seq):
            return False

        return True
