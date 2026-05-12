# Guia de Estilo e Estrutura de Conteúdo para @cafecomteniss

Este documento estabelece as diretrizes para a reformulação do conteúdo e do design visual do Instagram @cafecomteniss, com o objetivo de aumentar o engajamento e atrair 30.000 novos seguidores em 30 dias. A estratégia se baseia na incorporação de dados estatísticos de alta qualidade, precisão histórica e um design visual moderno, inspirado em referências como @tennisinsights e ATP Tennis IQ.

## 1. Princípios Gerais de Conteúdo

O conteúdo deve ser **informativo, visualmente atraente e historicamente preciso**, com foco em insights que agreguem valor aos fãs de tênis. A linguagem deve ser envolvente, mas sempre clara e concisa.

## 2. Revisão da Seção "Na História"

O principal problema de contexto histórico será resolvido com uma reformulação clara do título e do corpo do texto. A data e o contexto histórico devem ser imediatamente visíveis e destacados.

### Estrutura Sugerida:

*   **Título Principal (Visualmente Destacado):** `HÁ X ANOS: [Evento Principal]`
    *   Exemplo: `HÁ 12 ANOS: Serena atropela Errani em Roma!`
*   **Subtítulo/Corpo do Texto (Detalhes):** `Em [Data Completa], [Nome do Jogador] dominou [Nome do Oponente] com parciais de [Placar] no torneio de [Nome do Torneio] em [Local]. Este jogo marcou [Contexto/Significância do Evento].`
    *   Exemplo: `Em 12 de maio de 2014, Serena Williams dominou Sara Errani com parciais de 6-3 6-0 no WTA Premier 5 de Roma. Este jogo marcou a 10ª vitória consecutiva de Serena no saibro.`

## 3. Qualidade e Tipo de Imagens (Integrado com Template HTML)

As imagens são cruciais para o engajamento. Serão priorizadas **fotos de ação de alta qualidade** e a **visualização de dados será realizada através do template HTML fornecido**, garantindo clareza e profissionalismo.

### Diretrizes para Imagens:

*   **Fotos de Atletas:** Utilizar imagens de ação recentes e de alta resolução dos atletas em quadra. Evitar fotos de gala ou desatualizadas. Fontes potenciais incluem bancos de imagens de esportes (com licença adequada), arquivos de imprensa de torneios ou, em último caso, pesquisa avançada no Google Imagens com filtros de uso comercial.
*   **Visualizações de Dados:** A apresentação visual dos dados será gerenciada pelo template HTML (`post.html`). O foco será em fornecer os dados corretos e a URL da imagem de fundo para o template. Se gráficos forem necessários, eles devem ser gerados externamente (por exemplo, via scripts Python com `matplotlib`) e sua URL fornecida ao campo `image` do JSON do template.
*   **Consistência Visual:** O template HTML (`post.html`) já garante uma paleta de cores e tipografia consistentes. As cores principais são neon `#C8F135` para destaque, fundo preto `#0A0A0A` e a fonte `Bebas Neue` (além de `Geist` e `Instrument Serif` já presentes no template). O uso do template padronizado para diferentes tipos de postagens (histórico, insights, notícias) garantirá a identidade visual.

## 4. Seção de Insights e Dados (Com Dados ATP Tennis IQ e Template HTML)

Esta nova seção trará análises aprofundadas e estatísticas relevantes para os fãs de tênis, utilizando dados da ATP Tennis IQ (via PIF) e outras fontes confiáveis, e será apresentada através do template HTML fornecido.

### Tipos de Conteúdo de Insights:

*   **Análise Pré-Jogo:** Comparativos de jogadores (H2H, performance em superfícies específicas, estatísticas recentes).
*   **Análise Pós-Jogo:** Destaque para métricas chave que definiram o resultado (ex: eficácia do saque, pontos ganhos no segundo saque, conversão de break points).
*   **Perfis de Jogadores:** Infográficos com o "DNA" estatístico de um atleta, usando gráficos de radar para mostrar pontos fortes e fracos.
*   **Curiosidades Estatísticas:** Dados interessantes sobre recordes, streaks, ou performances históricas com base em métricas avançadas.

### Métricas a Considerar (Exemplos):

*   **Shot Quality:** Qualidade do golpe (saque, devolução, forehand, backhand) em uma escala de 0-10 [1].
*   **Steal Rate:** Capacidade de roubar pontos no saque do adversário.
*   **Conversion Rate:** Percentual de break points convertidos.
*   **Performance Rating:** Avaliação geral de desempenho.
*   **First Serve % / Win % on 1st Serve:** Eficácia do primeiro saque.
*   **Winners / Unforced Errors:** Pontos vencedores e erros não forçados.

## 5. Estratégia de Crescimento (30k Seguidores em 30 Dias)

O crescimento acelerado exigirá uma combinação de conteúdo de alta qualidade, consistência e estratégias de engajamento.

### Ações Sugeridas:

*   **Frequência de Postagens:** Aumentar a frequência de postagens para 3-5 vezes ao dia, mantendo a qualidade.
*   **Reels e Carrosséis:** Priorizar formatos de vídeo curto (Reels) com insights rápidos e carrosséis com visualizações de dados interativas.
*   **Interação:** Responder a comentários, fazer perguntas nas legendas e usar enquetes/quizzes nos Stories para aumentar o engajamento.
*   **Colaborações:** Buscar parcerias com outros perfis de tênis ou influenciadores.
*   **Hashtags Estratégicas:** Pesquisar e utilizar hashtags relevantes e de alto alcance.
*   **Anúncios Pagos (Opcional):** Considerar campanhas de anúncios direcionadas para acelerar o crescimento, se o orçamento permitir.

## Referências

[1] ATP Tour. (s.d.). *INSIGHTS: Shot Quality Explained*. Disponível em: [https://www.atptour.com/en/news/insights-shot-quality](https://www.atptour.com/en/news/insights-shot-quality)

---

Este guia servirá como base para a criação do Master Prompt de automação, garantindo que todo o conteúdo gerado esteja alinhado com os novos padrões de qualidade e estratégia, e seja compatível com o template HTML fornecido.
