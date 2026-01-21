# Lark Module

Feishu (Lark) messaging integration for receiving and replying to messages.

## Structure

```
lark/
├── lark_receive.py          # WebSocket message listener
├── lark_reply.py            # Message reply API
├── lark_streaming_reply.py  # Streaming card reply API
├── lark_resource.py         # Image/file download (internal)
└── lark_richtext.py         # Rich text parsing (internal)
```

## Environment Variables

```env
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=xxx
LARK_OPEN_ID=ou_xxx  # Optional, for @mention filtering in group chats
```

## Usage

### 1. Receive Messages

```python
from lark import LarkReceive

receive = LarkReceive()  # Auto starts listening

# Poll for messages
msg = receive.get()  # Returns (message_id, content) or None
```

### 2. Receive and Reply

```python
import json
from lark import LarkReceive, LarkReply

receive = LarkReceive()
reply = LarkReply()

while True:
    msg = receive.get()
    if msg:
        message_id, content = msg
        reply.reply(message_id, json.dumps(content, ensure_ascii=False))
```

### 3. Streaming Reply with Claude SDK

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock
from lark import LarkReceive, LarkStreamingReply

async def main():
    receive = LarkReceive()
    reply = LarkStreamingReply()

    async with ClaudeSDKClient(ClaudeAgentOptions(permission_mode="bypassPermissions")) as client:
        while True:
            msg = receive.get()
            if msg:
                mid, content = msg

                async def make_message():
                    yield {"type": "user", "message": {"role": "user", "content": content}}

                async def collect_response():
                    async for msg in client.receive_response():
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    yield block.text

                await client.query(make_message())
                await reply.reply(mid, collect_response())
            await asyncio.sleep(0.1)

asyncio.run(main())
```

## Content Format

`receive.get()` returns `(message_id, content)` where `content` is a list of blocks:

```python
# Text message
[{"type": "text", "text": "Hello"}]

# Image message
[{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}]

# Rich text with image
[
    {"type": "text", "text": "Check this:"},
    {"type": "image", "source": {...}},
    {"type": "text", "text": "What do you think?"}
]

# File (text content only)
[{"type": "text", "text": "[File: example.txt]content here..."}]
```
