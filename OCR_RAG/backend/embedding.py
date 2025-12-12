from openai import AsyncOpenAI
from .config import EMBED_API_BASE, EMBED_API_KEY, EMBED_MODEL

class EmbeddingClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=EMBED_API_BASE,
            api_key=EMBED_API_KEY,
        )

    async def get_embedding(self, text):
        if not text or not text.strip():
            return None
        text = text.replace("\n", " ")
        try:
            response = await self.client.embeddings.create(
                input=[text],
                model=EMBED_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None
