# Status do Projeto — Human + Desk (v2)

> *Revisão: 27 de novembro de 2026*

---

## 📍 Estado atual

Branch `main` alinhado com `origin/main` no commit `92bdb57`; as alterações desta rodada ainda não foram commitadas.
Working tree com mudanças pendentes (`git status`); nenhum push foi feito.
Suíte de testes: **274 passed**. Zero imports quebrados.
Line endings: os arquivos editados estão em LF. Os avisos do Git sobre `LF will be replaced by CRLF` decorrem de `core.autocrlf=true` nesta máquina; o repositório não tem `.gitattributes`.

---

## 📋 Etapas concluídas

| Etapa | Método | Resultado |
|---|---|---|
| **1 — Diagnóstico** | Mapeamento da stack, dependências desatualizadas, variáveis de ambiente, estrutura de pastas e fluxo atual. | Levantamento completo (`src/`, `tests/`, `data/`, `.github/`, `docs/`) e pontos de dor identificados. |
| **2 — Plano de refactor** | Definição da arquitetura (camadas separadas, contratos e testes), padrões de migração e checklist de qualidade. | Plano de execução com prioridade SOLID, validação robusta e cobertura de testes. |
| **3 — Núcleo/Core** | Refatoração dos módulos de negócio com SOLID, tipagem forte, logs estruturados, tratamento robusto de erros e validação rigorosa de entradas (`src/painel.py`, `src/triagem.py`, `src/redator.py`, `src/llm.py`, `src/auditoria.py`, `src/repositorio.py`, etc.). | Remoção de código morto e duplicado. **274 testes passando** (cobertura média 91%). Zero imports quebrados. |
| **4 — Utilitários e Testes** | Limpeza de funções duplicadas, manutenção de 274 testes, verificação de imports, dependências e `.env.example`. | Remoção de `decisao_por_texto` (redundante com `classificar_resposta`). Suíte completa verde. Build OK. `pip install -e .` ok. |

---

## 🔜 Próximos passos (prioridade)

1. Executar Gemini nos 50 casos do benchmark e registrar modelo, data, origem e fallbacks.
2. Ampliar para 100 casos com lote de teste reservado (sem ajustar regras/prompts).
3. Revisar rótulos V37–V50 com especialistas de service desk.
4. Antes de dados reais: autenticação/autorização, política de retenção, armazenamento protegido.
5. Reativar áudio transcrito: `docs/audio-transcricao-futura.md`.

---

## 📦 O que já está resolvido

- Sistema de máscara LGPD com NER local + fallback por regras.
- Painel Streamlit com dois modos (regras/gemini).
- Triagem com contador de origem e fallback detalhado.
- Auditoria em transação SQLite + outbox JSONL idempotente.
- Tema DXC com traduções PT/EN (201 chaves, 9 blocos, 228 entradas-folha).
- CI via GitHub Actions: Ruff, compilação e pytest em cada push/PR.
