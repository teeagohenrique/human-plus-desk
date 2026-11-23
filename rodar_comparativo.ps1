# Comparativo regras vs Gemini no conjunto de validacao independente.
# Uso: abra o PowerShell na pasta do projeto, defina GEMINI_API_KEY e rode:
#     .\rodar_comparativo.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not $env:GEMINI_API_KEY) {
    Write-Error 'Defina GEMINI_API_KEY nesta janela antes de rodar: $env:GEMINI_API_KEY = "sua_chave"'
}

# ID do modelo (nao e a versao do pacote google-genai).
$env:GEMINI_MODEL = "gemini-3.8-flash"

Write-Output "Modelo: $env:GEMINI_MODEL"

& .\.venv\Scripts\python.exe -m src.main --avaliar data/chamados_validacao_independente.json --provider regras
& .\.venv\Scripts\python.exe -m src.main --avaliar data/chamados_validacao_independente.json --provider gemini
