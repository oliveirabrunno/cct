# @cafecomteniss — Plano de Crescimento até 30k Seguidores

**Data:** 2026-05-27
**Janela crítica:** Roland Garros 2026 (em andamento)
**Catalisador imediato:** João Fonseca vs Novak Djokovic (próxima rodada)

## Contexto

O bot @cafecomteniss não publicou nada nos últimos 4 dias. Última peça gerada: 23/maio. Causas identificadas:

1. **Trend threshold irrealista** (4 menções em pt-BR/6h) — imprensa brasileira é lenta, Fonseca venceu mas nunca atingiu o threshold.
2. **Live monitor frágil** — varria só a página geral do Flashscore, não a página específica de Roland Garros; janela de 6h não comportava cron a cada hora.
3. **Sistema só reage, nunca antecipa** — não existia mecanismo para saber "amanhã Fonseca joga Djokovic às 11h BRT" e disparar conteúdo antes.

## Postura editorial: Event-Driven Bursts

Cadência baseline calma + EXPLOSÕES sincronizadas com big matches. Aproveita momentum sem fadiga de audiência.

### Baseline diário (4 posts/dia)
- 07h BRT: On this day (já funciona)
- 10h BRT: Stat card do jogador trending
- 15h BRT: Insight educativo (H2H ou stats avançados)
- 21h BRT: Night recap reel

### Camada burst (acionada pelo match_calendar)

```
T-48h  → Preview carrossel
T-24h  → Stat card do confronto
T-12h  → Story poll "Quem ganha?"
T-2h   → Reel teaser
T-30m  → Story countdown
T+0    → Story "Bola em jogo"
T+win  → Breaking card imediato
T+30m  → Carrossel highlights + stats
T+2h   → Reel de análise
T+24h  → Looking forward
```

Tamanho do burst depende do match importance score (1-10):
- **9-10** (Grand Slam + brasileiro/top tier): burst completo (6+ peças)
- **7-8** (Masters 1000 importante): burst médio (4 peças)
- **5-6** (relevante mas comum): 2 peças
- **<5**: ignora

**Fonseca x Djokovic em Roland Garros = importance 10.**

## Arquitetura técnica

### Componentes novos

**`scrapers/match_calendar.py`**
- `fetch_upcoming_matches(hours_ahead=72)` — varre Flashscore (URLs específicas de Grand Slam)
- `compute_importance(player_a, player_b, tournament, round)` — score 1-10
- `burst_plan(importance)` — lista de triggers com offset_h e tipo
- Persiste em `data/upcoming_matches.json`

**`scripts/burst_orchestrator.py`**
- Lê o calendário a cada 30min
- Para cada partida, verifica quais triggers estão na janela atual (±30min do offset)
- Dedup via SQLite: nunca repete trigger pro mesmo jogo em 24h
- Mapeia tipo de trigger → modo do orchestrator (`match-preview`, `stat-card`, `h2h-poll`, etc.)

**`.github/workflows/burst_orchestrator.yml`**
- Cron `0,30 8-23 * * *` (check de triggers)
- Cron `0 6,14,22 * * *` (refresh do calendário)

### Bugs corrigidos

| Arquivo | Mudança | Impacto |
|---|---|---|
| `analytics/trend_detector.py` | Threshold brasileiro = 2 (vs global 4) | Fonseca/Bia disparam com 2 menções em pt-BR |
| `scrapers/flashscore.py` | `MAX_MATCH_AGE_HOURS` 6 → 12 | Pega resultados mesmo com cron atrasado |
| `scrapers/flashscore.py` | Varre URL específica de Roland Garros | Cobertura confiável em Grand Slams |
| `scripts/competitor_insights.py` | Exit code 1 quando sem urgentes | Workflow agora skipa trigger_content corretamente |

## Hooks virais (tennis BR)

Categorias do `viral_master_prompt.txt` com novos exemplos contextualizados:

1. **Comparação geracional**: "Fonseca tem 19. Guga ganhou RG aos 24."
2. **Stat absurdo**: "Djokovic já tinha 7 títulos quando Fonseca nasceu."
3. **Mistério de chave**: "O caminho de Fonseca até a final passa por 3 ex-#1. Slide 4 vai te surpreender."
4. **Status BR**: "Brasileiros vivos no Roland Garros: 3. Há 10 anos eram 0."
5. **"E se?"**: "Fonseca vence Djokovic = top 20 garantido. Não é hipótese — é matemática."

## Mix de formato (target)

| Formato | Share | Razão |
|---|---|---|
| Carrossel | 40% | Melhor para retenção e save |
| Reel | 30% | **Multiplicador de alcance em 2026** para contas pequenas |
| Story | 20% | Engagement (polls, countdowns) |
| Card único | 10% | Breaking, momentos rápidos |

## Métricas de sucesso

- **Curto prazo (Roland Garros 2026):** 5k → 12k seguidores
- **Médio prazo (Wimbledon 2026):** 12k → 22k
- **Meta:** 30k antes do US Open 2026 (set/2026)

KPIs operacionais:
- ≥ 4 posts/dia em dias normais
- ≥ 8 posts em dias de big match
- 0 dias sem post (max gap atual: 4 dias — inaceitável)
- Tempo de reação para vitória de brasileiro: < 90min

## Próximos passos imediatos

1. ✅ Bugs corrigidos (threshold, MAX_AGE, RG URL, competitor exit code)
2. ✅ match_calendar.py + burst_orchestrator.py + workflow criados
3. ⏳ Commit + push + trigger manual do burst_orchestrator
4. ⏳ Verificar que `data/upcoming_matches.json` é gerado com Fonseca vs Djokovic
5. ⏳ Acompanhar primeiro burst em produção

## Estado conhecido / decisões tomadas

- **Não usar Instagram scraping direto** (ToS). Concorrentes são monitorados via Google News indexado.
- **GitHub Free tier (2000 min/mês)** é insuficiente. Plano aceita ~$5/mês em minutos extras OU migração futura para VPS.
- **claude-opus-4-7** em todos os prompts é caro mas justificável para qualidade na fase de bootstrap. Reavaliar quando passar de 10k seguidores.
- **Skip live_monitor de madrugada (00h-07h UTC)** — não tem jogo de tênis nesse horário.
