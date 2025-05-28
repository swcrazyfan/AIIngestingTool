# Concurrency limits are now set via the startup script (start_prefect_all.sh), not in code.

"""
Utility to ensure Prefect concurrency limits are set at runtime.
Reads defaults from settings.py.
"""
import asyncio
from prefect.client.orchestration import get_client
from video_ingest_tool.config.settings import DEFAULT_CONCURRENCY_LIMITS

async def ensure_concurrency_limit(tag: str, limit: int):
    async with get_client() as client:
        existing = await client.read_concurrency_limits()
        if any(cl.tag == tag for cl in existing):
            return
        try:
            await client.create_concurrency_limit(tag=tag, concurrency_limit=limit)
        except Exception as e:
            # Ignore if already exists, log others
            if "already exists" not in str(e):
                print(f"Error creating concurrency limit for {tag}: {e}")

def setup_concurrency_limits():
    """
    Ensure all concurrency limits in DEFAULT_CONCURRENCY_LIMITS are set.
    """
    for tag, limit in DEFAULT_CONCURRENCY_LIMITS.items():
        asyncio.run(ensure_concurrency_limit(tag, limit)) 