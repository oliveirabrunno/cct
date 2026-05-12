import asyncio
import aiohttp

async def test():
    url = "https://www.tennismajors.com/app/uploads/2026/05/Darderi_Rome_2026-1296x675.jpg"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            print(resp.status)
            print(resp.headers.get("Content-Type"))
            content = await resp.read()
            print("Bytes:", len(content))

asyncio.run(test())
