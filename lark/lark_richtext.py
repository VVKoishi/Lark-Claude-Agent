"""Lark RichText - Parse post messages to Claude format"""

from .lark_resource import LarkResource


class LarkRichText:
    """Parse Lark rich text (post) messages"""

    def __init__(self):
        self._resource = LarkResource()

    def parse(self, message_id: str, content: dict) -> list:
        """Parse rich text, return Claude format content array.
        Skips: at, media, emotion, hr"""
        claude_content = []
        texts = []

        title = content.get('title', '').strip()
        if title:
            texts.append(title)

        for line in content.get('content', []):
            line_texts = []
            for item in line:
                tag = item.get('tag')

                if tag == 'text':
                    line_texts.append(item.get('text', ''))

                elif tag == 'a':
                    line_texts.append(f"[{item.get('text', '')}]({item.get('href', '')})")

                elif tag == 'code_block':
                    line_texts.append(f"```{item.get('text', '')}```")

                elif tag == 'img':
                    if line_texts:
                        texts.append(''.join(line_texts))
                        line_texts = []
                    if texts:
                        claude_content.append({"type": "text", "text": '\n'.join(texts)})
                        texts = []

                    image_key = item.get('image_key')
                    if image_key:
                        source = self._resource.download_image_base64(message_id, image_key)
                        if source:
                            claude_content.append({"type": "image", "source": source})

            if line_texts:
                texts.append(''.join(line_texts))

        if texts:
            text = '\n'.join(texts).strip()
            if text:
                claude_content.append({"type": "text", "text": text})

        return claude_content
