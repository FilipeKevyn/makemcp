"""Decide qual provedor de LLM instanciar a partir da configuração genérica.

O projeto só pede três variáveis (``LLM_BASE_URL``, ``LLM_MODELO``,
``LLM_KEY``) para qualquer provedor. A escolha de *implementação* (Anthropic
nativa vs. compatível com OpenAI) é um detalhe de transporte, decidido aqui:

- ``LLM_PROVIDER=anthropic`` força a API nativa da Anthropic;
- ``LLM_PROVIDER=openai_compat`` força o formato Chat Completions;
- sem ``LLM_PROVIDER`` (padrão), detecta pelo ``base_url``: domínio
  ``anthropic.com`` vira Anthropic, qualquer outro vira compatível com
  OpenAI (OpenAI, Gemini, Groq, OpenRouter, Ollama, ...).

Adicionar um provedor novo é: escrever a classe em ``ui/llm/<nome>.py``
implementando ``ClienteLLM`` e acrescentar um ramo aqui.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .base import ClienteLLM, ConfiguracaoLLM
from .anthropic_provider import BASE_URL_PADRAO as _ANTHROPIC_BASE_URL_PADRAO

_PROVEDOR_ANTHROPIC = "anthropic"
_PROVEDOR_OPENAI_COMPAT = "openai_compat"


def _detectar_provedor(base_url: str) -> str:
    """Decide o provedor pelo domínio do ``base_url`` quando não foi forçado."""
    host = urlsplit(base_url).hostname or ""
    if host == "anthropic.com" or host.endswith(".anthropic.com"):
        return _PROVEDOR_ANTHROPIC
    return _PROVEDOR_OPENAI_COMPAT


def criar_cliente_llm(
    config: ConfiguracaoLLM,
    instrucoes_sistema: str,
    provedor_forcado: str | None = None,
) -> ClienteLLM:
    """Cria uma conversa nova com o provedor apropriado (uma por turno)."""
    provedor = (provedor_forcado or "").strip().lower() or _detectar_provedor(
        config.base_url or _ANTHROPIC_BASE_URL_PADRAO
    )

    if provedor == _PROVEDOR_ANTHROPIC:
        from .anthropic_provider import ClienteAnthropic

        return ClienteAnthropic(config, instrucoes_sistema)

    if provedor == _PROVEDOR_OPENAI_COMPAT:
        from .openai_compat import ClienteOpenAICompativel

        return ClienteOpenAICompativel(config, instrucoes_sistema)

    raise ValueError(
        f"LLM_PROVIDER desconhecido: {provedor!r}. Use 'anthropic' ou "
        "'openai_compat', ou deixe em branco para detectar pelo LLM_BASE_URL."
    )
