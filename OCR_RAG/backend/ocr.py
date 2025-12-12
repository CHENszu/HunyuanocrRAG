import base64
import json
from openai import AsyncOpenAI
from .config import OCR_API_BASE, OCR_API_KEY, OCR_MODEL

class OCRClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=OCR_API_BASE,
            api_key=OCR_API_KEY,
        )

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def get_text(self, image_path, prompt="Extract all text from this image. Output ONLY the extracted text. If there is no text, output nothing."):
        try:
            base64_img = self.encode_image(image_path)
            response = await self.client.chat.completions.create(
                model=OCR_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
                            {"type": "text", "text": prompt}
                        ]
                    }
                ],
                temperature=0.0,
                top_p=0.95,
                max_tokens=4096
            )
            content = response.choices[0].message.content.strip()
            
            # Clean markdown if present
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            content = content.strip()
            
            # Check for common "failure to find text" responses from VLM
            # These are known hallucinated "I can't see" messages
            failure_patterns = [
                "text is not visible",
                "cannot identify text",
                "no text found",
                "识别不出文字",
                "无法识别",
                "看不清文字",
                "unable to extract",
                "image contains no",
                "text is too small"
            ]
            
            # Case insensitive check
            content_lower = content.lower()
            for pattern in failure_patterns:
                if pattern in content_lower:
                    # If the content is VERY short (just the error message), discard it.
                    # If it's long, it might be a document that happens to have that phrase (unlikely but possible).
                    # Usually VLM failure messages are short sentences.
                    if len(content) < 100: 
                        print(f"Filtered failure message for {image_path}: {content}")
                        return ""

            # Parse JSON to extract just text
            try:
                data = json.loads(content)
                items = data if isinstance(data, list) else data.get("data", [])
                full_text = "\n".join([item.get("text", "") for item in items])
                return full_text if full_text else content # Fallback if empty
            except json.JSONDecodeError:
                return content # Return raw if not JSON
        except Exception as e:
            print(f"OCR Error for {image_path}: {e}")
            return ""
