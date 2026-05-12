# =============================================================
# CAFÉ COM TÊNIS — @cafecomteniss
# TAREFA: POST INSTITUCIONAL DE LANÇAMENTO
# Para impulsionamento via Meta Ads
# Arquivo: scripts/generate_launch_post.py
# =============================================================

"""
CONTEXTO DA TAREFA
==================
Gerar o post institucional de lançamento do @cafecomteniss.
Esse post vai ser impulsionado via Meta Ads para adquirir
os primeiros seguidores antes de Roland Garros (25/mai/2026).

É o único post do canal que pode falar SOBRE o canal.
Todos os outros são sobre tênis. Este é a exceção.

OBJETIVO PRIMÁRIO: conversão em seguidor
OBJETIVO SECUNDÁRIO: estabelecer identidade do canal
CANAL DE DISTRIBUIÇÃO: Instagram Feed (carrossel) + Meta Ads
ORÇAMENTO ADS: a definir — otimizar para "Seguir perfil"
"""

# =============================================================
# PROMPT PARA O CLAUDE API GERAR O POST
# =============================================================

LAUNCH_POST_PROMPT = """
MODO: POST INSTITUCIONAL DE LANÇAMENTO — @cafecomteniss

Você vai criar o carrossel de lançamento do Café com Tênis.
Este é o único post do canal que fala SOBRE o canal.
Vai ser impulsionado via Meta Ads. Objetivo: converter visualização em seguidor.

---

SOBRE O CANAL:
Nome: Café com Tênis
Handle: @cafecomteniss
Proposta: conteúdo de tênis ATP + WTA em português —
news, estatísticas reais, curiosidades, polêmicas, bastidores,
análises de jogos e a cobertura dos brasileiros João Fonseca e Bia Haddad.
Sem rosto. A autoridade vem dos dados e da qualidade editorial.
Tom: direto, inteligente, leve toque de humor. Bar entre amigos
que entendem de tênis — não aula, não jornal.

---

PÚBLICO-ALVO DO AD:
- Fãs de tênis brasileiros, 18-45 anos
- Acompanham ATP e WTA ocasionalmente ou com frequência
- Torcedores de Fonseca, Alcaraz, Sinner, Swiatek
- Já seguem perfis como @rodrigobulso, @andreguedestennis
- Sentem falta de conteúdo de tênis de qualidade em português

---

ESTRUTURA DO CARROSSEL (8 slides):

SLIDE 1 — GANCHO (para o scroll + parar o ad)
Visual: fundo escuro, tipografia enorme, foto de atleta em ação
Objetivo: parar o scroll em 0.3 segundos
Texto: uma frase que captura tudo que o canal é
NÃO use "bem-vindo" ou "apresentando"
Pense: o que faria um fã de tênis parar o scroll às 22h?
Exemplo de direção (não copiar):
"O tênis que você queria acompanhar. Em português. Com dados."

SLIDE 2 — O PROBLEMA QUE RESOLVEMOS
Visual: lista clean, ícones simples
Texto: o que falta no mercado de conteúdo de tênis BR hoje
Ativar gatilho de IDENTIFICAÇÃO: "isso sou eu"
3-4 bullets curtos, diretos
Exemplo de direção:
"Você assiste às 3h da manhã mas nunca tem quem analise depois."
"A stat que muda tudo? Ninguém traduz para o Brasil."

SLIDE 3 — O QUE VOCÊ VAI ENCONTRAR AQUI (parte 1)
Visual: cards com ícones, layout limpo
Conteúdo: news e breaking results em tempo real
          H2H e estatísticas que ninguém calcula em PT
          Análises de jogos com dados reais
Frase de ancoragem: "Antes de qualquer outro canal em português."

SLIDE 4 — O QUE VOCÊ VAI ENCONTRAR AQUI (parte 2)
Visual: continuação visual do slide 3
Conteúdo: João Fonseca e Bia Haddad — cobertura total
          Curiosidades históricas que você não sabia
          Polêmicas e bastidores do tour
          Humor quando o tênis pede
Frase de ancoragem: "ATP + WTA. Todo dia. Sem perder nada."

SLIDE 5 — PROVA SOCIAL / AUTORIDADE (via dados do esporte)
Visual: stat grande, impactante
Não temos seguidores ainda — então a autoridade vem dos dados
que vamos trazer. Mostrar um exemplo real do tipo de conteúdo.
Use uma stat REAL e chocante do tênis atual:
Ex: João Fonseca, 19 anos, já é top 29 ATP.
    Nadal chegou lá com 21. Djokovic com 20.
    Isso é o que você vai encontrar aqui.

SLIDE 6 — ROLAND GARROS (urgência / momento)
Visual: saibro vermelho, tensão dramática
Roland Garros começa em 25 de maio.
O maior Grand Slam da temporada.
Fonseca, Alcaraz, Sinner, Swiatek.
Texto: criar senso de urgência — "você precisa estar aqui antes disso começar"
SEM contar a data explicitamente no slide — deixar em aberto para
o seguidor querer descobrir (pull, não push)

SLIDE 7 — COMO FUNCIONA (simplicidade)
Visual: 3 passos simples, visual clean
Passo 1: Segue o @cafecomteniss
Passo 2: Ativa as notificações
Passo 3: Nunca mais perde nada do tour
Frase: "30 segundos. Para não perder nada."
NÃO use "é grátis" — óbvio e barato

SLIDE 8 — CTA FINAL (conversão)
Visual: logo centralizado, fundo limpo, impacto máximo
Texto principal: uma frase. Uma.
CTA: direto, sem rodeio
Deve responder: "por que AGORA e não depois?"
Exemplo de direção:
"O tour não espera. Você vai acompanhar com ou sem dados.
Prefere com."
Handle grande: @cafecomteniss

---

LEGENDA DO POST (para o campo de caption do Instagram):

Escrever como se fosse a primeira conversa com o seguidor.
Tom: como se um amigo apaixonado por tênis estivesse
apresentando o canal para outro amigo.

Estrutura da legenda:
- Linha 1: hook que complementa o slide 1 (não repete)
- Parágrafo 1: o que somos (2-3 frases)
- Parágrafo 2: o que vamos cobrir (específico, com nomes)
- Parágrafo 3: por que agora (Roland Garros, Fonseca)
- CTA final: simples, direto
- Hashtags: 20 hashtags estratégicas

Máximo: 200 palavras no corpo + hashtags separados.

---

CONFIGURAÇÃO PARA META ADS:

Gerar também as seguintes variações para teste A/B no Ads Manager:

VERSÃO A — EMOCIONAL:
Foco na identificação do fã que fica sem conteúdo de qualidade.
Hook: a dor de ser fã de tênis no Brasil.
CTA: "agora tem um lugar para você"

VERSÃO B — RACIONAL:
Foco nos dados e na cobertura técnica.
Hook: stats e análises que não existem em PT.
CTA: "acompanhe com inteligência"

VERSÃO C — URGÊNCIA (FONSECA):
Foco no João Fonseca e Roland Garros.
Hook: o melhor tenista brasileiro de uma geração.
CTA: "não perde nenhum jogo dele"

Para cada versão, gerar:
- Headline do ad (máx 40 caracteres): texto principal do Meta Ads
- Texto primário (máx 125 caracteres): aparece acima da imagem
- Descrição (máx 30 caracteres): texto abaixo do CTA

---

ESPECIFICAÇÕES VISUAIS PARA O CLAUDE GERAR O HTML:

Brand kit do @cafecomteniss:
- Fundo principal: #0A0A0A (preto quente)
- Destaque: #C8F135 (verde lima — cor da marca)
- Texto principal: #FFFFFF
- Texto secundário: #AAAAAA
- Superfícies: #111111
- Fontes: 'Bebas Neue' (títulos grandes), 'DM Sans' (corpo)
- Tamanho de cada slide: 1080x1080px (feed) ou 1080x1350px (retrato)
- Logo: texto "café com tênis" em Bebas Neue, cor lima, canto inferior direito
- Fotografias: atletas reais das fotos do banco Wikimedia (já baixadas)

ESTILO VISUAL GERAL:
Dark, editorial, premium mas acessível. Contraste alto.
Hierarquia tipográfica clara. Números grandes quando há stat.
Não é revista de luxo. É canal de conteúdo com personalidade.
Referência visual: entre o @statmuse e o @espnfc.

---

OUTPUT ESPERADO DO CLAUDE CODE:

1. HTML de cada um dos 8 slides (para Puppeteer converter em PNG)
2. Caption completa em português
3. 20 hashtags estratégicas
4. 3 variações de copy para Meta Ads (A/B/C)
5. Recomendação de configuração do ad:
   - Objetivo: Engajamento com perfil (seguir)
   - Público: Brasil, 18-45, interesse em tênis/esportes
   - Formato: Carrossel
   - Orçamento sugerido: R$30-50/dia por 7 dias para validar
   - Duração: 7 dias antes de Roland Garros

---

CHECKLIST ANTES DE FINALIZAR:

[ ] Slide 1 para o scroll em 0.3 segundos?
[ ] Cada slide faz querer ver o próximo?
[ ] Post funciona para quem nunca viu o perfil?
[ ] Caption ativa gatilho de identificação + utilidade?
[ ] CTA é invisível (não pede explicitamente o follow)?
[ ] Copy do ad tem menos de 125 chars no texto primário?
[ ] Visual usa apenas o brand kit definido?
[ ] Fotos de atletas são do banco local (Wikimedia)?
[ ] Puppeteer vai conseguir renderizar o HTML?

---

COMO RODAR:

python scripts/generate_launch_post.py

O script vai:
1. Chamar a Claude API com este prompt
2. Parsear o JSON de output
3. Gerar os 8 HTMLs dos slides
4. Converter cada HTML em PNG via Puppeteer
5. Salvar em output/launch_post/
6. Gerar launch_post_copy.txt com legenda + ad copy
7. Exibir preview no terminal

Após revisão manual → publicar no Instagram → impulsionar via Meta Ads.
"""

# =============================================================
# CONFIGURAÇÃO DO META ADS (referência)
# =============================================================

META_ADS_CONFIG = {
    "objetivo": "PROFILE_VISITS",  # ou PAGE_LIKES — testar ambos
    "formato": "CAROUSEL",
    "publico": {
        "paises": ["BR"],
        "idade_min": 18,
        "idade_max": 45,
        "interesses": [
            "Tennis", "ATP World Tour", "WTA",
            "Roland Garros", "Wimbledon",
            "João Fonseca", "Carlos Alcaraz",
            "Esportes", "ESPN Brasil"
        ],
        "comportamentos": ["Engaged Shoppers", "Sports fans"]
    },
    "orcamento_diario_reais": 40,
    "duracao_dias": 7,
    "horarios_pico": ["07:00-09:00", "12:00-14:00", "19:00-22:00"],
    "copies_ab_test": ["emocional", "racional", "urgencia_fonseca"],
    "nota": """
        Começar com R$40/dia por 7 dias = R$280 total para validar.
        Acompanhar CPF (Custo Por Seguidor) diariamente.
        Se CPF > R$2,00: pausar e testar nova copy.
        Se CPF < R$1,00: escalar orçamento.
        Meta: 1.000 seguidores pagos na primeira semana.
    """
}
