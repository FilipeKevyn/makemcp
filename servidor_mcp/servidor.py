"""Servidor MCP (transporte stdio) com as tools de tarefas do minicurso.

O servidor expõe seis tools que operam a API de tarefas por HTTP. Em outras
palavras: o agente/LLM fala MCP, o MCP fala HTTP com a API — e cada camada
pode ser inspecionada separadamente.

Cada tool é só uma casca fina: monta o método e o caminho do endpoint e delega
a chamada HTTP (e a tradução de erros) para ``cliente_api.requisitar``.

Como rodar (a partir da raiz do projeto)::

    uv run python -m servidor_mcp.servidor

Com o transporte stdio, o ``stdout`` pertence ao protocolo MCP; por isso todo
log vai para o ``stderr`` (dá para ver o "lado do servidor" sem quebrar a
comunicação). A base da API é lida de ``API_URL`` em ``cliente_api.py``.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import cliente_api

logger = logging.getLogger("servidor_mcp")
if not logger.handlers: 
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [MCP] %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = MCPServer(
    "tarefas-mcp",
    instructions=(
        "Servidor MCP didático que opera uma API de tarefas (TO-DO).\n\n"
        "Cada tarefa tem id (inteiro, gerado pela API), titulo (texto não "
        "vazio), descricao (texto, pode ser vazio) e concluido (booleano, "
        "começa como falso). Use as tools tarefas_* para criar, listar, obter, "
        "atualizar, concluir/desmarcar e remover tarefas; a API fica em "
        "API_URL e reiniciar seu processo zera "
        "todos os ids."
    ),
)


@mcp.tool(
    title="Criar tarefa",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    )
)
async def tarefas_criar(titulo: str, descricao: str = "") -> dict[str, Any]:
    return {}


# @mcp.tool(
#     title="Listar tarefas",
#     annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
# )
# async def tarefas_listar() -> list[dict[str, Any]]:
#     """Lista todas as tarefas, em ordem de criação.

#     Use quando o usuário pedir "liste as tarefas" ou "o que tenho para fazer".
#     Devolve uma lista (possivelmente vazia) de tarefas com id, titulo,
#     descricao e concluido.
#     """
#     logger.info("tool tarefas_listar chamada")
#     return await cliente_api.requisitar("GET", "/tarefas")


@mcp.tool(
    title="Obter tarefa por id",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def tarefas_obter(id: int) -> dict[str, Any]:
    return {}


@mcp.tool(
    title="Atualizar tarefa",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def tarefas_atualizar(
    id: int,
    titulo: str | None = None,
    descricao: str | None = None,
) -> dict[str, Any]:
    return {}


@mcp.tool(
    title="...",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
async def tarefas_concluir_ou_desmarcar(
    id: int,
    concluido: bool | None = None,
) -> dict[str, Any]:
    return {}


@mcp.tool(
    title="...",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def tarefas_remover(id: int) -> dict[str, Any]:
    return {}


def main() -> None:
    """Sobe o servidor MCP no transporte stdio (padrão da demo)."""
    logger.info("iniciando servidor MCP em stdio (API em %s)", cliente_api.API_URL)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
