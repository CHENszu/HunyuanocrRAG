from openai import AsyncOpenAI
from .config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL

class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=LLM_API_BASE,
            api_key=LLM_API_KEY,
        )

    async def get_answer_stream(self, query, context_chunks, history=None):
        if not context_chunks and not history:
             yield "我无法在提供的文档中找到任何相关信息。"
             return

        context_str = "\n\n".join([f"来源: {c['source']}\n内容: {c['text']}" for c in context_chunks])
        
        system_prompt = """你是一个智能文档助手，负责分析用户的个人文档。
请使用以下上下文信息来回答用户的问题。
要求：
1. 必须使用中文回答。
2. 如果答案不在上下文中，请明确说明你不知道。
3. 结合对话历史来理解用户的意图（例如“他的”指代上文提到的人）。
"""

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
                
        # Add current context and query
        user_content = f"""上下文信息:
{context_str}

用户问题: {query}
回答:"""
        messages.append({"role": "user", "content": user_content})
        
        try:
            stream = await self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.7,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"生成回答时出错: {e}"

    async def get_answer(self, query, context_chunks):
        if not context_chunks:
            return "I couldn't find any relevant information in the provided documents."
            
        context_str = "\n\n".join([f"Source: {c['source']}\nContent: {c['text']}" for c in context_chunks])
        
        prompt = f"""You are a helpful assistant analyzing personal documents. Use the following context to answer the user's question.
If the answer is not in the context, say you don't know.

Context:
{context_str}

Question: {query}
Answer:"""
        
        try:
            response = await self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating answer: {e}"
