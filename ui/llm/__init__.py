"""Camada de abstração de provedores de LLM.

Veja ``ui/llm/base.py`` para os contratos e ``ui/llm/fabrica.py`` para como
um provedor é escolhido a partir de ``LLM_BASE_URL``/``LLM_MODELO``/``LLM_KEY``.
"""

from .base import (
    ChamadaFerramenta,
    ClienteLLM,
    ConfiguracaoLLM,
    ErroLLM,
    FerramentaLLM,
    RespostaLLM,
    ResultadoFerramenta,
)
from .fabrica import criar_cliente_llm

__all__ = [
    "ChamadaFerramenta",
    "ClienteLLM",
    "ConfiguracaoLLM",
    "ErroLLM",
    "FerramentaLLM",
    "RespostaLLM",
    "ResultadoFerramenta",
    "criar_cliente_llm",
]
