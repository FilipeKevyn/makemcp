"""Provedor de LLM para a API nativa da Anthropic (Claude), via SDK oficial.

Usa ``client.messages.create`` (Messages API), não um endpoint "compatível
com OpenAI" — a Anthropic não expõe um. As diferenças de formato ficam todas
escondidas aqui dentro:

- autenticação é ``x-api-key`` (o SDK cuida disso a partir de ``api_key``);
- ``system`` é um parâmetro próprio, não uma mensagem na lista;
- tools usam ``input_schema`` (não ``parameters``);
- a resposta vem em blocos de conteúdo (``text`` / ``tool_use``), não em
  ``message.tool_calls``;
- o resultado de uma tool volta como um bloco ``tool_result`` dentro de uma
  mensagem ``user`` (não como uma mensagem de papel ``tool``).
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from .base import (
    ChamadaFerramenta,
    ClienteLLM,
    ConfiguracaoLLM,
    ErroLLM,
    FerramentaLLM,
    RespostaLLM,
    ResultadoFerramenta,
)

#: Limite de tokens de saída por chamada — generoso o bastante para uma
#: resposta em pt-BR com várias tools, sem exigir streaming.
MAX_TOKENS_RESPOSTA = 4096

#: Base padrão da API da Anthropic (usada quando ``LLM_BASE_URL`` aponta
#: para "anthropic.com" mas sem caminho, ou é deixada em branco).
BASE_URL_PADRAO = "https://api.anthropic.com"


def _ferramentas_para_anthropic(
    ferramentas: list[FerramentaLLM],
) -> list[dict[str, Any]]:
    return [
        {
            "name": ferramenta.nome,
            "description": ferramenta.descricao,
            "input_schema": ferramenta.parametros,
        }
        for ferramenta in ferramentas
    ]


def _conteudo_resultado(resultado: ResultadoFerramenta) -> str:
    """Serializa o resultado de uma tool para texto (formato do bloco)."""
    if resultado.ok:
        if isinstance(resultado.conteudo, str):
            return resultado.conteudo
        return json.dumps(resultado.conteudo, ensure_ascii=False)
    return resultado.erro or "A tool falhou sem detalhes."


class ClienteAnthropic(ClienteLLM):
    """Uma conversa com a Messages API da Anthropic."""

    def __init__(self, config: ConfiguracaoLLM, instrucoes_sistema: str) -> None:
        self._modelo = config.modelo
        self._sistema = instrucoes_sistema
        self._mensagens: list[dict[str, Any]] = []
        self._ferramentas: list[dict[str, Any]] = []

        self._client = anthropic.Anthropic(
            api_key=config.chave,
            base_url=config.base_url or BASE_URL_PADRAO,
        )

    def iniciar(
        self, mensagem_usuario: str, ferramentas: list[FerramentaLLM]
    ) -> RespostaLLM:
        self._ferramentas = _ferramentas_para_anthropic(ferramentas)
        self._mensagens = [{"role": "user", "content": mensagem_usuario}]
        return self._pedir_resposta()

    def continuar(self, resultados: list[ResultadoFerramenta]) -> RespostaLLM:
        blocos_resultado = [
            {
                "type": "tool_result",
                "tool_use_id": resultado.chamada.id,
                "content": _conteudo_resultado(resultado),
                "is_error": not resultado.ok,
            }
            for resultado in resultados
        ]
        self._mensagens.append({"role": "user", "content": blocos_resultado})
        return self._pedir_resposta()

    def _pedir_resposta(self) -> RespostaLLM:
        try:
            resposta = self._client.messages.create(
                model=self._modelo,
                max_tokens=MAX_TOKENS_RESPOSTA,
                system=self._sistema,
                tools=self._ferramentas,
                messages=self._mensagens,
            )
        except anthropic.AuthenticationError as erro:
            raise ErroLLM(
                "A LLM_KEY não foi aceita pela API da Anthropic. Confira a "
                "chave no `.env`."
            ) from erro
        except anthropic.NotFoundError as erro:
            raise ErroLLM(
                f"Modelo `{self._modelo}` não encontrado na Anthropic. "
                "Confira LLM_MODELO no `.env`."
            ) from erro
        except anthropic.RateLimitError as erro:
            raise ErroLLM(
                "A API da Anthropic recusou por limite de uso (rate limit). "
                "Tente novamente em instantes."
            ) from erro
        except anthropic.APIConnectionError as erro:
            raise ErroLLM(
                f"Não consegui falar com a Anthropic em {self._client.base_url}. "
                f"Detalhe: {erro}"
            ) from erro
        except anthropic.APIStatusError as erro:
            raise ErroLLM(f"A API da Anthropic respondeu com erro: {erro.message}") from erro

        # O histórico nativo precisa dos blocos crus (inclusive tool_use) para
        # a próxima chamada entender a que resultado cada um se refere.
        self._mensagens.append({"role": "assistant", "content": resposta.content})

        texto = "\n".join(
            bloco.text for bloco in resposta.content if bloco.type == "text"
        ).strip()
        chamadas = [
            ChamadaFerramenta(id=bloco.id, nome=bloco.name, argumentos=bloco.input)
            for bloco in resposta.content
            if bloco.type == "tool_use"
        ]
        return RespostaLLM(texto=texto, chamadas=chamadas)
