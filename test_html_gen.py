import asyncio
from generators.visual import generate_post

async def test():
    data = {"tournament": "Rome"}
    post_data = {
        "title": "Test Title",
        "player_image_query": "Luciano Darderi"
    }
    path = await generate_post("match_result", data, post_data)
    print("Generated path:", path)
    
asyncio.run(test())
