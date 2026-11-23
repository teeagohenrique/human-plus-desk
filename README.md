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
.\.venv\Scripts\streamlit.exe run app.py
```

## Limites honestos desta versão (v2 — Fases 1 e 2)
- Triagem e Percepção ainda rodam por **regras determinísticas**, sem LLM/CrewAI integrado.
- **Benchmark honesto:**
  - Em `data/chamados_simulados.json` (escrito junto com as regras): 16/16 (não prova qualidade).
  - Em `data/chamados_validacao_independente.json` (16 chamados com linguagem natural): **Intenção 3/16 (19%)** e **Urgência 10/16 (62%)**. Esse resultado evidencia o limite das regras fixas e justifica a Fase 3.
- Nomes de pessoas ainda **não** são mascarados (necessário NER/Presidio antes de enviar textos a LLMs externos).
- Transcrição de áudio (`openai-whisper`) e orquestração (`crewai`) ainda não estão ativos.

## Próximo passo (Fase 3)
1. Proteger nomes próprios na máscara de dados.
2. Integrar LLM / CrewAI (`output_pydantic`) na Triagem, Percepção e/ou Redator OARS, mantendo o guardrail determinístico em Python como trava obrigatória.
3. Reavaliar `data/chamados_validacao_independente.json` para medir o ganho real frente às regras.
