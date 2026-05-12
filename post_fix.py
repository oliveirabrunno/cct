import asyncio
from dotenv import load_dotenv
load_dotenv()
from generators.carousel import generate_trend_carousel
from publisher.graph_publisher import GraphPublisher
from utils.dedup import register_post

async def main():
    print("Gerando carrossel...")
    
    # Contexto específico para forçar o post desejado
    news = [{"title": "João Fonseca é cabeça de chave em Roland Garros", "summary": "Brasileiro entra como cabeça de chave no Grand Slam francês após grande temporada."}]
    signals = {"news_count": 1, "test": False}
    
    result = await generate_trend_carousel("João Fonseca", signals, news)
    
    if result and result.get("image_paths"):
        pub = GraphPublisher()
        print("Publicando no Instagram...")
        ok = await pub.publish_carousel(
            result["image_paths"], 
            result["caption"], 
            result["hashtags"]
        )
        if ok:
            register_post("trend_carousel", "João Fonseca", description=result["caption"][:100])
            print("Post publicado com sucesso!")
        else:
            print("Falha ao publicar.")
    else:
        print("Falha ao gerar carrossel.")

if __name__ == "__main__":
    asyncio.run(main())
