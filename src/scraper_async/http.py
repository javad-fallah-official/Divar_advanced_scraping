import asyncio
import aiohttp

_session = None
_sem = None


async def init_client(concurrency: int = 20, timeout: float = 10.0, headers: dict | None = None):
    global _session, _sem
    _sem = asyncio.Semaphore(concurrency)
    t = aiohttp.ClientTimeout(total=timeout)
    conn = aiohttp.TCPConnector(limit=concurrency, force_close=False, enable_cleanup_closed=True)
    default_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://divar.ir/",
    }
    merged = default_headers | (headers or {})
    _session = aiohttp.ClientSession(timeout=t, connector=conn, headers=merged)
    return _session


async def close_client():
    global _session
    if _session:
        await _session.close()
        _session = None


async def fetch_text(url: str, method: str = "GET", json: dict | None = None, headers: dict | None = None, retries: int = 2) -> str | None:
    async with _sem:
        for i in range(retries + 1):
            try:
                if method == "POST":
                    async with _session.post(url, json=json, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        return await resp.text()
                else:
                    async with _session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        return await resp.text()
            except Exception:
                continue
    return None
