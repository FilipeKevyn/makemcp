"""Provedor de LLM para qualquer API compatível com o formato OpenAI
"Chat Completions" — OpenAI, Gemini (endpoint `/openai`), Groq, OpenRouter,
Ollama, etc.

Fala HTTP puro com ``httpx`` (não existe um "SDK OpenAI genérico" aqui: o
ponto deste módulo é falar só o formato de wire comum a todos esses
provedores, sem acoplar a nenhum SDK deles).  A autenticação é sempre
``Authorization: Bearer <chave>``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .base import (
    ChamadaFerramenta,
    ClienteLLM,
    ConfiguracaoLLM,
    ErroLLM,
    FerramentaLLM,
    RespostaLLM,
    ResultadoFerramenta,
)

TIMEOUT_LLM = 60.0


def _ferramentas_para_openai(ferramentas: list[FerramentaLLM]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": ferramenta.nome,
                "description": ferramenta.descricao,
                "parameters": ferramenta.parametros,
            },
        }
        for ferramenta in ferramentas
    ]


def _conteudo_resultado(resultado: ResultadoFerramenta) -> str:
    if resultado.ok:
        if isinstance(resultado.conteudo, str):
            return resultado.conteudo
        return json.dumps(resultado.conteudo, ensure_ascii=False)
    return resultado.erro or "A tool falhou sem detalhes."


class ClienteOpenAICompativel(ClienteLLM):
    """Uma conversa com um endpoint `/chat/completions` compatível com OpenAI."""

    def __init__(self, config: ConfiguracaoLLM, instrucoes_sistema: str) -> None:
        self._modelo = config.modelo
        self._url = f"{config.base_url.rstrip('/')}/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {config.chave}",
            "Content-Type": "application/json",
        }
        self._mensagens: list[dict[str, Any]] = [
            {"role": "system", "content": instrucoes_sistema}
        ]
        self._ferramentas: list[dict[str, Any]] = []

    def iniciar(
        self, mensagem_usuario: str, ferramentas: list[FerramentaLLM]
    ) -> RespostaLLM:
        self._ferramentas = _ferramentas_para_openai(ferramentas)
        self._mensagens.append({"role": "user", "content": mensagem_usuario})
        return self._pedir_resposta()

    def continuar(self, resultados: list[ResultadoFerramenta]) -> RespostaLLM:
        for resultado in resultados:
            self._mensagens.append(
                {
                    "role": "tool",
                    "tool_call_id": resultado.chamada.id,
                    "content": _conteudo_resultado(resultado),
                }
            )
        return self._pedir_resposta()

    def _pedir_resposta(self) -> RespostaLLM:
        corpo = {
            "model": self._modelo,
            "messages": self._mensagens,
            "tools": self._ferramentas,
        }
        try:
            with httpx.Client(timeout=TIMEOUT_LLM) as http:
                resposta = http.post(self._url, headers=self._headers, json=corpo)
                resposta.raise_for_status()
                dados = resposta.json()
        except httpx.HTTPStatusError as erro:
            if erro.response.status_code in (401, 403):
                raise ErroLLM(
                    "A LLM_KEY não foi aceita pelo provedor. Confira a chave "
                    "no `.env`."
                ) from erro
            raise ErroLLM(
                f"O provedor de LLM respondeu com erro "
                f"{erro.response.status_code}: {erro.response.text[:300]}"
            ) from erro
        except httpx.HTTPError as erro:
            raise ErroLLM(
                f"Não consegui falar com o provedor de LLM em {self._url} "
                f"({type(erro).__name__})."
            ) from erro

        escolha = dados["choices"][0]["message"]
        self._mensagens.append(escolha)

        texto = (escolha.get("content") or "").strip()
        chamadas = [
            ChamadaFerramenta(
                id=chamada["id"],
                nome=chamada["function"]["name"],
                argumentos=json.loads(chamada["function"]["arguments"] or "{}"),
            )
            for chamada in escolha.get("tool_calls") or []
        ]
        return RespostaLLM(texto=texto, chamadas=chamadas)
