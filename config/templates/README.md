# Café com Tênis — Templates para Instagram

Templates HTML para gerar **posts, stories e carrosséis** da `@cafecomteniss`. Layout único: **Editorial** (foto + filete colorido na cor da quadra + serif). Edite um JSON, abra no browser → tem a imagem pronta.

---

## Arquivos

| Arquivo                          | Formato     | Para que serve                              |
| -------------------------------- | ----------- | ------------------------------------------- |
| `post.html`                      | 1080 × 1080 | Post de feed (1 imagem)                     |
| `story.html`                     | 1080 × 1920 | Story / capa de Reel                        |
| `carousel.html`                  | 1080 × 1350 | Carrossel (capa + N slides + CTA)           |
| `data.example.json`              | —           | Exemplos de payload                         |
| `README.md`                      | —           | Este arquivo                                |

---

## Como o Claude Code usa

### Para um POST simples
1. Abra `post.html`.
2. Edite o bloco `<script id="post-data" type="application/json">` no topo do arquivo.
3. Capture com puppeteer:
   ```js
   await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });
   await page.goto('file:///abs/path/post.html');
   await page.waitForNetworkIdle();
   await page.screenshot({ path: 'post.png', clip: { x:0, y:0, width:1080, height:1080 } });
   ```

### Para um STORY
Igual ao post, com `story.html` e viewport `1080 × 1920`. Áreas seguras do Instagram (~250px topo/rodapé) já estão preservadas no layout.

### Para um CARROSSEL
1. Abra `carousel.html`.
2. Edite o JSON em `<script id="carousel-data">`. Cada item de `slides` vira um cartão 1080×1350.
3. Cada slide tem `data-slide-index="N"`. Capture cada um:
   ```js
   await page.setViewport({ width: 1080, height: 4000, deviceScaleFactor: 2 });
   await page.goto('file:///abs/path/carousel.html');
   await page.waitForNetworkIdle();
   const slides = await page.$$('[data-slide-index]');
   for (let i = 0; i < slides.length; i++) {
     await slides[i].screenshot({ path: `slide-${String(i+1).padStart(2,'0')}.png` });
   }
   ```

---

## Schema dos dados

### Post / Story
```jsonc
{
  "surface":  "clay",                           // "hard" | "grass" | "clay" | "neutral"
  "badge":    "Insight",                        // categoria — string curta
  "kicker":   "Roland Garros · Estatística",    // contexto (torneio/rodada). "" para esconder
  "title":    "Alcaraz tem o melhor saque...",  // título principal — vai em serif grande
  "subtitle": "78% de pontos no 1º serviço...", // descrição complementar
  "image":    "https://.../foto.jpg",           // URL absoluta ou caminho local
  "credit":   "Reuters / Yves Herman"           // fotógrafo/fonte. opcional
}
```

### Carrossel
```jsonc
{
  "surface": "clay",
  "badge":   "Análise",        // aparece só na capa
  "credit":  "Reuters / ...",  // mostrado em slides com foto
  "slides": [
    { "kind": "cover",  "kicker": "...", "title": "...", "subtitle": "...", "image": "..." },
    { "kind": "text",   "kicker": "...", "title": "...", "body": "..." },
    { "kind": "stat",   "value": "78%",  "caption": "...", "body": "..." },
    { "kind": "image",  "image": "...",  "caption": "..." },
    { "kind": "quote",  "quote": "...",  "attribution": "..." },
    { "kind": "outro",  "headline": "...", "cta": "Siga @cafecomteniss" }
  ]
}
```

#### Tipos de slide do carrossel

| `kind`  | Para quê                                            | Campos                                 |
| ------- | --------------------------------------------------- | -------------------------------------- |
| `cover` | Capa do carrossel — hook visual                     | `kicker?`, `title`, `subtitle?`, `image` |
| `text`  | Bloco textual em creme — explicação, contexto       | `kicker?`, `title`, `body?`            |
| `stat`  | Número-destaque sobre fundo escuro com gradiente    | `value`, `caption?`, `body?`           |
| `image` | Foto full-bleed com legenda em pé de página         | `image`, `caption`                     |
| `quote` | Citação grande em serif italic + atribuição         | `quote`, `attribution?`                |
| `outro` | CTA final ("Siga @cafecomteniss")                   | `headline?`, `cta?`                    |

Use o melhor para cada ideia. Ordem sugerida: `cover → text → stat → image → quote → outro`. Mas é flexível — repita ou pule à vontade.

---

## Sistema visual

### Superfícies (cor por tipo de quadra)

| `surface` | Quando usar                                | Primária   | Acento     |
| --------- | ------------------------------------------ | ---------- | ---------- |
| `hard`    | US Open, AO, Miami, Indian Wells, Cincinnati | `#1E40AF`  | `#3B82F6`  |
| `grass`   | Wimbledon, Queen's, Halle, Eastbourne       | `#1F6F3C`  | `#3DA15A`  |
| `clay`    | Roland Garros, Madrid, Roma, Rio Open       | `#B4441C`  | `#E76A2A`  |
| `neutral` | Ranking, opinião, conteúdo sem quadra       | `#1A1A1C`  | `#D4B96A`  |

### Badges sugeridos
`Resultado` · `Insight` · `Análise` · `Ranking` · `História` · `Notícia` · `Curiosidade` · `Agenda`
(Qualquer string curta funciona — vai em CAPS pelo CSS.)

### Tipografia
Carregada do Google Fonts no `<head>`:
- **Instrument Serif** — títulos editoriais
- **Geist** — subtítulos / corpo
- **Geist Mono** — badges, kickers, créditos, números de página

### Wordmark
Logo gerada inline em SVG (bolinha de tênis + "café com tênis" em serif italic). Para trocar quando tiver logo oficial: substituir o bloco `wordmarkSVG` / `wordmark()` no `<script>` de cada template.

---

## Dicas de conteúdo

- **Título curto**: 4–8 palavras. O serif fica grande, mais que isso polui.
- **Subtítulo factual**: 1–2 frases. Vai explicar/complementar, não repetir.
- **Imagem com espaço negativo**: a foto ideal tem ação no centro/superior e fundo limpo na parte inferior (onde mora o texto). Quando não tiver, o gradiente do template segura.
- **Stat slides**: o número precisa ser surpreendente. Se for óbvio, use `text` no lugar.
- **Carrossel ideal**: 5–8 slides. Menos não vale o swipe; mais cansa.

---

## Export rápido (sem puppeteer)

Abra o arquivo no Chrome:
- **Post**: redimensione a janela para 1080px de largura, F12 → device mode → 1080×1080, screenshot.
- **Carrossel**: cada slide tem `data-slide-index`. Console: `document.querySelector('[data-slide-index="0"]').scrollIntoView()` e capture.

Mas o caminho recomendado é puppeteer (snippets acima).
