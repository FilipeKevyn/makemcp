"""Contratos comuns a qualquer provedor de LLM.

A ideia central: o resto do projeto (agente, UI) só conhece estes tipos e o
protocolo :class:`ClienteLLM` — nunca o formato de request/response de um
provedor específico. Isso é o que permite trocar de "Gemini via endpoint
compatível com OpenAI" para "Claude via API nativa da Anthropic" mudando só
o `.env`, sem tocar em ``ui/agente_llm.py``.

Cada provedor concreto (:mod:`ui.llm.anthropic_provider`,
:mod:`ui.llm.openai_compat`) implementa :class:`ClienteLLM` e decide sozinho
como traduzir ``FerramentaLLM``/``ChamadaFerramenta`` para o formato que a
sua API espera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ConfiguracaoLLM:
    """Os três dados que *qualquer* provedor de LLM precisa para responder.

    ``base_url``, ``modelo`` e ``chave`` vêm de variáveis de ambiente
    genéricas (``LLM_BASE_URL``, ``LLM_MODELO``, ``LLM_KEY``); o provedor é
    decidido a partir delas (veja :mod:`ui.llm.fabrica`), nunca hardcoded.
    """

    base_url: str
    modelo: str
    chave: str


@dataclass(frozen=True)
class FerramentaLLM:
    """Descrição de uma tool no formato neutro (independe do provedor)."""

    nome: str
    descricao: str
    #: JSON Schema dos argumentos (o mesmo que o MCP já publica).
    parametros: dict[str, Any]


@dataclass(frozen=True)
class ChamadaFerramenta:
    """Uma chamada de tool pedida pelo modelo."""

    id: str
    nome: str
    argumentos: dict[str, Any]


@dataclass
class ResultadoFerramenta:
    """O que devolvemos ao modelo após executar uma :class:`ChamadaFerramenta`."""

    chamada: ChamadaFerramenta
    ok: bool
    conteudo: Any = None
    erro: str | None = None


@dataclass
class RespostaLLM:
    """Resposta de um turno do modelo.

    ``texto`` é o que mostrar à pessoa (pode ser vazio quando o modelo só
    pediu tools). ``chamadas`` fica vazia quando o modelo terminou o turno.
    """

    texto: str = ""
    chamadas: list[ChamadaFerramenta] = field(default_factory=list)

    @property
    def pediu_ferramentas(self) -> bool:
        return bool(self.chamadas)


class ErroLLM(Exception):
    """Erro amigável (pt-BR) ao falar com o provedor de LLM."""


class ClienteLLM(Protocol):
    """Uma *conversa* com um provedor de LLM, do início ao fim de um turno.

    Uma instância é criada por turno do chat (veja ``ui.agente_llm``) e
    mantém o histórico internamente no formato nativo do provedor. O
    contrato tem só dois métodos porque é exatamente o que um turno precisa:
    começar com a mensagem da pessoa e, se o modelo pedir tools, continuar
    depois de executá-las.
    """

    def iniciar(
        self, mensagem_usuario: str, ferramentas: list[FerramentaLLM]
    ) -> RespostaLLM: ...

    def continuar(self, resultados: list[ResultadoFerramenta]) -> RespostaLLM: ...
