from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver.exceptions import ToolError

# Carrega o ``.env`` da raiz do projeto (se existir) antes de ler as variáveis.
load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

TIMEOUT_API = 10.0


def _endpoint(caminho: str) -> str:
    """Monta a URL completa de um endpoint da API."""
    return f"{API_URL}{caminho}"


def _corpo_json(resposta: httpx.Response) -> Any:
    """Lê o corpo JSON da resposta, devolvendo o texto puro se não for JSON."""
    try:
        return resposta.json()
    except ValueError:
        return resposta.text


def _resumo_validacao(resposta: httpx.Response) -> str:
    """Resume o 422 do FastAPI (lista de erros de validação) em uma frase."""
    corpo = _corpo_json(resposta)
    detalhes = corpo.get("detail") if isinstance(corpo, dict) else None
    if isinstance(detalhes, list):
        partes: list[str] = []
        for item in detalhes:
            # ``loc`` costuma ser algo como ["body", "titulo"]; o "body" é ruído.
            local = [str(p) for p in item.get("loc", []) if p != "body"]
            campo = ".".join(local) or "corpo"
            partes.append(f"{campo}: {item.get('msg', 'valor inválido')}")
        if partes:
            return "; ".join(partes)
    return str(detalhes)


def _traduzir_erro(erro: httpx.HTTPStatusError, tarefa_id: int | None) -> ToolError:
    """Converte um código HTTP de erro na ToolError correspondente em pt-BR."""
    resposta = erro.response
    if resposta.status_code == 404 and tarefa_id is not None:
        return ToolError(f"Tarefa {tarefa_id} não encontrada")
    if resposta.status_code == 422:
        return ToolError(f"Dados inválidos: {_resumo_validacao(resposta)}")

    corpo = _corpo_json(resposta)
    detalhe = corpo.get("detail") if isinstance(corpo, dict) else corpo
    return ToolError(f"Erro {resposta.status_code} na API: {detalhe}")


async def requisitar(
    metodo: str,
    caminho: str,
    *,
    json: dict[str, Any] | None = None,
    tarefa_id: int | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_API) as cliente:
            resposta = await cliente.request(metodo, _endpoint(caminho), json=json)
    except httpx.ConnectError as erro:
        raise ToolError(f"API indisponível em {API_URL}") from erro
    except httpx.TimeoutException as erro:
        raise ToolError(
            f"A API não respondeu em {TIMEOUT_API:.0f}s ({API_URL})"
        ) from erro

    try:
        resposta.raise_for_status()
    except httpx.HTTPStatusError as erro:
        raise _traduzir_erro(erro, tarefa_id) from erro

    if resposta.status_code == 204 or not resposta.content:
        return None
    return resposta.json()