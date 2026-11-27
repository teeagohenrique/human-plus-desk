# Human + Desk (v2 — MVP Enxuto)

Assistente de service desk em Python que ajuda a analista a priorizar chamados e responder com clareza e empatia.  
**A IA só sugere, explica e registra. Quem decide e envia é sempre a analista.**

## Em poucas linhas

- **Governança antes de IA:** CPF, CNPJ, e-mail, telefone e nomes próprios são mascarados antes do processamento. Padrões fixos, heurísticas e NER local rodam offline; se o NER falhar e Gemini estiver selecionado, o texto não é enviado e o fluxo cai para regras (`src/mascara.py`, `src/ner_local.py`, `src/pipeline.py`).
- **Humano no controle:** urgência sem pré-seleção, `[colchetes]` obrigatórios no rascunho e decisão 100% humana na tela (`src/ui_marina.py`, `app.py`).
- **Resiliência observável:** regras offline e Gemini atrás da mesma interface; origem efetiva exibida por chamado e motivos de fallback contados na CLI (`src/llm.py`, `app.py`).
- **Engenharia verificada:** 278 testes coletados (`pytest --collect-only -q`), incluindo `AppTest`, regressões de máscara/NER, outbox, estimativas por horário comercial, simulação de passos/prazo do Acervo e conteúdo bilíngue; Ruff e `compileall` limpos. CI executa Ruff, compilação, pytest e mypy em cada push/PR (GitHub Actions).

## Estado do projeto — Etapas concluídas (27/11/2026)

| Etapa | Método | Resultado |
|---|---|---|
| **1 — Diagnóstico** | Mapeamento da stack, dependências desatualizadas, variáveis de ambiente, estrutura de pastas e fluxo atual. | Levantamento completo (`src/`, `tests/`, `data/`, `.github/`, `docs/`) e pontos de dor identificados. |
| **2 — Plano de refactor** | Definição da arquitetura (camadas separadas, contratos e testes), padrões de migração e checklist de qualidade. | Plano de execução com prioridade SOLID, validação robusta e cobertura de testes. |
| **3 — Núcleo/Core** | Refatoração dos módulos de negócio com SOLID, tipagem forte, logs estruturados, tratamento robusto de erros e validação rigorosa de entradas (`src/painel.py`, `src/triagem.py`, `src/redator.py`, `src/llm.py`, `src/auditoria.py`, `src/repositorio.py`, etc.). | Remoção de código morto e duplicado. **278 testes passando** (cobertura média 91%). Zero imports quebrados. |
| **4 — Utilitários e Testes** | Limpeza de funções duplicadas, manutenção de 278 testes, verificação de imports, dependências e `.env.example`. | Remoção de `decisao_por_texto` (redundante com `classificar_resposta`). Suíte completa verde. Build OK. `pip install -e .` ok. |

## O problema
A analista abre dezenas de chamados sem saber qual é mais urgente e escreve respostas sob pressão, com risco de prometer prazos que não pode cumprir.

## Fluxo v2 (humano no controle)
**Máscara (LGPD) → Agente 1: Triagem → Agente 2: Percepção → Agente 3: Redator (OARS + Guardrail) → Painel da Analista → Auditoria → Calibração**

- **Máscara (`src/mascara.py`):** CPF, CNPJ, e-mail, telefone e nomes próprios são substituídos por marcadores usando padrões locais, heurísticas e NER Presidio/spaCy. Se a execução do NER falhar, o status da máscara é reportado; ao pedir Gemini, o pipeline não envia o texto e usa as regras locais. Os detectores não garantem cobertura universal de dados identificáveis.
- **Agente 1 — Triagem (`src/triagem.py`):** intenção e urgência com **trecho literal** (*"sem trecho, sem campo"*).
- **Agente 2 — Percepção (`src/percepcao.py`):** até 3 palpites em forma de hipótese (*necessidade não dita*, *padrão entre chamados*, *risco de recorrência*) + 5 leituras possíveis e campo livre. Na hipótese de necessidade não dita, indica o tópico correspondente no Acervo e as palavras relacionadas do chamado.
- **Acervo de Soluções (`src/acervo.py`, `data/acervo_simulado.json`, `data/acervo_simulado_en.json`):** 5 materiais e 20 tópicos fictícios em PT/EN. Os cenários são demonstrativos, não SLAs; o simulador conta dias úteis de 09h às 18h em São Paulo e não considera feriados.
- **Agente 3 — Redator (`src/redator.py`):** rascunho em linguagem **OARS** conectado à Percepção e ao Acervo (substitui automaticamente `[SOLUÇÃO PROVISÓRIA...]` pela solução do acervo entre `[ ]`, mantendo apenas `[PRAZO DE RETORNO: a analista preenche]` como pendência obrigatória).
- **Guardrail (`validar_rascunho`):** bloqueia promessa de prazo, rótulo sobre a pessoa, números que não constam no chamado e dado pessoal sem máscara.
- **Painel Streamlit (`app.py`, com as telas em `src/ui_marina.py` e `src/ui_rafael.py`):**
  - *Central de Atendimento (Marina):* fila ordenada por urgência, seleção explícita de urgência (sem pré-seleção, para evitar viés de concordância automática), consulta à Aba do Acervo com simulador de tempo, botão `"Usar na minha resposta"` sinalizado, trava de pendências em `[colchetes]` e exibição apenas de `@` no lugar do nome do cliente/paciente.
  - *Gestão e Qualidade (Rafael):* métricas, histórico por dia, calibração passiva das leituras, matriz de concordância da triagem, visualização da resposta finalizada e reabertura auditada; cadastro de nomes simulado fica em `data/supervisao_simulada.json`, usado somente nessa visão.
- **Auditoria (`src/auditoria.py`, `src/repositorio.py`):** decisões primeiro em transação SQLite; um outbox idempotente exporta JSONL após commit e tenta sincronizar eventos pendentes na inicialização.
- **Persistência (`src/repositorio.py`):** `human_desk.db` é criado na raiz e populado com 16 chamados da fila e os 50 do benchmark, já mascarados. Decisões, urgências e reaberturas são gravadas em transações com agente e timestamp ISO UTC; o outbox publica decisões no JSONL de forma idempotente. Reaberturas preservam o histórico anterior.

## Ética e escopo
- O sistema lê **sinais no texto**, nunca diagnostica nem rotula pessoas.
- Entrada por áudio transcrito é futura e planejada em `docs/audio-transcricao-futura.md`; qualquer implementação deverá revisar a transcrição, passar pelo mesmo fluxo de máscara e nunca inferir emoção pela voz.
- Este repositório é uma simulação com dados fictícios, sem autenticação por usuário ou controle de autorização no servidor. Antes de qualquer uso com dados reais, implementar autenticação/autorização, política de retenção e proteção de armazenamento; a navegação Marina/Rafael não é controle de acesso.
- O módulo `src/autonomia.py` (portão estatístico Clopper-Pearson) foi **pausado/desligado da interface do MVP** e mantido apenas como referência para escala futura com dados reais.

## Como rodar (usando o `.venv` já configurado)
```powershell
cd human-plus-desk
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.main
.\.venv\Scripts\python.exe -m src.main --avaliar
.\.venv\Scripts\python.exe -m src.main --avaliar data\chamados_validacao_independente.json
.\.venv\Scripts\python.exe -m src.main --avaliar data\chamados_validacao_independente.json --provider gemini
.\.venv\Scripts\streamlit.exe run app.py
```

Para usar o Gemini, configure `GEMINI_API_KEY` e `GEMINI_MODEL` no `.env` da raiz (ignorado pelo git). Sem chave, o modo é `regras`; se a chave estiver presente mas faltar o modelo ou o NER local falhar, há fallback para regras com motivo contado na CLI, sem chamada externa.

## Camada LLM (Fase 3 — integrada em `src/llm.py`)
- Dois adaptadores atrás da mesma interface: `regras` (padrão, determinístico e offline) e `gemini` (`gemini-3.5-flash-lite` no `.env` de referência).
- Chave e modelo ficam no `.env`, carregado por `src/config.py` tanto na CLI quanto no painel. Variáveis já definidas no terminal têm prioridade.
- O import do SDK é lazy. Falhas de SDK/API, modelo ausente, máscara NER incompleta ou resposta rejeitada usam regras locais; a origem aparece no chamado e a CLI conta os motivos de fallback.
- `validar_trechos` é comum aos dois adaptadores: exige trecho literal exato contra o texto **mascarado**, com capitalização preservada e fronteira de palavra (`cai` não casa com `caiu`).
- Espaçamento de 4,6 s entre chamadas e backoff limitado: 3 tentativas para 429 (respeitando `retryDelay`) e 5 para 503 (10/20/40/60 s).
- Contador de origem da triagem: `gemini`, `regras` e `fallback` (Gemini pedido, mas respondido pelas regras). O `--avaliar` imprime `Origem: ...` e `Fallbacks: ...` e devolve ambos os dicionários (`origem` e `fallback_motivos`) no resultado. `zerar_contadores()` limpa os dois antes de cada medição. "Gemini pedido sem chave" continua contando como `regras`, não como fallback.
- A máscara cobre nomes próprios por heurística de prefixos e por NER local (`src/mascara.py`, `src/ner_local.py`), antes de qualquer envio externo. O modelo PT é instalado com `python -m spacy download pt_core_news_sm` (não está no PyPI).

## Benchmark de validação (50 chamados; resultados Gemini históricos em V01–V36)
`data/chamados_validacao_independente.json` contém agora 50 casos sintéticos. V01–V36 preservam o lote original; V37–V50 são um lote complementar criado sem consultar o código das regras nem ajustar o prompt. Todos os dados são fictícios. Os novos gabaritos ainda precisam de revisão por especialistas; portanto, os resultados são exploratórios e não devem ser apresentados como validação definitiva.

**Baseline atual verificada para regras (50 chamados):**

| Métrica | Regras | Resultado |
|---|---:|---:|
| Intenção | 16/50 | 32% |
| Urgência | 28/50 | 56% |

`[Fonte: execução local de python -m src.main --avaliar data/chamados_validacao_independente.json --provider regras; 24 de novembro de 2026]`

A comparação com Gemini abaixo é histórica e cobre somente os 36 casos originais. Não foi repetida no conjunto ampliado; não há resultado Gemini verificado para 50 casos.

**Medição histórica no lote original (36 chamados):**

| Métrica | Regras | Gemini | Diferença |
|---|---|---|---|
| Intenção | 8/36 (22%) | **26/36 (72%)** | +18 acertos |
| Urgência | 20/36 (56%) | **29/36 (81%)** | +9 acertos |

`[Fonte: saída de --provider gemini: "Origem: gemini=28 | regras=0 | fallback=8" e "Arquivo: chamados_validacao_independente.json | Provider: gemini | Intenção: 26/36 (72%) | Urgência: 29/36 (81%)", 23 de novembro de 2026]`

Dos 36 chamados, 28 foram respondidos pelo Gemini e 8 caíram em fallback por regras. A urgência se manteve em 29/36. A medição anterior, feita antes do contador e antes do endurecimento de `validar_trechos` com fronteira de palavra (`src/llm.py :: validar_trechos`), registrou 31/36 (86%) em intenção e 29/36 (81%) em urgência. A queda de 86% para 72% em intenção coincide com esse endurecimento e com a entrada do fallback por exceção de API. Essa medição antiga **não separava os motivos**. `src/llm.py` agora registra cada fallback por causa (erro de API por status, trecho inválido, schema inválido, guardrail, marcadores faltantes, SDK ou cliente indisponíveis) e o `--avaliar` imprime a linha `Fallbacks: ...`. A nova medição com a instrumentação ligada está registrada abaixo e não reproduziu os 8 fallbacks; classificar retroativamente aqueles casos não é possível com os dados disponíveis.

**Nova medição (instrumentação de motivos ligada, 23 de novembro de 2026):**

| Métrica | Regras | Gemini | Diferença |
|---|---|---|---|
| Intenção | 8/36 (22%) | **32/36 (89%)** | +24 acertos |
| Urgência | 20/36 (56%) | **27/36 (75%)** | +7 acertos |

`[Fonte: saída de rodar_comparativo.ps1: "Origem: gemini=36 | regras=0 | fallback=0", "Fallbacks: nenhum" e "Arquivo: chamados_validacao_independente.json | Provider: gemini | Intenção: 32/36 (89%) | Urgência: 27/36 (75%)"]`

Nesta execução não houve nenhum fallback — nem 429/503, nem `trecho_invalido`, `schema_invalido` ou qualquer outro motivo registrado. O placar anterior, com 28 acertos e 8 fallbacks em intenção, não foi reproduzido; a causa daqueles 8 casos segue sem classificação.

Histórico: na amostra de 16 chamados, Regras 3/16 (19%) e 10/16 (62%) contra Gemini 13/16 (81%) e 12/16 (75%). A primeira tentativa de auditoria foi interrompida por `503 UNAVAILABLE` após as cinco tentativas de backoff, sem placar parcial; a segunda completou com o resultado acima.

**O que a medição cobre:** apenas a triagem (intenção e urgência), que é o que `--avaliar` compara entre os adaptadores. O redator com LLM existe em `rascunho_com_llm` (`src/llm.py:560`) e é exposto via `processar_chamado` (`src/main.py:55`); o comando `demonstrar` (`src/main.py:70-72`) executa `processar` sobre a fila, e `rascunho_com_llm` não é o caminho do teste de demonstração, portanto não entra neste placar.

## Limites honestos desta versão
- A amostra atual tem 50 casos sintéticos. V37–V50 ainda precisam de revisão especializada; métricas em amostra sintética não são validação de produção.
- As métricas Gemini de 72%/81% e 89%/75% são históricas, medidas somente nos 36 casos V01–V36. Não existe placar Gemini verificado para os 50 casos.
- A baseline local medida na amostra ampliada é 16/50 (32%) em intenção e 28/50 (56%) em urgência. Não ajustamos regras em função do lote V37–V50.
- A origem exibida no painel vem do valor por item devolvido por `triagem_com_origem`/`rascunho_com_origem`. O contador agregado `CONTADOR_TRIAGEM` serve apenas ao `--avaliar` da CLI e não mistura sessões do Streamlit.
- Transcrição de áudio segue como fase futura planejada em `docs/audio-transcricao-futura.md`; somente texto transcrito, revisão humana e máscara serão permitidos. Não inclui análise de emoção na voz.
- Análise de prosódia/emoção continua fora do projeto por risco legal e baixa confiabilidade científica.

## Painel Streamlit com LLM (implementado)
- Seletor explícito na barra lateral: `regras` (padrão) ou `gemini`. O modelo continua vindo do `.env`, sem valor fixo no código.
- Cada item mostra a procedência da triagem e do rascunho: `Gemini (API)`, `Regras (offline)` ou `Fallback por regras`.
- A fila é cacheada por provedor/modelo e cada rascunho adaptado é cacheado por item/leitura/provider, para não repetir chamadas a cada rerun do Streamlit.
- Na leitura inicial, o rascunho gerado ao montar a fila é reaproveitado em vez de ser refeito na tela: abrir o painel com Gemini custa 32 chamadas (16 triagens + 16 rascunhos), não 48.
- O retry do Redator Gemini exige os dois marcadores (`[PRAZO...]` e `[SOLUÇÃO PROVISÓRIA...]`); sem eles, cai em fallback por regras.
- Erro de API (429/503/cota) vira fallback e é sinalizado no selo — a tela da analista não quebra.
- A decisão continua 100% humana: urgência sem pré-seleção e origem registrada na auditoria.

## Camada de apresentação (`src/tema_dxc.py` e `src/textos.py`)
- A identidade visual DXC (paleta roxo/magenta/laranja, Space Grotesk, logotipo Human [+] Desk), o seletor de idioma e o alternador Claro/Escuro ficam em `src/tema_dxc.py`. Os textos PT/EN vivem em `src/textos.py` — 201 chaves por idioma, incluindo 9 blocos aninhados e 228 entradas-folha — e são reexportados por `src/tema_dxc.py`.
- `app.py` importa `I18N`, `render_dxc_theme`, `render_dxc_logo` e `render_language_selector` de `src/tema_dxc.py`; não mantém cópia local de CSS, SVG ou traduções. `get_text` fica disponível no módulo para rótulos pontuais sem duplicar o dicionário.
- O seletor PT/EN fica no topo da área principal; o tema Claro/Escuro fica na barra lateral (`tema_ui`). As chaves de widgets usadas pela agent API (`urg_ui_C15`, callbacks e filtros) não mudaram.
- O módulo de tema não lê segredos: a configuração continua restrita a `GEMINI_API_KEY` e `GEMINI_MODEL` em `.env` (`src/config.py`). Use `.env.example` como referência; valores iguais a `sua_chave_aqui` são ignorados (`src/config.py :: carregar_env`).
- `tests/test_tema_dxc.py` cobre paridade PT/EN de 201 chaves (9 blocos, 228 entradas-folha), CSS, SVG e troca de idioma; `tests/test_app_navegacao.py` cobre navegação e preservação de estado. Suíte total: **278 testes coletados** (`pytest --collect-only -q`).

## Próximos passos
1. Revisar os rótulos V37–V50 com especialistas de service desk e congelar a versão do conjunto antes de qualquer ajuste de regras ou prompt.
2. Após revisão e autorização para chamadas externas, executar Gemini nos mesmos 50 casos e registrar modelo, data, origem e fallbacks; essa medição ainda não foi feita.
3. Antes de apresentar métricas definitivas à DXC, ampliar para 100 casos com um lote de teste reservado, sem usá-lo para ajustar regras ou prompts.
4. Antes de qualquer dado real, implementar autenticação/autorização no servidor, política de retenção e armazenamento protegido; o protótipo atual é simulado.
