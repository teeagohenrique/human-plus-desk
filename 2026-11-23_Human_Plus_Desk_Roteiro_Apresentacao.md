# Roteiro de Apresentação Sênior — Human [+] Desk (4 min)

Documento de apoio para a demo. Não altera código, testes, prompts nem contratos.

## Bloco 1 — Contexto e Privacidade por Design (0:00 – 0:45)

**Ação na tela:** Abra a Central de Atendimento no chamado crítico (C15 • Acesso). Aponte para a caixa de texto e para o selo LGPD • Dados Mascarados.

**O que dizer:**
> "O desafio de colocar IA em operações de suporte corporativo não é gerar texto — é governança. No Human [+] Desk, aplicamos mascaramento de dados sensíveis antes que qualquer informação toque a camada de inteligência. O analista trabalha com o contexto operacional completo, com os dados pessoais mascarados na origem, e a privacidade (LGPD) é garantida antes da chamada à IA."

**Evidência:** `src/pipeline.py:45` mascara (`mascarar(texto)`) antes de `llm.triagem_com_origem(mascara.texto, ...)` em `:46` e `llm.rascunho_com_origem(mascara.texto, ...)` em `:54`. O selo é `txt["lgpd_badge"]` em `src/ui_marina.py:254`, seguido do texto mascarado em `:256`. C15 tem `gabarito.intencao = "acesso"` e `urgencia = "alta"` em `data/chamados_simulados.json`.

## Bloco 2 — Resiliência e Troca de Adaptador ao Vivo (0:45 – 1:30)

**Ação na tela:** Na barra lateral, alterne o seletor Motor de IA entre o modo Regras (offline) e Gemini, mostrando o rascunho se adaptar em tempo real.

**O que dizer:**
> "Sistemas críticos não podem parar se uma API externa oscilar. Projetamos uma arquitetura desacoplada de adaptadores: aqui eu consigo alternar ao vivo entre o motor determinístico offline e o Gemini. O sistema degrada com elegância, sem interromper o SLA da operação."

**Evidência:** `src/ui_comum.py:fila_base()` passa `provider` e `model` para `montar_fila`; o modelo vem de `os.getenv("GEMINI_MODEL", "")`, nunca fixo no código. `src/llm.py:435-449` devolve a origem de cada triagem (`gemini`, `regras` ou `fallback`) e `src/painel.py:75` registra a origem efetiva de cada rascunho.

## Bloco 3 — Mitigação de Viés e "Humano no Controle" (1:30 – 2:30)

**Ação na tela:** Clique no fluxo de 3 passos: no Passo 2 (Definir urgência), destaque que nenhuma opção vem marcada por padrão. Selecione a urgência, avance para o Passo 3, preencha os [colchetes] e clique em Aprovar.

**O que dizer:**
> "Para evitar que o analista apenas clique em 'aceitar' no piloto automático — o que contamina as métricas de qualidade —, a urgência intencionalmente não vem pré-selecionada. Além disso, o sistema trava o envio enquanto houver variáveis entre [colchetes] pendentes, garantindo zero erro operacional antes da resposta sair."

**Evidência:** `src/ui_marina.py:83` inicializa `"urgencia": None`; o `st.pills` em `:375` usa `default=estado["urgencia"]` com `key=f"urg_ui_{item.id}"` e callback `_registrar_urgencia_ui` (`:54`), que grava no SQLite em `:58`. A trava de [colchetes] está em `:438` (`need_brack`) e o botão de aprovação em `:444`. A validação pela agent API confirmou o widget `urg_ui_C15` sem valor pré-selecionado.

## Bloco 4 — Governança, Calibração e Persistência (2:30 – 3:30)

**Ação na tela:** Mude para a tela de Gestão e Qualidade (Rafael). Mostre a matriz de calibração (IA × Analista), o histórico persistido no SQLite e faça o teste de Reabrir Chamado (ou dê um F5 na página).

**O que dizer:**
> "Na visão de gestão do Rafael, fechamos o ciclo de auditoria. Usamos SQLite para persistência transacional — se eu atualizar a página agora, nada se perde — e mantemos uma trilha imutável. Mesmo se um chamado for reaberto, o histórico original da decisão permanece intacto para alimentar a matriz de calibração entre a IA e o time humano."

**Evidência:** `src/repositorio.py:65` (`tickets`) e `:80` (`eventos`); `reabrir()` em `:189` preserva `resolvido_por`, `resolvido_em` e `resposta_final`, conforme o teste `test_reabrir_nao_apaga_auditoria`. O JSONL permanece como trilha analítica; `decisoes_vigentes()` em `src/painel.py:140` descarta a decisão substituída e a matriz considera só a vigente após a reabertura. Placar da nova medição instrumentada: 32/36 (89%) em intenção e 27/36 (75%) em urgência, com "Fallbacks: nenhum" (0 fallbacks). A medição final da suíte é de **278 testes coletados** (`pytest --collect-only -q`), atualizada em 27/11/2026.

## Bloco 5 — Padrão Corporativo e Encerramento (3:30 – 4:00)

**Ação na tela:** No topo direito, alterne o idioma de PT para EN e mude rapidamente entre Modo Claro e Escuro.

**O que dizer:**
> "Por fim, toda a camada visual foi inspirada na identidade da DXC, preparada para operações globais com suporte nativo a múltiplos idiomas, temas claro e escuro e uma base coberta por 278 testes automatizados garantindo estabilidade a cada evolução."

**Evidência:** o seletor PT/EN fica em `st.columns([9.4, 1.6])` no topo da área principal e chama `render_language_selector()` (módulo `src/tema_dxc.py`); o tema Claro/Escuro é o `segmented_control` `tema_ui` na sidebar, que chama `render_dxc_theme()` e `render_dxc_logo()`. A identidade visual (CSS, SVG) foi isolada em `src/tema_dxc.py` sem duplicação; as 201 chaves de topo e 228 entradas-folha por idioma ficam em `src/textos.py`. Suíte validada: **278 testes coletados** (`pytest --collect-only -q`).

## Ajustes aplicados ao texto sugerido

1. **Bloco 1:** "contexto completo" virou "contexto operacional completo, com os dados pessoais mascarados na origem". O analista não vê os dados sensíveis; vê o contexto da ocorrência já mascarado.
2. **Bloco 5:** o número acompanhou as entregas: 115 (antes da integração SQLite) → 129 (após a extração do tema) → 199 (após a cobertura das telas com `AppTest`) → 211 (no HEAD `b7a1748`) → 213 → **250** na medição atual, medido com `pytest --collect-only -q`. Os valores antigos ficam apenas como histórico.
3. Os demais blocos foram mantidos como enviados — todos possuem evidência direta no código.

## Visão futura (fora do MVP) — Portão de Autonomia e Central de Solução

Esta seção registra a direção discutida para fases posteriores. Ela **não faz parte da demo de 4 minutos** e não propõe alteração de código, de contrato ou de comportamento do MVP. [Fonte: instrução do usuário nesta conversa, 2026-11-23]

### 1. Estado atual: decisão 100% humana

> "Visão futura (desligado no MVP): Portão de Autonomia. No MVP (v2), todas as decisões permanecem 100% humanas. O módulo `src/autonomia.py` (portão estatístico Clopper-Pearson) permanece guardado no repositório para fases futuras, quando houver volume real de chamados e modelos treinados." [Fonte: instrução do usuário nesta conversa, 2026-11-23]

O portão estatístico está pausado na interface (`README.md:33`) e o cálculo Clopper-Pearson está descrito em `src/autonomia.py:10`. O princípio do fluxo permanece: "a IA só sugere; nada é enviado" (`src/painel.py:4`).

### 2. O que a Análise Contextual já entrega hoje

Exemplo citado: chamado com prazo "até o meio-dia", processo crítico "nota fiscal", "Todos" afetados, bloqueio "parados" e palavra-chave "acesso". [Fonte: instrução do usuário nesta conversa, 2026-11-23]

> 1 - CHAMADO: Análise Contextual (1 hipótese)\
> Pode ser que, além da correção, ajude uma solução provisória para cumprir o prazo mencionado. (Média)\
> Confirmar: Existe um caminho provisório que ajudaria a cumprir esse prazo antes da correção definitiva?

A hipótese e a pergunta de confirmação surgem quando há sinal de prazo e o texto não pede solução provisória (`src/percepcao.py:95-104`); a confiança `media` está em `src/percepcao.py:101`. A análise foi escrita antes do ajuste de nomenclatura, quando a tela se chamava "Percepção". Hoje a interface usa `txt["perception"]` = "Análise Contextual" / "Contextual Insight" (`src/textos.py:127,373`), e "Percepção" permanece apenas como nome técnico do módulo.

O "(Média)" é o grau de confiança da heurística: um palpite da IA, não um diagnóstico. Essa natureza deve continuar explícita em qualquer evolução.

### 3. Direção compatível com a proposta: trazer alternativas do material do setor

A visão descrita é que a Análise Contextual não apenas aponte a necessidade não dita, mas traga à analista alternativas já existentes em um material do setor — por exemplo, um script que a equipe usa para resolver demandas recorrentes —, indicando o trecho útil para que Marina leia, fique ciente e decida. [Fonte: instrução do usuário nesta conversa, 2026-11-23]

Isso é compatível com o desenho atual: continua sendo sugestão apresentada ao humano, sem envio automático. Hoje **não existe base de conhecimento no projeto**; seria uma frente nova, a ser especificada separadamente, com definição de quais materiais podem ser consultados e como a origem da sugestão seria registrada na auditoria.

### 4. O que fica de fora: chamada automática à central de solução

A visão também descreve um número da central de solução que, ao ser acionado, faria uma chamada, com Marina aguardando o retorno e enviando o caso para o setor resolver em tempo real. [Fonte: instrução do usuário nesta conversa, 2026-11-23]

Esse ponto **não entra na proposta atual**. Ele conflita com o princípio "a IA só sugere; nada é enviado" (`src/painel.py:4`) e com o portão de autonomia desligado no MVP (`README.md:33`). Ligar telefonia e enviar o caso é ação externa com efeito real, além de envolver gravação e LGPD — é decisão de produto, não ajuste de interface. Fica registrado como possibilidade futura, dependente de volume real de chamados, modelo treinado e definição clara de quem autoriza o envio.

### 5. Atualização das medidas desde a redação original

O Bloco 5 passou a registrar 250 testes, com o histórico de 115, 129, 199, 211 e 213 mantido no item 2 de "Ajustes aplicados ao texto sugerido". Após as entregas de UI/UX (`d7b9bc4`), de paridade PT/EN (`c756adc`), da cobertura de fallbacks (`c9216f4`), do CI (`c8a7352`), do ajuste final de temas e tabelas (`62d4b6c`), da validação do JSONL de auditoria (`664ae9a`), do isolamento dos contadores do LLM (`d6f51c5`), da rastreabilidade do estado anterior no SQLite (`8b04f59`), da unificação do núcleo do pipeline (`2d63d13`), das correções de execução da CLI (`c02cce1`) e da cobertura das telas com `AppTest` (`66375bb`), além de `ed8f6f3` (responsividade da cascata e da legenda), `18636bd` (reuso do cliente Gemini por chave), `dc15e11` (`import os` no topo de `config.py`) e `b7a1748` (preservação de navegação, motor e toggle na troca de idioma), a cobertura do estado por chamado na troca PT/EN e as entregas de UI do Acervo (`166722c`, `666736e`) elevam a medição local a **250 testes coletados** (`pytest --collect-only -q`); a correção do teste de fuso horário (`05e8d41`) estabilizou o CI, concluído com `success` no run `#29`. `ruff check app.py src tests`, `compileall` e os 5 testes de fallbacks também passaram, e `src/ui_comum.py` chegou a 100% de cobertura; a frente de UI/UX validou 24 gráficos Altair em PT/EN e nos modos Claro e Escuro, além do ícone `?` vazado e das tabelas da aba Calibração no Modo Claro. As referências de linha dos blocos anteriores refletem a versão dos arquivos na época da redação.

A nova medição com instrumentação de motivos (`rodar_comparativo.ps1`, 2026-11-23) registrou `Origem: gemini=36 | regras=0 | fallback=0` e `Fallbacks: nenhum`, com 32/36 (89%) em intenção e 27/36 (75%) em urgência. Os 8 fallbacks da medição anterior não foram reproduzidos e seguem sem causa classificada; os números antigos ficam apenas como histórico.

## [Complemento Externo] — Evoluções de produto rumo a piloto operacional real

Seção separada conforme a regra de rastreabilidade. O conteúdo abaixo veio de material externo fornecido por você, não do repositório: não é evidência do código atual, não faz parte da demo de 4 minutos e não altera o MVP. [Fonte: material externo fornecido pelo usuário, 2026-11-23]

- Fluxo bilíngue real ponta a ponta (atendimento PT ↔ EN): detectar automaticamente o idioma do chamado do cliente; se chegar em inglês, traduzir para a analista responder em português e traduzir/revisar a resposta final para inglês antes de registrar — guardando ambas as versões em Finalizados e estendendo máscara + guardrail (mascara.py, redator.py) para regras em inglês.
- RAG com base de conhecimento (runbooks / KBs) sob a mesma regra "sem fonte, sem sugestão": permitir que a Análise Contextual e o Redator OARS sugiram contornos provisórios reais citando o código do artigo interno (ex.: [KB-1042]), sem inventar procedimentos.
- Conectores ITSM e multiusuário real: criar adaptadores para ServiceNow, Jira Service Management ou Zendesk, trocar SQLite local por PostgreSQL em ambiente compartilhado e substituir os nomes fixos "Marina" / "Rafael" por autenticação (SSO/OAuth) com perfis de permissão (analista vs. gestor).
- Adaptador de LLM local/privado (Ollama / vLLM / Azure OpenAI): aproveitando que llm.py já é desacoplado por adaptadores, suportar modelos hospedados internamente para clientes corporativos com restrição estrita de tráfego externo.
- Observabilidade operacional no painel do Rafael: acompanhar SLA por prioridade, tempo médio de decisão da analista por etapa, taxa de fallback por motivo ao longo do tempo e custo estimado de tokens por chamado.
