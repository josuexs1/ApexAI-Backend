import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings

class OllamaCloudClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_CLOUD_HOST
        self.headers = {
            "Authorization": f"Bearer {settings.OLLAMA_API_KEY}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=settings.HTTPX_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )

    async def close(self):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def chat(self, messages: list, tools: list = None, think: bool = False):
        payload = {
            "model": settings.DEFAULT_MODEL,
            "messages": messages,
            "stream": False,
            "think": think
        }
        if tools:
            payload["tools"] = tools

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def web_search(self, query: str, max_results: int = 5):
        payload = {"query": query, "max_results": max_results}
        response = await self.client.post("/api/web_search", json=payload)
        response.raise_for_status()
        return response.json()

ollama_client = OllamaCloudClient()