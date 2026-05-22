import os
import json
import anthropic
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

PROMPTS_DIR = Path("config/prompts")
MODEL = "claude-opus-4-7"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY não definida no .env")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    log.warning(f"Prompt '{name}' não encontrado em {path}")
    return ""


class ContentGenerator:

    def generate_caption(self, post_type: str, data: dict) -> str:
        system = _load_prompt("base_voice") or (
            "Você é o Café com Tênis (@cafecomteniss), canal de tênis brasileiro. "
            "Tom: direto, apaixonado, informativo. Sem enrolação. "
            "Escreve em português do Brasil."
        )
        prompt = _load_prompt("caption") or (
            f"Gere uma legenda para Instagram sobre {post_type}.\n"
            f"Dados: {json.dumps(data, ensure_ascii=False)}\n"
            "Máximo 150 palavras. Inclua 3-5 hashtags relevantes ao final."
        )
        prompt = prompt.replace("{post_type}", post_type)
        prompt = prompt.replace("{data}", json.dumps(data, ensure_ascii=False, indent=2))

        return self._call_claude(system, prompt)

    def generate_carousel_slides(self, post_type: str, data: dict) -> dict:
        system = (
            (_load_prompt("viral_master_prompt") + "\n\n" + _load_prompt("base_voice"))
            if _load_prompt("viral_master_prompt") and _load_prompt("base_voice")
            else _load_prompt("viral_master_prompt")
            or _load_prompt("base_voice")
            or "Você é o Café com Tênis (@cafecomteniss). "
               "Crie conteúdo de alta retenção para Instagram, modelo @ri.cred."
        )
        prompt_template = _load_prompt(post_type) or _load_prompt("carousel") or (
            "Crie um carrossel de slides sobre {player_name}.\n"
            "Dados: {data}\n\n"
            "OUTPUT JSON:\n"
            '{"surface": "clay", "badge": "Conteúdo", "credit": "📸", '
            '"slides": [{"kind": "cover", "kicker": "", "title": "", "subtitle": "", "player_image_query": "{player_name}"}], '
            '"caption": "Legenda do post", "hashtags": []}\n'
            'Nota: "kind" pode ser: "cover", "text", "stat", "image", "quote", "outro".'
        )

        prompt = prompt_template
        for k, v in data.items():
            prompt = prompt.replace(f"{{{k}}}", str(v))
        prompt = prompt.replace("{data}", json.dumps(data, ensure_ascii=False, indent=2))

        raw = self._call_claude(system, prompt)
        return self._parse_json_response(raw)

    def generate_story_text(self, post_data: dict) -> str:
        system = (
            "Você é o Café com Tênis. Gere texto ultra-curto para story Instagram. "
            "Máximo 3 linhas, 28 caracteres por linha."
        )
        prompt = _load_prompt("story_teaser") or (
            f"Dados do post: {json.dumps(post_data, ensure_ascii=False)}\n"
            "Retorne apenas o texto final, sem explicações."
        )
        prompt = prompt.replace("{post_data}", json.dumps(post_data, ensure_ascii=False))
        return self._call_claude(system, prompt)

    def generate_with_claude_raw(self, prompt: str, max_tokens: int = 8192) -> str:
        return self._call_claude("", prompt, max_tokens=max_tokens)

    def _call_claude(self, system: str, prompt: str, max_tokens: int = 4096) -> str:
        client = _get_client()
        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            resp = client.messages.create(**kwargs)
            return resp.content[0].text
        except Exception as e:
            log.error(f"Claude API erro: {e}")
            return ""

    def _parse_json_response(self, raw: str) -> dict:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError as e:
            log.error(f"JSON parse falhou: {e}\nRaw: {raw[:200]}")
        return {}
