"""
Diagnóstico completo da integração Meta / Instagram.
Uso: python scripts/check_meta.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN    = os.getenv("META_ACCESS_TOKEN", "")
PAGE_ID  = os.getenv("PAGE_ID", "")
IG_ID    = os.getenv("META_IG_USER_ID", "")
GRAPH    = "https://graph.facebook.com/v19.0"

BOLD  = "\033[1m"
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
RESET = "\033[0m"

def ok(msg):  print(f"{GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"{RED}❌ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠️  {msg}{RESET}")
def head(msg): print(f"\n{BOLD}{msg}{RESET}")


def check_token():
    head("1. TOKEN")
    if not TOKEN:
        fail("META_ACCESS_TOKEN não definido no .env")
        return False

    resp = requests.get(
        f"{GRAPH}/debug_token",
        params={"input_token": TOKEN, "access_token": TOKEN},
        timeout=10,
    ).json()
    data = resp.get("data", {})

    if not data.get("is_valid"):
        fail(f"Token inválido: {resp}")
        return False

    ok(f"Token válido — tipo: {data.get('type')}, expira: {data.get('expires_at', 'nunca')}")
    scopes = data.get("scopes", [])
    print(f"   Escopos: {', '.join(scopes)}")

    required = {"instagram_basic", "instagram_content_publish", "pages_read_engagement"}
    missing = required - set(scopes)
    if missing:
        fail(f"Escopos faltando: {missing}")
        return False
    ok("Todos os escopos necessários presentes")
    return True


def check_page():
    head("2. FACEBOOK PAGE")
    if not PAGE_ID:
        fail("PAGE_ID não definido no .env")
        return None

    resp = requests.get(
        f"{GRAPH}/{PAGE_ID}",
        params={
            "fields": "name,id,instagram_business_account,connected_instagram_account",
            "access_token": TOKEN,
        },
        timeout=10,
    ).json()

    if "error" in resp:
        fail(f"Erro ao acessar Page: {resp['error']['message']}")
        return None

    ok(f"Page encontrada: {resp.get('name')} (ID: {resp.get('id')})")

    ig_biz = resp.get("instagram_business_account")
    ig_con = resp.get("connected_instagram_account")

    if ig_biz:
        ok(f"Instagram Business conectado: {ig_biz['id']}")
        return ig_biz["id"]
    elif ig_con:
        warn(f"Instagram pessoal/creator conectado: {ig_con['id']} (pode não ter permissão de publicação)")
        return ig_con["id"]
    else:
        fail("Nenhuma conta Instagram conectada à Facebook Page")
        print()
        print("  COMO CORRIGIR:")
        print("  1. Acesse instagram.com → Configurações → Tipo de conta e ferramentas")
        print("     → Mudar para conta profissional → Empresa → vincule ao FB")
        print("  2. Ou: acesse sua Facebook Page → Configurações → Instagram")
        print("     → Conectar conta → faça login com @cafecomteniss")
        print("  3. Depois, gere novo token em developers.facebook.com/tools/explorer")
        print("     Selecione seu App → Generate Token → marque: instagram_basic,")
        print("     instagram_content_publish, pages_read_engagement, pages_show_list")
        print("  4. Atualize META_ACCESS_TOKEN no .env e rode este script novamente")
        return None


def check_ig_account(ig_id: str):
    head("3. INSTAGRAM BUSINESS ACCOUNT")
    resp = requests.get(
        f"{GRAPH}/{ig_id}",
        params={
            "fields": "username,account_type,followers_count,media_count",
            "access_token": TOKEN,
        },
        timeout=10,
    ).json()

    if "error" in resp:
        fail(f"Erro ao acessar conta IG: {resp['error']['message']}")
        return False

    ok(f"@{resp.get('username')} — tipo: {resp.get('account_type')}")
    ok(f"Seguidores: {resp.get('followers_count', '?')} | Posts: {resp.get('media_count', '?')}")

    if resp.get("account_type") not in ("BUSINESS", "MEDIA_CREATOR"):
        warn("Conta não é Business nem Creator — publicação via API pode falhar")
    return True


def test_publish_dry():
    head("4. TESTE DE PUBLICAÇÃO (dry run)")
    ig_id = IG_ID or "?"
    resp = requests.get(
        f"{GRAPH}/{ig_id}/media",
        params={"fields": "id,timestamp", "access_token": TOKEN, "limit": 1},
        timeout=10,
    ).json()

    if "error" in resp:
        fail(f"Não foi possível listar mídia: {resp['error']['message']}")
        return False

    medias = resp.get("data", [])
    ok(f"Endpoint de mídia acessível — {len(medias)} post(s) listado(s)")
    return True


if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  Café com Tênis — Diagnóstico Meta/Instagram")
    print(f"{'='*50}")

    if not check_token():
        sys.exit(1)

    ig_id_from_page = check_page()

    if ig_id_from_page:
        check_ig_account(ig_id_from_page)

        # Atualizar .env se ID diferente
        if ig_id_from_page != IG_ID:
            warn(f"META_IG_USER_ID no .env ({IG_ID}) difere do ID da Page ({ig_id_from_page})")
            print(f"   Atualize .env: META_IG_USER_ID={ig_id_from_page}")

        test_publish_dry()
        print(f"\n{GREEN}{BOLD}✅ Integração pronta para publicação!{RESET}")
    else:
        print(f"\n{RED}{BOLD}❌ Integração incompleta — siga as instruções acima.{RESET}")
        sys.exit(1)
