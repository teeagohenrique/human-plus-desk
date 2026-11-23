# Human + Desk (v2 — MVP Enxuto)

Assistente de service desk em Python que ajuda a analista a priorizar chamados e responder com clareza e empatia.  
**A IA só sugere, explica e registra. Quem decide e envia é sempre a analista.**

## O problema
A analista abre dezenas de chamados sem saber qual é mais urgente e escreve respostas sob pressão, com risco de prometer prazos que não pode cumprir.

## Fluxo v2 (humano no controle)
**Máscara (LGPD) → Agente 1: Triagem → Agente 2: Percepção → Agente 3: Redator (OARS + Guardrail) → Painel da Analista → Auditoria → Calibração**

- **Máscara (LGPD):** CPF, CNPJ, e-mail e telefone são trocados por `[CPF]` etc. antes de qualquer agente ver o texto (`src/mascara.py`).
- **Agente 1 — Triagem (`src/triagem.py`):** intenção e urgência com **trecho literal** (*"sem trecho, sem campo"*).
- **Agente 2 — Percepção (`src/percepcao.py`):** até 3 palpites em forma de hipótese (*necessidade não dita*, *padrão entre chamados*, *risco de recorrência*) + 5 leituras possíveis e campo livre.
- **Agente 3 — Redator (`src/redator.py`):** rascunho em linguagem **OARS** conectado à Percepção (reage à leitura escolhida e aos palpites), deixando prazos e soluções provisórias em `[colchetes]` para a analista preencher.
- **Guardrail (`validar_rascunho`):** bloqueia promessa de prazo, rótulo sobre a pessoa, números que não constam no chamado e dado pessoal sem máscara.
- **Painel Streamlit (`app.py`):**
  - *Painel da Marina:* fila ordenada por urgência, seleção explícita de urgência (sem pré-seleção, para evitar viés de concordância automática), adaptação ao vivo do rascunho ao trocar a leitura e trava de `[colchetes]`.
  - *Painel do Rafael:* métricas, histórico por dia, calibração passiva das leituras e matriz de concordância da triagem.
- **Auditoria (`src/auditoria.py`):** log *append-only* em JSON Lines (`data/painel_log.jsonl` e `data/auditoria.jsonl`).

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
- Chave e modelo ficam no `.env`, carregado por `src/main.py` apenas na execução da CLI. Variáveis já definidas no terminal têm prioridade.
- O import do SDK é lazy e o fallback para regras é silencioso quando não há chave.
- `validar_trechos` é comum aos dois adaptadores: exige trecho literal exato contra o texto **mascarado**, com capitalização preservada.
- Espaçamento de 4,6 s entre chamadas e backoff limitado: 3 tentativas para 429 (respeitando `retryDelay`) e 5 para 503 (10/20/40/60 s).
- A máscara cobre também nomes próprios por heurística (`src/mascara.py`), antes de qualquer envio externo.

## Benchmark no conjunto independente (36 chamados)
`data/chamados_validacao_independente.json` foi escrito com formulações naturais, sem ajustar regras nem prompt em cima dele. V01–V16 foram preservados da amostra original; V17–V36 foram acrescentados. Ambos os provedores rodaram no **mesmo arquivo**.

| Métrica | Regras | Gemini | Diferença |
|---|---|---|---|
| Intenção | 8/36 (22%) | **31/36 (86%)** | +23 acertos |
| Urgência | 20/36 (56%) | **29/36 (81%)** | +9 acertos |

`[Fonte: saídas de --provider regras e --provider gemini no mesmo arquivo, 23 de novembro de 2026]`

Na medição anterior de 16 chamados, o placar foi Regras 3/16 (19%) e 10/16 (62%) contra Gemini 13/16 (81%) e 12/16 (75%). A amostra maior confirmou o ganho.

**O que a medição cobre:** apenas a triagem (intenção e urgência), que é o que `--avaliar` compara entre os adaptadores. O redator com LLM existe em `rascunho_com_llm` e é usado pelo comando de demonstração, mas não entra neste placar.

## Limites honestos desta versão
- 36 chamados ainda é amostra pequena: o resultado é sinal forte, não número definitivo.
- A medição não distingue quantos chamados foram respondidos pelo Gemini e quantos caíram no fallback silencioso para regras.
- `validar_trechos` aceita fragmento de palavra (ex.: `cai` em `caiu`); é ponto de atenção, não alterado nesta rodada.
- O painel Streamlit (`app.py`, `src/painel.py`) ainda consome triagem e rascunho por **regras**. O Gemini está disponível pela CLI; levá-lo ao painel é trabalho futuro.
- Transcrição de áudio (`openai-whisper`) e orquestração (`crewai`) seguem fora do MVP, como planejado.
- Análise de prosódia/emoção continua fora do projeto por risco legal e baixa confiabilidade científica.

## Próximos passos
1. Registrar contador de fallback na medição, para separar respostas do modelo e das regras.
2. Levar o adaptador LLM ao painel, mantendo o guardrail determinístico e a decisão humana sem pré-seleção.
3. Revalidar em amostra maior (50–100 chamados) antes de apresentar os números como definitivos à DXC.
