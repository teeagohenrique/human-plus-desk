"""Máscara de dados pessoais (LGPD): roda ANTES de qualquer agente ver o texto.

Camadas aplicadas nesta ordem, sempre offline:
- padrões com formato fixo: e-mail, CNPJ, CPF, telefone BR;
- heurística local de nomes com prefixos explícitos (Sr./Sra./Dr., "aqui é o",
  "meu nome é", "para a", "máquina da" etc.);
- NER local (Presidio + spaCy em português) para nomes fora desses prefixos,
  pela mesma interface `mascarar()`. Se o modelo falhar, a heurística anterior
  continua valendo.

NÃO valida os dígitos verificadores do CPF/CNPJ: mascara por formato (prefere
mascarar demais a vazar).
"""
import re

from pydantic import BaseModel

# A ordem importa: CNPJ (14 dígitos) antes de CPF (11), e CPF antes de telefone.
PADROES = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("CNPJ", re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")),
    ("CPF", re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")),
    ("TELEFONE", re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}(?!\d)")),
]

# Nome próprio simples ou composto (ex.: "Carlos", "Maria Clara", "João da Silva")
_PALAVRA_NOME = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{1,}"
_NOME_GRUPO = rf"({_PALAVRA_NOME}(?:\s+(?:(?:da|de|do|dos|das)\s+)?{_PALAVRA_NOME}){{0,2}})"

# Contextos explícitos onde um nome próprio de pessoa aparece em chamados de service desk.
# (?i:...) fica apenas no prefixo para que _NOME_GRUPO continue exigindo inicial maiúscula.
_PADROES_NOME = [
    re.compile(rf"\b((?:Sr\.?|Sra\.?|Srta\.?|Dr\.?|Dra\.?)\s+){_NOME_GRUPO}"),
    re.compile(rf"\b((?i:(?:aqui\s+é|sou|quem\s+fala\s+é)\s+(?:o|a))\s+){_NOME_GRUPO}"),
    re.compile(rf"\b((?i:(?:meu\s+nome\s+é|me\s+chamo|chamo-me))\s+){_NOME_GRUPO}"),
    re.compile(rf"\b((?i:(?:para\s+(?:o|a)|máquina\s+(?:do|da)|computador\s+(?:do|da)|usuário\s+(?:do|da)|conta\s+(?:do|da)))\s+){_NOME_GRUPO}"),
    re.compile(rf"\b((?i:(?:atenciosamente|att\.?|obrigad[oa]|abs\.?)),?\s+){_NOME_GRUPO}"),
]

# Termos capitalizados comuns em TI/negócio que não são nomes de pessoas.
_NAO_NOMES = {
    "Excel", "Word", "Outlook", "Teams", "Power", "Windows", "Linux", "Mac",
    "Google", "Microsoft", "Oracle", "Salesforce", "ServiceNow", "Zendesk",
    "Campinas", "Brasil", "Segunda", "Terça", "Quarta", "Quinta", "Sexta",
    "Sábado", "Domingo", "Janeiro", "Fevereiro", "Março", "Abril", "Maio",
    "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
}


class ResultadoMascara(BaseModel):
    texto: str
    tipos_encontrados: list[str]


def _mascarar_nomes(texto: str) -> tuple[str, int]:
    total = 0

    def _substituir(m: re.Match) -> str:
        nonlocal total
        prefixo, candidato = m.group(1), m.group(2)
        palavras = [p for p in candidato.split() if p not in ("da", "de", "do", "dos", "das")]
        if not palavras or all(p in _NAO_NOMES for p in palavras):
            return m.group(0)
        total += 1
        return f"{prefixo}[NOME]"

    for padrao in _PADROES_NOME:
        texto = padrao.sub(_substituir, texto)
    return texto, total


def _nomes_por_ner(texto: str) -> list[tuple[int, int]]:
    """Importa o NER sob demanda; indisponibilidade não derruba a máscara."""
    try:
        from src.ner_local import nomes_encontrados
    except Exception:
        return []
    return nomes_encontrados(texto)


def mascarar(texto: str) -> ResultadoMascara:
    encontrados: list[str] = []
    for tipo, padrao in PADROES:
        texto, n = padrao.subn(f"[{tipo}]", texto)
        encontrados.extend([tipo] * n)
    texto, n_nomes = _mascarar_nomes(texto)
    encontrados.extend(["NOME"] * n_nomes)
    for inicio, fim in reversed(_nomes_por_ner(texto)):
        trecho = texto[inicio:fim]
        if not trecho or all(palavra in _NAO_NOMES for palavra in trecho.split()):
            continue
        texto = texto[:inicio] + "[NOME]" + texto[fim:]
        encontrados.append("NOME")
    return ResultadoMascara(texto=texto, tipos_encontrados=encontrados)
