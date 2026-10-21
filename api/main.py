from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, status

from api.armazenamento import ArmazenamentoTarefas
from api.modelos import Tarefa, TarefaAtualizar, TarefaConcluir, TarefaCriar

# --- Armazenamento

_armazenamento = ArmazenamentoTarefas()


def obter_armazenamento() -> ArmazenamentoTarefas:
    """Dependência do FastAPI que devolve o armazenamento único da aplicação.

    Em produção trocaríamos isso por um banco de dados; aqui o dicionário em
    memória deixa o caminho visível para quem está aprendendo.
    """
    return _armazenamento

DependenciaArmazenamento = Annotated[
    ArmazenamentoTarefas, Depends(obter_armazenamento)
]

# --- Rotas

router = APIRouter(prefix="/tarefas", tags=["tarefas"])

IdTarefa = Annotated[int, Path(description="Id numérico da tarefa")]


def _erro_nao_encontrada(tarefa_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Tarefa {tarefa_id} não encontrada",
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Cria uma tarefa")
def criar_tarefa(dados: TarefaCriar, armazenamento: DependenciaArmazenamento) -> Tarefa:
    return armazenamento.criar(dados)


@router.get("", summary="Lista todas as tarefas")
def listar_tarefas(armazenamento: DependenciaArmazenamento) -> list[Tarefa]:
    return armazenamento.listar()


@router.get("/{tarefa_id}", summary="Obtém uma tarefa pelo id")
def obter_tarefa(
    tarefa_id: IdTarefa, armazenamento: DependenciaArmazenamento
) -> Tarefa:
    tarefa = armazenamento.obter(tarefa_id)
    if tarefa is None:
        raise _erro_nao_encontrada(tarefa_id)
    return tarefa


@router.patch("/{tarefa_id}", summary="Atualiza título e/ou descrição")
def atualizar_tarefa(
    tarefa_id: IdTarefa,
    dados: TarefaAtualizar,
    armazenamento: DependenciaArmazenamento,
) -> Tarefa:
    tarefa = armazenamento.atualizar(tarefa_id, dados)
    if tarefa is None:
        raise _erro_nao_encontrada(tarefa_id)
    return tarefa


@router.patch(
    "/{tarefa_id}/concluido",
    summary="Marca como concluída ou desmarca",
)
def concluir_tarefa(
    tarefa_id: IdTarefa,
    armazenamento: DependenciaArmazenamento,
    dados: TarefaConcluir | None = None,
) -> Tarefa:
    concluido = dados.concluido if dados is not None else None
    tarefa = armazenamento.definir_concluido(tarefa_id, concluido)
    if tarefa is None:
        raise _erro_nao_encontrada(tarefa_id)
    return tarefa


@router.delete(
    "/{tarefa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove uma tarefa",
)
def remover_tarefa(
    tarefa_id: IdTarefa, armazenamento: DependenciaArmazenamento
) -> None:
    if not armazenamento.remover(tarefa_id):
        raise _erro_nao_encontrada(tarefa_id)


# --- Aplicação

app = FastAPI(
    title="API de Tarefas — Minicurso MCP",
    description=(
        "API didática de tarefas (TO-DO) do minicurso de MCP, com CRUD completo "
        "e armazenamento em memória (reiniciar o processo zera os dados). "
        "Explore e teste as rotas interativamente em `/docs`."
    ),
    version="0.1.0",
    openapi_tags=[
        {
            "name": "tarefas",
            "description": (
                "Operações de CRUD das tarefas: criar, listar, obter, "
                "atualizar parcialmente, concluir/desmarcar e remover."
            ),
        }
    ],
)

app.include_router(router)
