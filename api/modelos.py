from pydantic import BaseModel, ConfigDict, Field, model_validator


class Tarefa(BaseModel):
    """Uma tarefa armazenada na API."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "titulo": "Comprar leite",
                    "descricao": "Dois litros e um pão",
                    "concluido": False,
                }
            ]
        }
    )

    id: int = Field(description="Identificador único, gerado automaticamente pela API")
    titulo: str = Field(min_length=1, description="Título da tarefa (nunca vazio)")
    descricao: str = Field(description="Descrição livre (pode ser vazia)")
    concluido: bool = Field(
        default=False,
        description="Indica se a tarefa já foi concluída (começa como falsa)",
    )


class TarefaCriar(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"titulo": "Comprar leite", "descricao": "Dois litros e um pão"},
                {"titulo": "Lavar o carro"},
            ]
        }
    )

    titulo: str = Field(
        min_length=1,
        description="Título da tarefa (obrigatório e não vazio)",
    )
    descricao: str = Field(
        default="",
        description="Descrição livre (opcional; quando omitida, fica vazia)",
    )


class TarefaAtualizar(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"titulo": "Comprar leite desnatado"},
                {"descricao": "Trocar por leite vegetal"},
            ]
        }
    )

    titulo: str | None = Field(
        default=None,
        min_length=1,
        description="Novo título (não pode ser vazio)",
    )
    descricao: str | None = Field(
        default=None,
        description="Nova descrição",
    )

    @model_validator(mode="after")
    def exigir_pelo_menos_um_campo(self) -> "TarefaAtualizar":
        """Rejeita (422) payload sem nenhum campo útil para atualizar."""
        if self.titulo is None and self.descricao is None:
            raise ValueError(
                "Informe ao menos um campo para atualizar: 'titulo' e/ou 'descricao'"
            )
        return self


class TarefaConcluir(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"concluido": True},
                {"concluido": False},
            ]
        }
    )

    concluido: bool | None = Field(
        default=None,
        description=(
            "Novo estado de conclusão; quando omitido, alterna o valor atual"
        ),
    )
