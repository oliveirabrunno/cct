import asyncio
from dotenv import load_dotenv
load_dotenv()
from scrapers.match_stats import build_match_context
from generators.match_result_card import generate_match_result_card

async def main():
    ctx = build_match_context(
        winner="Luciano Darderi",
        loser="Alexander Zverev",
        score="6-4 3-6 6-0",
        tournament="Masters 1000 de Roma",
        round_name="2ª Rodada"
    )
    result = await generate_match_result_card(ctx)
    if result:
        print(f"Card gerado: {result['image_path']}")
        print(f"Caption: {result['caption']}")
    else:
        print("Erro ao gerar card")

if __name__ == "__main__":
    asyncio.run(main())
