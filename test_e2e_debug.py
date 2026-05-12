"""
Teste E2E: simula exatamente o que run_live_monitor faz.
Gera o card e inspeciona o HTML intermediário para ver se a imagem está lá.
"""
import asyncio, json, time, re, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from generators.visual import generate_post, _image_to_base64
from utils.image_manager import ImageManager

async def main():
    img_manager = ImageManager()
    
    # Simula o match_context
    match_context = {
        "winner": "Luciano Darderi",
        "loser": "Alexander Zverev", 
        "tournament": "Rome",
        "round": "R32",
        "score": "6-3 3-6 6-0",
    }
    
    post_data = {
        "surface": "clay",
        "badge": "RESULTADO",
        "kicker": "Roma · R32",
        "title": "DARDERI VENCE",
        "subtitle": "6-3 3-6 6-0 · Eliminação de Zverev",
        "player_image_query": "Luciano Darderi"
    }
    
    # === PASSO 1: Buscar imagem (como generate_post faz) ===
    player_query = post_data.get("player_image_query")
    print(f"\n[1] Buscando imagem para: {player_query}")
    
    img_data = await img_manager.get_player_image(
        player_query,
        image_type="any",
        tournament_name=match_context.get("tournament", "")
    )
    
    print(f"[2] img_data retornado: {img_data}")
    
    if img_data and img_data.get("path"):
        local_path = img_data["path"]
        print(f"[3] Caminho da imagem: {local_path}")
        print(f"[4] Arquivo existe? {os.path.exists(local_path)}")
        
        if os.path.exists(local_path):
            file_size = os.path.getsize(local_path)
            print(f"[5] Tamanho do arquivo: {file_size} bytes")
            
            # Testar base64
            b64 = _image_to_base64(local_path)
            print(f"[6] Base64 gerado? {bool(b64)}")
            print(f"[7] Primeiros 80 chars do base64: {b64[:80]}")
            print(f"[8] Tamanho total do base64: {len(b64)} chars")
    else:
        print("[3] ❌ NENHUMA IMAGEM RETORNADA! path é None ou vazio")
        print(f"    img_data completo: {img_data}")
    
    # === PASSO 2: Gerar o post e inspecionar o HTML ===
    print(f"\n[9] Gerando post completo via generate_post()...")
    result_path = await generate_post("match_result", match_context, post_data)
    print(f"[10] Resultado: {result_path}")
    
    if result_path and os.path.exists(result_path):
        png_size = os.path.getsize(result_path)
        print(f"[11] PNG gerado: {png_size} bytes")
    
    # === PASSO 3: Verificar se o HTML intermediário tinha a imagem ===
    # Regerar o HTML sem deletar
    post_data2 = dict(post_data)
    if img_data and img_data.get("path"):
        post_data2["image"] = _image_to_base64(img_data["path"])
    
    html_content = Path("config/templates/post.html").read_text(encoding="utf-8")
    json_str = json.dumps(post_data2, ensure_ascii=False)
    html_content = re.sub(
        r'<script id="post-data" type="application/json">.*?</script>',
        f'<script id="post-data" type="application/json">\n{json_str}\n</script>',
        html_content,
        flags=re.DOTALL
    )
    
    # Procura pela tag image no JSON injetado
    if "data:image" in html_content:
        print(f"\n[12] ✅ HTML contém imagem base64 embutida!")
    elif "file://" in html_content:
        print(f"\n[12] ⚠️  HTML contém file:// URI (pode falhar no Actions)")
    elif '"image": ""' in html_content or '"image":""' in html_content:
        print(f"\n[12] ❌ HTML tem image vazio! A imagem NÃO foi injetada")
    else:
        # Procura o valor do campo image
        img_match = re.search(r'"image"\s*:\s*"([^"]{0,100})', json_str)
        if img_match:
            print(f"\n[12] Campo image no JSON: '{img_match.group(1)}...'")
        else:
            print(f"\n[12] ❌ Campo 'image' não encontrado no JSON!")

asyncio.run(main())
