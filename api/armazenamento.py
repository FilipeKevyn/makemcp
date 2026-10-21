from api.modelos import Tarefa, TarefaAtualizar, TarefaCriar


class ArmazenamentoTarefas:
    def __init__(self) -> None:
        self._tarefas: dict[int, Tarefa] = {}
        self._proximo_id = 1

    def criar(self, dados: TarefaCriar) -> Tarefa:
        tarefa = Tarefa(
            id=self._proximo_id,
            titulo=dados.titulo,
            descricao=dados.descricao,
            concluido=False,
        )
        self._tarefas[tarefa.id] = tarefa
        self._proximo_id += 1
        return tarefa

    def listar(self) -> list[Tarefa]:
        return list(self._tarefas.values())

    def obter(self, tarefa_id: int) -> Tarefa | None:
        return self._tarefas.get(tarefa_id)

    def atualizar(self, tarefa_id: int, dados: TarefaAtualizar) -> Tarefa | None:
        tarefa = self._tarefas.get(tarefa_id)
        if tarefa is None:
            return None
        if dados.titulo is not None:
            tarefa.titulo = dados.titulo
        if dados.descricao is not None:
            tarefa.descricao = dados.descricao
        return tarefa

    def definir_concluido(
        self, tarefa_id: int, concluido: bool | None
    ) -> Tarefa | None:
        tarefa = self._tarefas.get(tarefa_id)
        if tarefa is None:
            return None
        if concluido is None:
            tarefa.concluido = not tarefa.concluido
        else:
            tarefa.concluido = concluido
        return tarefa

    def remover(self, tarefa_id: int) -> bool:
        return self._tarefas.pop(tarefa_id, None) is not None
