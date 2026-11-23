# Comparativo regras vs Gemini no conjunto de validacao independente.
# Uso: abra o PowerShell na pasta do projeto, defina GEMINI_API_KEY e rode:
#     .\rodar_comparativo.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    Write-Error 'Crie o arquivo .env na raiz com GEMINI_API_KEY e GEMINI_MODEL antes de rodar.'
}

# Modelo e chave vem do .env, carregado por src.main (arquivo ignorado pelo git).
Write-Output "Modelo e chave: lidos de .env"

& .\.venv\Scripts\python.exe -m src.main --avaliar data/chamados_validacao_independente.json --provider regras
& .\.venv\Scripts\python.exe -m src.main --avaliar data/chamados_validacao_independente.json --provider gemini
