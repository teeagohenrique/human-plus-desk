# Fase futura: entrada por transcrição de áudio

Status: planejamento. O MVP atual não ingere nem transcreve áudio; `data/audios_simulados/` permanece apenas como diretório de referência. Nenhuma biblioteca de ASR foi adicionada.

## Escopo permitido

- Receber arquivos de áudio de simulação e produzir texto transcrito.
- Encaminhar somente o texto transcrito para o fluxo existente (`processar_chamado`), que aplica a máscara antes da triagem, percepção e qualquer provedor externo.
- Manter decisão, revisão e resposta final sob controle humano.

## Fora do escopo

- Inferir emoção, personalidade, intenção psicológica ou estado mental pela voz, prosódia, velocidade, volume ou características biométricas.
- Usar áudio bruto como entrada do Gemini ou de outro LLM.
- Tratar a transcrição automática como evidência perfeita ou substituir a confirmação da analista.

## Contrato proposto para uma implementação futura

Um adaptador isolado deverá receber um arquivo validado e devolver um objeto `Transcricao` com, no mínimo: texto, idioma detectado (se disponível), provedor/modelo, timestamp e avisos de baixa confiança. O adaptador não deve classificar urgência nem escrever no banco. A UI deverá mostrar a transcrição para revisão humana antes de chamar `processar_chamado`.

## Controles que precisam existir antes de implementar

1. Validar extensão, MIME real, tamanho máximo, duração e codec; rejeitar conteúdo incompatível sem executar mídia embutida.
2. Definir se o reconhecimento será local ou externo. Se externo, documentar transferência, retenção, região e controles do fornecedor antes de enviar qualquer áudio.
3. Nunca armazenar o binário por padrão. Se a simulação precisar preservá-lo, definir prazo de retenção e remoção explícita.
4. Manter o áudio fora dos logs; registrar somente metadados mínimos e o texto após a máscara.
5. Fazer a máscara rodar sobre a transcrição antes de LLMs. Se a máscara estiver incompleta, usar regras locais e não enviar o texto externamente.
6. Informar que a transcrição pode conter erros e exigir revisão humana antes da triagem ou resposta.
7. Cobrir testes para arquivo inválido, falha/baixa confiança do ASR, ausência de envio do áudio bruto, máscara da transcrição e proibição de análise emocional.

A dependência de transcrição (por exemplo, Whisper) só deverá entrar quando essa fase for aprovada e seus controles puderem ser verificados. Até lá, áudio e análise de emoção continuam explicitamente fora do produto.
