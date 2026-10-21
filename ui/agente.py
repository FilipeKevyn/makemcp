"""Agente simulado: entende comandos em pt-BR por regras (sem LLM).

A peça central deste módulo é a **interface de eventos**: todo agente (este
simulado ou `AgenteLLM`, em `ui/agente_llm.py`) expõe um método
``processar(mensagem, cliente)`` que devolve um *iterador* de eventos, sempre
na mesma ordem lógica de um turno:

    EventoChamadaTool  -> EventoResultadoTool -> ... -> EventoTextoFinal

Isso é o que garante, na UI, que o cartão da tool apareça **antes** da
resposta final (e que várias tools no mesmo turno apareçam em ordem). Trocar
o agente por um LLM de verdade no futuro não exige mudar `ui/app.py`: basta
implementar a mesma assinatura.

Só o "entendimento" da frase é simulado (por expressões regulares); as tools
chamadas são sempre as tools **reais** do servidor MCP, via `cliente`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator, Protocol

from cliente_mcp import ErroClienteMCP


@dataclass(frozen=True)
class EventoChamadaTool:
    nome: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class EventoResultadoTool:
    nome: str
    ok: bool
    conteudo: Any


@dataclass(frozen=True)
class EventoTextoFinal:
    texto: str


Evento = EventoChamadaTool | EventoResultadoTool | EventoTextoFinal


class ClienteTools(Protocol):
    """O único contrato que um agente precisa do cliente MCP."""

    def chamar_tool(self, nome: str, argumentos: dict[str, Any]) -> Any: ...


TEXTO_AJUDA = (
    "Não entendi esse comando. Comandos que eu entendo:\n\n"
    "- **criar**: `crie uma tarefa chamada <título>` ou "
    "`crie a tarefa <título> com descrição <descrição>`\n"
    "- **listar**: `liste as tarefas` ou `minhas tarefas`\n"
    "- **obter**: `mostre a tarefa <id>` ou `detalhes da tarefa <id>`\n"
    "- **atualizar**: `atualize o título da tarefa <id> para <novo título>` ou "
    "`mude a descrição da tarefa <id> para <nova descrição>`\n"
    "- **concluir**: `conclua a tarefa <id>` ou `desmarque a tarefa <id>`\n"
    "- **remover**: `remova a tarefa <id>`\n"
    "- **ajuda**: `ajuda`"
)


def _resumir(conteudo: Any) -> str:
    """Resumo em pt-BR de uma tarefa (ou lista) devolvida por uma tool."""
    if isinstance(conteudo, dict) and "titulo" in conteudo:
        situacao = " (concluída)" if conteudo.get("concluido") else ""
        return f"id {conteudo['id']}: {conteudo['titulo']}{situacao}"
    return str(conteudo)


class AgenteSimulado:
    """Interpreta comandos em pt-BR por regex e chama as tools reais do MCP."""

    def processar(self, mensagem: str, cliente: ClienteTools) -> Iterator[Evento]:
        texto = mensagem.strip()

        intencao = (
            self._tentar_criar(texto)
            or self._tentar_listar(texto)
            or self._tentar_obter(texto)
            or self._tentar_atualizar(texto)
            or self._tentar_concluir(texto)
            or self._tentar_remover(texto)
            or self._tentar_ajuda(texto)
        )

        if intencao is None:
            yield EventoTextoFinal(TEXTO_AJUDA)
            return

        nome_tool, argumentos, resumir_sucesso = intencao
        yield EventoChamadaTool(nome=nome_tool, argumentos=argumentos)
        try:
            resultado = cliente.chamar_tool(nome_tool, argumentos)
        except ErroClienteMCP as erro:
            yield EventoResultadoTool(nome=nome_tool, ok=False, conteudo=str(erro))
            yield EventoTextoFinal(f"Não consegui: {erro}")
            return

        yield EventoResultadoTool(nome=nome_tool, ok=True, conteudo=resultado)
        yield EventoTextoFinal(resumir_sucesso(resultado))

    # --- Reconhecimento de intenções (cada método devolve None se não casar) ---

    def _tentar_ajuda(self, texto: str):
        if re.fullmatch(r"(?i)\s*ajuda\s*[?!.]*\s*", texto):
            return ("__ajuda__", {}, lambda r: TEXTO_AJUDA)
        return None

    def _tentar_criar(self, texto: str):
        padrao = re.compile(
            r"(?i)\b(crie|criar|adicion\w*|anot\w*)\b.*?"
            r"(?:tarefa\s+)?chamad[ao]\s+(?P<titulo_a>.+?)"
            r"(?:\s+com\s+descri[cç][aã]o\s+(?P<descricao>.+))?$"
        )
        m = padrao.search(texto)
        if not m:
            padrao_simples = re.compile(
                r"(?i)\b(crie|criar|adicion\w*|anot\w*)\b\s+(?:a\s+)?tarefa\s+"
                r"(?P<titulo_b>.+?)"
                r"(?:\s+com\s+descri[cç][aã]o\s+(?P<descricao2>.+))?$"
            )
            m = padrao_simples.search(texto)
            if not m:
                return None
            titulo = m.group("titulo_b").strip()
            descricao = (m.group("descricao2") or "").strip()
        else:
            titulo = m.group("titulo_a").strip()
            descricao = (m.group("descricao") or "").strip()

        if not titulo:
            return None

        def resumir(resultado: Any) -> str:
            return f"Tarefa criada com {_resumir(resultado)}."

        return ("tarefas_criar", {"titulo": titulo, "descricao": descricao}, resumir)

    def _tentar_listar(self, texto: str):
        if re.search(r"(?i)\b(liste|listar|minhas\s+tarefas)\b", texto):
            def resumir(resultado: Any) -> str:
                if not resultado:
                    return "Você não tem nenhuma tarefa ainda."
                linhas = "\n".join(f"- {_resumir(t)}" for t in resultado)
                return f"Você tem {len(resultado)} tarefa(s):\n\n{linhas}"

            return ("tarefas_listar", {}, resumir)
        return None

    def _extrair_id(self, texto: str) -> int | None:
        m = re.search(r"tarefa\s+(?:de\s+id\s+)?(\d+)", texto, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"\bid\s+(\d+)", texto, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def _tentar_obter(self, texto: str):
        if not re.search(r"(?i)\b(mostre|mostrar|ver|veja|obtenha|obter|detalhes)\b", texto):
            return None
        id_tarefa = self._extrair_id(texto)
        if id_tarefa is None:
            return None

        def resumir(resultado: Any) -> str:
            return f"Tarefa encontrada — {_resumir(resultado)}."

        return ("tarefas_obter", {"id": id_tarefa}, resumir)

    def _tentar_atualizar(self, texto: str):
        if not re.search(r"(?i)\b(atualiz\w*|mud\w*|altere|edite)\b", texto):
            return None
        id_tarefa = self._extrair_id(texto)
        if id_tarefa is None:
            return None

        campos: dict[str, Any] = {}
        m_titulo = re.search(
            r"(?i)t[ií]tulo.*?\bpara\s+(?P<valor>.+)", texto
        )
        m_descricao = re.search(
            r"(?i)descri[cç][aã]o.*?\bpara\s+(?P<valor>.+)", texto
        )
        if m_titulo:
            campos["titulo"] = m_titulo.group("valor").strip()
        if m_descricao:
            campos["descricao"] = m_descricao.group("valor").strip()

        if not campos:
            return None

        def resumir(resultado: Any) -> str:
            return f"Tarefa atualizada — {_resumir(resultado)}."

        return ("tarefas_atualizar", {"id": id_tarefa, **campos}, resumir)

    def _tentar_concluir(self, texto: str):
        if not re.search(
            r"(?i)\b(conclu\w*|desmarqu\w*|marque\w*\s+como\s+conclu[íi]da)\b", texto
        ):
            return None
        id_tarefa = self._extrair_id(texto)
        if id_tarefa is None:
            return None

        argumentos: dict[str, Any] = {"id": id_tarefa}
        if re.search(r"(?i)\bdesmarqu\w*\b", texto):
            argumentos["concluido"] = False
        elif re.search(r"(?i)\bconclu\w*\b|\bmarque\w*\b", texto):
            argumentos["concluido"] = True

        def resumir(resultado: Any) -> str:
            return f"Tarefa atualizada — {_resumir(resultado)}."

        return ("tarefas_concluir", argumentos, resumir)

    def _tentar_remover(self, texto: str):
        if not re.search(r"(?i)\b(remov\w*|apague\w*|exclu\w*|delete\w*)\b", texto):
            return None
        id_tarefa = self._extrair_id(texto)
        if id_tarefa is None:
            return None

        def resumir(resultado: Any) -> str:
            return f"Tarefa {id_tarefa} removida."

        return ("tarefas_remover", {"id": id_tarefa}, resumir)
