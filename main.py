"""
Simple single agent demo with Lark integration.
"""

import asyncio
import os

# ENV
from dotenv import load_dotenv
load_dotenv()

# LOG
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CLAUDE
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

# LARK
from lark import LarkReceive, LarkStreamingReply

# PROMPT
SYSTEM_PROMPT = """You are a helpful assistant. Answer questions clearly and concisely."""

async def collect_response(client):
    """Yield response text chunks from Claude"""
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    yield f"{block.text}\n"
                elif isinstance(block, ToolUseBlock):
                    yield f"[{block.name} {block.input}]\n"
        elif isinstance(msg, ResultMessage):
            logger.info(f"Result: {msg.duration_ms}ms, ${msg.total_cost_usd or 0:.2f}")

async def user_message(content):
    yield {"type": "user", "message": {"role": "user", "content": content}}

async def lark_task(client, receive, reply):
    """Process Lark messages from queue"""
    while True:
        msg = receive.get()
        if msg:
            mid, content = msg
            await client.query(user_message(content))
            await reply.reply(mid, collect_response(client))
        else:
            await asyncio.sleep(0.1)


async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY not found.")
        return

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        system_prompt=SYSTEM_PROMPT,
        model="haiku",
        max_buffer_size=1024*1024*10,
        setting_sources=["user", "project"],
        allowed_tools=["Task", "Bash", "Glob", "Grep", "Read", "WebFetch", "WebSearch", "Skill", "TaskOutput", "TodoWrite"],
        disallowed_tools=["Edit", "Write", "NotebookEdit", "EnterPlanMode", "ExitPlanMode", "AskUserQuestion", "KillShell"],
    )

    async with ClaudeSDKClient(options=options) as client:
        asyncio.create_task(lark_task(client, LarkReceive(), LarkStreamingReply()))
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Goodbye!")