import hashlib
import json
import logging
import math
import litellm
from src.config import DATA_DIR, EMBEDDING_MODEL, EMBEDDING_API_KEY

logger = logging.getLogger(__name__)

CACHE_FILE = DATA_DIR / "embeddings_cache.json"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def get_embedding(text: str) -> list:
    response = litellm.embedding(
        model=EMBEDDING_MODEL,
        input=[text],
        api_key=EMBEDDING_API_KEY,
    )
    return response["data"][0]["embedding"]


def cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_cached_embedding(page_id: str, jd_text: str) -> list:
    """Return embedding from cache or compute and store it."""
    cache = _load_cache()
    key = f"{page_id}:{_md5(jd_text)}"
    if key in cache:
        logger.debug(f"Embedding cache hit for {page_id}")
        return cache[key]
    logger.info(f"Computing embedding for page {page_id}")
    embedding = get_embedding(jd_text)
    cache[key] = embedding
    _save_cache(cache)
    return embedding
