"""Sessão MCP (stdio) usada pela UI, viva por todo o processo do Streamlit.

O Streamlit reexecuta o script do zero a cada interação (rerun), mas uma
sessão MCP é assíncrona e precisa ficar viva entre esses reruns — não dá para
abrir e fechar o subprocesso do servidor MCP a cada mensagem do chat. A saída
usada aqui: uma *thread própria* com seu próprio event loop asyncio, onde a
sessão é aberta uma única vez; o restante do app (síncrono) conversa com essa
thread via ``run_coroutine_threadsafe``. A instância fica cacheada por
processo com ``st.cache_resource``, então todos os reruns reaproveitam a
mesma sessão (e o mesmo subprocesso do servidor MCP).
"""

from __future__ import annotations

import asyncio
import os
import shlex
import sys
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

#: Tempo máximo de espera por uma chamada de tool (a API já tem seu próprio
#: timeout mais curto; esta margem cobre o round-trip completo via stdio).
TIMEOUT_TOOL = 30.0


@dataclass(frozen=True)
class FerramentaMCP:
    """Descrição mínima de uma tool, no formato que o agente precisa."""

    nome: str
    descricao: str
    parametros: dict[str, Any]


class ErroClienteMCP(Exception):
    """Erro amigável (pt-BR) ao falar com o servidor MCP."""


def _comando_padrao() -> list[str]:
    """Comando default: o mesmo Python do projeto rodando o módulo do servidor."""
    comando = os.environ.get("MCP_COMANDO", sys.executable)
    args = os.environ.get("MCP_ARGS", "-m servidor_mcp.servidor")
    return [comando, *shlex.split(args)]


def _raiz_projeto() -> str:
    """Raiz do repositório (pai de ``ui/``), para o ``cwd`` e o ``PYTHONPATH``."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ClienteMCP:
    """Mantém uma sessão MCP (stdio) viva numa thread dedicada."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

        futuro = asyncio.run_coroutine_threadsafe(self._iniciar(), self._loop)
        try:
            futuro.result(timeout=TIMEOUT_TOOL)
        except Exception as erro:
            raise ErroClienteMCP(
                "Não consegui iniciar o servidor MCP. Confira se o comando "
                f"{_comando_padrao()!r} está correto e se a API está acessível "
                f"(detalhe: {erro})."
            ) from erro

    async def _iniciar(self) -> None:
        comando, *args = _comando_padrao()
        raiz = _raiz_projeto()
        env = {**os.environ, "PYTHONPATH": raiz}
        parametros = StdioServerParameters(
            command=comando, args=args, cwd=raiz, env=env
        )

        self._pilha = AsyncExitStack()
        leitura, escrita = await self._pilha.enter_async_context(
            stdio_client(parametros)
        )
        self._sessao = await self._pilha.enter_async_context(
            ClientSession(leitura, escrita)
        )
        await self._sessao.initialize()

    def _executar(self, corrotina) -> Any:
        futuro = asyncio.run_coroutine_threadsafe(corrotina, self._loop)
        return futuro.result(timeout=TIMEOUT_TOOL)

    def listar_tools(self) -> list[FerramentaMCP]:
        """Lista as tools do servidor (nome, descrição e JSON Schema)."""
        resultado = self._executar(self._sessao.list_tools())
        return [
            FerramentaMCP(
                nome=tool.name,
                descricao=tool.description or "",
                parametros=tool.input_schema,
            )
            for tool in resultado.tools
        ]

    def chamar_tool(self, nome: str, argumentos: dict[str, Any]) -> Any:
        """Chama uma tool pelo nome e devolve o payload (ou levanta ``ErroClienteMCP``)."""
        resultado = self._executar(self._sessao.call_tool(nome, argumentos))

        if resultado.is_error:
            raise ErroClienteMCP(_mensagem_erro(nome, resultado.content))

        conteudo = resultado.structured_content
        if isinstance(conteudo, dict) and list(conteudo.keys()) == ["result"]:
            # O MCP só aceita "object" como saída estruturada; um retorno que
            # já era uma lista (ex.: `tarefas_listar`) chega embrulhado em
            # {"result": [...]} — desembrulhamos para o formato original.
            return conteudo["result"]
        if conteudo is not None:
            return conteudo
        return _texto_conteudo(resultado.content)


def _texto_conteudo(blocos: list[Any]) -> str:
    """Junta os blocos de texto de um resultado MCP numa única string."""
    partes = [bloco.text for bloco in blocos if getattr(bloco, "type", None) == "text"]
    return "\n".join(partes) if partes else "(sem conteúdo)"


def _mensagem_erro(nome_tool: str, blocos: list[Any]) -> str:
    """Extrai a mensagem amigável de um erro de tool, sem o prefixo técnico."""
    texto = _texto_conteudo(blocos)
    prefixo = f"Error executing tool {nome_tool}: "
    if texto.startswith(prefixo):
        return texto[len(prefixo):]
    return texto


@st.cache_resource(show_spinner="Iniciando servidor MCP...")
def obter_cliente_mcp() -> ClienteMCP:
    """Instância única do cliente MCP para todo o processo do Streamlit."""
    return ClienteMCP()
