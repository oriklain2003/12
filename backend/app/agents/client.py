"""Gemini client singleton — initialized once at lifespan startup."""

from google import genai
from app.config import settings

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Return the initialized Gemini client. Raises if not yet initialized."""
    if _client is None:
        raise RuntimeError(
            "Gemini client not initialized — call init_client() in lifespan"
        )
    return _client


async def init_client() -> None:
    """Initialize the Gemini client singleton from settings. Call once in lifespan."""
    global _client
    _client = genai.Client(api_key=settings.gemini_api_key)


async def close_client() -> None:
    """Close the Gemini client and release resources. Call in lifespan shutdown."""
    global _client
    if _client is not None:
        # aclose releases the internal aiohttp session
        try:
            await _client.aio.aclose()
        except Exception:
            pass  # Suppress known SDK cleanup warnings (googleapis/python-genai#834)
        _client = None
