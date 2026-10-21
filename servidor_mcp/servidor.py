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

# O ``httpx`` também loga cada requisição HTTP em INFO; aqui queremos destacar
# apenas as chamadas de tool, então baixamos o nível dele.
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
    """Cria uma nova tarefa e devolve a tarefa criada, já com o id.

    Exemplos de uso:
    - "crie uma tarefa chamada Comprar leite" -> titulo="Comprar leite"
    - "crie a tarefa Comprar leite com descrição dois litros" ->
      titulo="Comprar leite", descricao="dois litros"

    Erros: título vazio é rejeitado pela API (422) e vira um erro amigável.
    """
    logger.info("tool tarefas_criar chamada com %s", {"titulo": titulo})
    return await cliente_api.requisitar(
        "POST", "/tarefas", json={"titulo": titulo, "descricao": descricao}
    )


@mcp.tool(
    title="Listar tarefas",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def tarefas_listar() -> list[dict[str, Any]]:
    """Lista todas as tarefas, em ordem de criação.

    Use quando o usuário pedir "liste as tarefas" ou "o que tenho para fazer".
    Devolve uma lista (possivelmente vazia) de tarefas com id, titulo,
    descricao e concluido.
    """
    logger.info("tool tarefas_listar chamada")
    return await cliente_api.requisitar("GET", "/tarefas")


@mcp.tool(
    title="Obter tarefa por id",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def tarefas_obter(id: int) -> dict[str, Any]:
    """Devolve uma tarefa específica pelo seu id.

    Exemplo de uso: "mostre a tarefa 2" -> id=2.
    Erros: se a tarefa não existir, retorna um erro amigável ("Tarefa N não
    encontrada").
    """
    logger.info("tool tarefas_obter chamada com %s", {"id": id})
    return await cliente_api.requisitar("GET", f"/tarefas/{id}", tarefa_id=id)


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
    """Atualiza parcialmente uma tarefa: título e/ou descrição.

    Informe ao menos um dos campos; o campo omitido permanece como estava.
    Exemplos de uso:
    - "atualize o título da tarefa 2 para Comprar pão" -> id=2,
      titulo="Comprar pão"
    - "mude a descrição da tarefa 2 para dois litros" -> id=2,
      descricao="dois litros"

    Erros: id inexistente e payload sem nenhum campo viram erros amigáveis.
    """
    campos: dict[str, Any] = {}
    if titulo is not None:
        campos["titulo"] = titulo
    if descricao is not None:
        campos["descricao"] = descricao
    logger.info("tool tarefas_atualizar chamada com %s", {"id": id, **campos})
    return await cliente_api.requisitar(
        "PATCH", f"/tarefas/{id}", json=campos, tarefa_id=id
    )


@mcp.tool(
    title="Concluir ou desmarcar tarefa",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        # Sem ``concluido`` a tool alterna o estado, então repetir a mesma
        # chamada pode mudar o resultado — por isso não é idempotente.
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
async def tarefas_concluir(
    id: int,
    concluido: bool | None = None,
) -> dict[str, Any]:
    """Marca uma tarefa como concluída, desmarca ou alterna o estado.

    Um único endpoint serve aos dois usos:
    - "conclua a tarefa 2" / "marque a tarefa 2 como concluída" -> id=2,
      concluido=True
    - "desmarque a tarefa 2" -> id=2, concluido=False
    - quando ``concluido`` é omitido, o estado atual é **alternado**
      (``true`` vira ``false`` e vice-versa) -> id=2

    Devolve a tarefa com o novo valor de ``concluido``. Erros: id inexistente
    retorna "Tarefa N não encontrada".
    """
    corpo: dict[str, Any] = {}
    if concluido is not None:
        corpo["concluido"] = concluido
    logger.info("tool tarefas_concluir chamada com %s", {"id": id, **corpo})
    return await cliente_api.requisitar(
        "PATCH", f"/tarefas/{id}/concluido", json=corpo, tarefa_id=id
    )


@mcp.tool(
    title="Remover tarefa",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def tarefas_remover(id: int) -> dict[str, Any]:
    """Remove uma tarefa pelo id.

    Exemplo de uso: "remova a tarefa 3" -> id=3.
    Erros: remover um id inexistente retorna "Tarefa N não encontrada".
    """
    logger.info("tool tarefas_remover chamada com %s", {"id": id})
    await cliente_api.requisitar("DELETE", f"/tarefas/{id}", tarefa_id=id)
    return {"id": id, "removido": True}


def main() -> None:
    """Sobe o servidor MCP no transporte stdio (padrão da demo)."""
    logger.info("iniciando servidor MCP em stdio (API em %s)", cliente_api.API_URL)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
