# Human + Desk (v2 — MVP Enxuto)

Assistente de service desk em Python que ajuda a analista a priorizar chamados e responder com clareza e empatia.  
**A IA só sugere, explica e registra. Quem decide e envia é sempre a analista.**

## O problema
A analista abre dezenas de chamados sem saber qual é mais urgente e escreve respostas sob pressão, com risco de prometer prazos que não pode cumprir.

## Fluxo v2 (humano no controle)
**Máscara (LGPD) → Agente 1: Triagem → Agente 2: Percepção → Agente 3: Redator (OARS + Guardrail) → Painel da Analista → Auditoria → Calibração**

- **Máscara (LGPD):** CPF, CNPJ, e-mail, telefone e nomes próprios (por heurística) são trocados por `[CPF]`, `[NOME]` etc. antes de qualquer agente ver o texto (`src/mascara.py`).
- **Agente 1 — Triagem (`src/triagem.py`):** intenção e urgência com **trecho literal** (*"sem trecho, sem campo"*).
- **Agente 2 — Percepção (`src/percepcao.py`):** até 3 palpites em forma de hipótese (*necessidade não dita*, *padrão entre chamados*, *risco de recorrência*) + 5 leituras possíveis e campo livre.
- **Agente 3 — Redator (`src/redator.py`):** rascunho em linguagem **OARS** conectado à Percepção (reage à leitura escolhida e aos palpites), deixando prazos e soluções provisórias em `[colchetes]` para a analista preencher.
- **Guardrail (`validar_rascunho`):** bloqueia promessa de prazo, rótulo sobre a pessoa, números que não constam no chamado e dado pessoal sem máscara.
- **Painel Streamlit (`app.py`):**
  - *Painel da Marina:* fila ordenada por urgência, seleção explícita de urgência (sem pré-seleção, para evitar viés de concordância automática), adaptação ao vivo do rascunho ao trocar a leitura e trava de `[colchetes]`.
  - *Painel do Rafael:* métricas, histórico por dia, calibração passiva das leituras, matriz de concordância da triagem e reabertura auditada de chamados.
- **Auditoria (`src/auditoria.py`):** log *append-only* em JSON Lines (`data/painel_log.jsonl` e `data/auditoria.jsonl`).
- **Persistência (`src/repositorio.py`):** `human_desk.db` é criado na raiz do projeto no primeiro `streamlit run app.py` e populado com os 16 chamados da fila e os 36 do benchmark, já mascarados. Mudar urgência, aprovar/rejeitar e reabrir gravam na hora na tabela `eventos`, com agente (`Marina`/`Rafael`) e timestamp ISO em UTC; reabrir não apaga a resolução anterior. Status, contadores e respostas registradas sobrevivem a F5 e ao reinício do Streamlit.

## Ética e escopo
- O sistema lê **sinais no texto**, nunca diagnostica nem rotula pessoas.
- Análise de prosódia/emoção na voz (`librosa`) está **fora do projeto** por risco legal (AI Act da UE / PL 2.338/2023) e baixa confiabilidade científica. Áudio entra apenas como canal (transcrição) em fase futura.
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

Para usar o Gemini, preencha `GEMINI_API_KEY` e `GEMINI_MODEL` no `.env` da raiz (arquivo ignorado pelo git). Sem chave, o comando acima cai silenciosamente em `regras`.

## Camada LLM (Fase 3 — integrada em `src/llm.py`)
- Dois adaptadores atrás da mesma interface: `regras` (padrão, determinístico e offline) e `gemini` (`gemini-3.5-flash-lite` no `.env` de referência).
- Chave e modelo ficam no `.env`, carregado por `src/config.py` tanto na CLI quanto no painel. Variáveis já definidas no terminal têm prioridade.
- O import do SDK é lazy. O fallback para regras é silencioso quando não há chave, quando o SDK falha (429/503/cota esgotada) ou quando a resposta não passa no guardrail.
- `validar_trechos` é comum aos dois adaptadores: exige trecho literal exato contra o texto **mascarado**, com capitalização preservada e fronteira de palavra (`cai` não casa com `caiu`).
- Espaçamento de 4,6 s entre chamadas e backoff limitado: 3 tentativas para 429 (respeitando `retryDelay`) e 5 para 503 (10/20/40/60 s).
- Contador de origem da triagem: `gemini`, `regras` e `fallback` (Gemini pedido, mas respondido pelas regras). O `--avaliar` imprime a linha `Origem: ...` e devolve o dicionário no resultado.
- A máscara cobre também nomes próprios por heurística (`src/mascara.py`), antes de qualquer envio externo.

## Benchmark no conjunto independente (36 chamados)
`data/chamados_validacao_independente.json` foi escrito com formulações naturais, sem ajustar regras nem prompt em cima dele. V01–V16 foram preservados da amostra original; V17–V36 foram acrescentados. Ambos os provedores rodaram no **mesmo arquivo**.

**Medição auditada (com contador de origem):**

| Métrica | Regras | Gemini | Diferença |
|---|---|---|---|
| Intenção | 8/36 (22%) | **26/36 (72%)** | +18 acertos |
| Urgência | 20/36 (56%) | **29/36 (81%)** | +9 acertos |

`[Fonte: saída de --provider gemini: "Origem: gemini=28 | regras=0 | fallback=8" e "Arquivo: chamados_validacao_independente.json | Provider: gemini | Intenção: 26/36 (72%) | Urgência: 29/36 (81%)", 23 de novembro de 2026]`

Dos 36 chamados, 28 foram respondidos pelo Gemini e 8 caíram em fallback por regras. A urgência se manteve em 29/36. A medição anterior, feita antes do contador e antes do endurecimento de `validar_trechos` com fronteira de palavra (`src/llm.py:122-129`), registrou 31/36 (86%) em intenção e 29/36 (81%) em urgência. A queda de 86% para 72% em intenção coincide com esse endurecimento e com a entrada do fallback por exceção de API. A causa dos 8 fallbacks **não foi instrumentada separadamente** — o contador não distingue trecho inválido de erro de API —, então não é possível atribuí-la sem nova medição.

Histórico: na amostra de 16 chamados, Regras 3/16 (19%) e 10/16 (62%) contra Gemini 13/16 (81%) e 12/16 (75%). A primeira tentativa de auditoria foi interrompida por `503 UNAVAILABLE` após as cinco tentativas de backoff, sem placar parcial; a segunda completou com o resultado acima.

**O que a medição cobre:** apenas a triagem (intenção e urgência), que é o que `--avaliar` compara entre os adaptadores. O redator com LLM existe em `rascunho_com_llm` e é usado pelo comando de demonstração, mas não entra neste placar.

## Limites honestos desta versão
- 36 chamados ainda é amostra pequena: o resultado é sinal forte, não número definitivo.
- O placar de 86% / 81% ficou apenas como histórico: foi medido antes do contador e antes do endurecimento de `validar_trechos`. O placar auditado é 72% / 81%, com separação por origem.
- A baseline das regras foi revalidada após o endurecimento de `validar_trechos` e da regex de prazo em `src/triagem.py`: segue em `8/36 (22%) | 20/36 (56%)`.
- A origem exibida no painel vem do valor por item devolvido por `triagem_com_origem`/`rascunho_com_origem`. O contador agregado `CONTADOR_TRIAGEM` serve apenas ao `--avaliar` da CLI e não mistura sessões do Streamlit.
- Transcrição de áudio (`openai-whisper`) e orquestração (`crewai`) seguem fora do MVP, como planejado.
- Análise de prosódia/emoção continua fora do projeto por risco legal e baixa confiabilidade científica.

## Painel Streamlit com LLM (implementado)
- Seletor explícito na barra lateral: `regras` (padrão) ou `gemini`. O modelo continua vindo do `.env`, sem valor fixo no código.
- Cada item mostra a procedência da triagem e do rascunho: `Gemini (API)`, `Regras (offline)` ou `Fallback por regras`.
- A fila é cacheada por provedor/modelo e cada rascunho adaptado é cacheado por item/leitura/provider, para não repetir chamadas a cada rerun do Streamlit.
- Na leitura inicial, o rascunho gerado ao montar a fila é reaproveitado em vez de ser refeito na tela: abrir o painel com Gemini custa 32 chamadas (16 triagens + 16 rascunhos), não 48.
- O retry do Redator Gemini exige os dois marcadores (`[PRAZO...]` e `[SOLUÇÃO PROVISÓRIA...]`); sem eles, cai em fallback por regras.
- Erro de API (429/503/cota) vira fallback e é sinalizado no selo — a tela da analista não quebra.
- A decisão continua 100% humana: urgência sem pré-seleção e origem registrada na auditoria.

## Próximos passos
1. Investigar os 8 fallbacks da medição auditada com instrumentação separada (trecho inválido vs. erro de API) antes de atribuir causa à queda de 86% para 72% em intenção.
2. Revalidar em amostra maior (50–100 chamados) antes de apresentar os números como definitivos à DXC.
3. Se fizer ajuste de prompt para `indefinida`, medir em chamados novos — nunca reutilizar os 36 como critério de sucesso.
