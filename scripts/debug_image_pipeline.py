"""
Script de diagnóstico: rastreia cada etapa do pipeline de imagem.
Roda no GitHub Actions (ou localmente) e imprime um relatório detalhado.

Uso: python scripts/debug_image_pipeline.py
"""
import asyncio
import os
import sys
import json
import base64
import subprocess
from pathlib import Path

# Garantir que o projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def main():
    print("=" * 70)
    print("DIAGNÓSTICO DO PIPELINE DE IMAGEM — CAFÉ COM TÊNIS")
    print("=" * 70)

    # ── 1. Verificar variáveis de ambiente ──
    print("\n[1] VARIÁVEIS DE AMBIENTE")
    env_vars = {
        "SERPAPI_KEY": bool(os.getenv("SERPAPI_KEY")),
        "FLICKR_API_KEY": bool(os.getenv("FLICKR_API_KEY")),
        "IMGBB_API_KEY": bool(os.getenv("IMGBB_API_KEY")),
        "META_ACCESS_TOKEN": bool(os.getenv("META_ACCESS_TOKEN")),
        "META_IG_USER_ID": bool(os.getenv("META_IG_USER_ID")),
        "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
    }
    for k, v in env_vars.items():
        status = "✅ presente" if v else "❌ AUSENTE"
        print(f"    {k}: {status}")

    # ── 2. Verificar se o template post.html existe ──
    print("\n[2] TEMPLATES")
    post_html = Path("config/templates/post.html")
    print(f"    post.html existe: {post_html.exists()}")
    if post_html.exists():
        content = post_html.read_text()
        print(f"    post.html tamanho: {len(content)} bytes")
        has_json_block = 'id="post-data"' in content
        print(f"    post.html tem bloco JSON: {has_json_block}")

    # ── 3. Verificar Puppeteer/Node ──
    print("\n[3] NODE / PUPPETEER")
    try:
        node_ver = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        print(f"    Node: {node_ver.stdout.strip()}")
    except Exception as e:
        print(f"    ❌ Node não encontrado: {e}")

    try:
        result = subprocess.run(
            ["node", "-e", "try { require('puppeteer'); console.log('OK'); } catch(e) { console.log('FALHA: ' + e.message); }"],
            capture_output=True, text=True, timeout=10
        )
        print(f"    Puppeteer require: {result.stdout.strip()}")
    except Exception as e:
        print(f"    ❌ Puppeteer check falhou: {e}")

    # ── 4. Testar busca de imagem do Google Images ──
    print("\n[4] BUSCA DE IMAGEM (Google Images via SerpAPI)")
    try:
        from utils.image_sources.google_images import search_player_images, SERPAPI_KEY
        print(f"    SERPAPI_KEY carregada no módulo: {bool(SERPAPI_KEY)} (primeiros 8 chars: {SERPAPI_KEY[:8] if SERPAPI_KEY else 'N/A'})")
        
        photos = search_player_images("Novak Djokovic", count=2, tournament_name="Rome")
        print(f"    Resultados Google Images: {len(photos)}")
        if photos:
            print(f"    Primeira foto URL: {photos[0].get('url', '')[:80]}...")
        else:
            print(f"    ❌ NENHUMA FOTO encontrada via SerpAPI!")
    except Exception as e:
        print(f"    ❌ Erro na busca: {e}")

    # ── 5. Testar ImageManager completo ──
    print("\n[5] IMAGE MANAGER — get_player_image()")
    try:
        from utils.image_manager import ImageManager
        img_manager = ImageManager()
        img_data = await img_manager.get_player_image(
            "Novak Djokovic", image_type="any", tournament_name="Rome"
        )
        print(f"    Resultado: {img_data}")
        if img_data:
            path = img_data.get("path")
            print(f"    path: {path}")
            print(f"    source: {img_data.get('source')}")
            if path:
                exists = os.path.exists(path)
                print(f"    arquivo existe: {exists}")
                if exists:
                    size = os.path.getsize(path)
                    print(f"    tamanho: {size} bytes")
                    
                    # Testar base64
                    from generators.visual import _image_to_base64
                    b64 = _image_to_base64(path)
                    print(f"    base64 gerado: {bool(b64)} ({len(b64)} chars)")
                    print(f"    base64 começa com: {b64[:60]}")
            else:
                print(f"    ❌ path é None! Verifique _get_placeholder()")
        else:
            print(f"    ❌ img_data é None!")
    except Exception as e:
        import traceback
        print(f"    ❌ Erro: {e}")
        traceback.print_exc()

    # ── 6. Testar geração completa do post ──
    print("\n[6] GERAÇÃO COMPLETA DO POST (generate_post)")
    try:
        from generators.visual import generate_post

        post_data = {
            "surface": "clay",
            "badge": "DIAGNÓSTICO",
            "kicker": "Teste · Debug",
            "title": "TESTE DE IMAGEM",
            "subtitle": "Se este post tiver imagem, o pipeline funciona.",
            "player_image_query": "Novak Djokovic"
        }

        result_path = await generate_post("debug_test", {"tournament": "Rome"}, post_data)
        print(f"    Resultado: {result_path}")

        if result_path and os.path.exists(result_path):
            size = os.path.getsize(result_path)
            print(f"    PNG gerado: {size} bytes")
            
            # Verificar se o PNG é uma imagem real (não toda preta)
            # Verificar os primeiros bytes (PNG magic number)
            with open(result_path, "rb") as f:
                header = f.read(8)
                is_png = header[:4] == b'\x89PNG'
                print(f"    É PNG válido: {is_png}")
            
            # Fazer upload de teste ao imgbb para validar
            if os.getenv("IMGBB_API_KEY"):
                import requests
                with open(result_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                resp = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": os.getenv("IMGBB_API_KEY"), "image": img_b64},
                    timeout=30,
                )
                data = resp.json()
                if data.get("success"):
                    print(f"    ✅ Upload imgbb OK: {data['data']['url']}")
                else:
                    print(f"    ❌ Upload imgbb falhou: {data}")
        else:
            print(f"    ❌ PNG NÃO foi gerado!")
    except Exception as e:
        import traceback
        print(f"    ❌ Erro na geração: {e}")
        traceback.print_exc()

    # ── 7. Verificar o HTML intermediário ──
    print("\n[7] VERIFICAÇÃO DO HTML INTERMEDIÁRIO")
    try:
        import re
        from generators.visual import _image_to_base64
        from utils.image_manager import ImageManager

        img_manager2 = ImageManager()
        img_data2 = await img_manager2.get_player_image("Novak Djokovic", image_type="any")

        test_post = {
            "surface": "clay",
            "badge": "TEST",
            "kicker": "Test",
            "title": "Test",
            "subtitle": "Test",
            "image": "",
            "credit": ""
        }

        if img_data2 and img_data2.get("path") and os.path.exists(img_data2["path"]):
            test_post["image"] = _image_to_base64(img_data2["path"])
            test_post["credit"] = img_data2.get("credit_text", "")

        json_str = json.dumps(test_post, ensure_ascii=False)
        
        # O campo image tem conteúdo?
        image_val = test_post["image"]
        if image_val.startswith("data:image"):
            print(f"    ✅ Campo 'image' tem base64 ({len(image_val)} chars)")
        elif image_val.startswith("file://"):
            print(f"    ⚠️  Campo 'image' tem file:// URI: {image_val[:80]}")
        elif image_val == "":
            print(f"    ❌ Campo 'image' está VAZIO!")
        else:
            print(f"    ❓ Campo 'image' tem valor inesperado: {image_val[:80]}")

        # Verificar se o JSON cabe no HTML sem corromper
        html_content = post_html.read_text(encoding="utf-8")
        html_new = re.sub(
            r'<script id="post-data" type="application/json">.*?</script>',
            f'<script id="post-data" type="application/json">\n{json_str}\n</script>',
            html_content,
            flags=re.DOTALL
        )
        if json_str in html_new:
            print(f"    ✅ JSON injetado corretamente no HTML")
        else:
            print(f"    ❌ JSON NÃO encontrado no HTML após injeção!")

    except Exception as e:
        import traceback
        print(f"    ❌ Erro: {e}")
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("FIM DO DIAGNÓSTICO")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
