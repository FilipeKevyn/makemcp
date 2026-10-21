"""Agente com LLM real: mesma interface de eventos de ``AgenteSimulado``.

Em vez de interpretar a frase por regex, este agente manda a mensagem (e a
lista de tools do MCP) para um LLM de verdade e deixa o modelo decidir quais
tools chamar (*tool calling*). O laço é simples: pergunta ao modelo, executa
as tools pedidas via MCP, devolve os resultados, repete — até o modelo
responder só em texto ou o limite de passos ser atingido.

O provedor concreto (Anthropic nativo ou qualquer API compatível com OpenAI)
é escondido atrás de ``ui.llm.ClienteLLM``; este módulo só conhece esse
contrato neutro, nunca o formato de wire de um provedor específico.
"""

from __future__ import annotations

import os
from typing import Iterator

from agente import Evento, EventoChamadaTool, EventoResultadoTool, EventoTextoFinal
from cliente_mcp import ClienteMCP, ErroClienteMCP
from llm.base import (
    ChamadaFerramenta,
    ConfiguracaoLLM,
    ErroLLM,
    FerramentaLLM,
    ResultadoFerramenta,
)
from llm.fabrica import criar_cliente_llm

#: Limite de idas e vindas de tool calling num único turno — evita que o
#: modelo entre num laço infinito de chamadas.
MAX_PASSOS = 6

INSTRUCOES_SISTEMA = (
    "Você é o assistente do minicurso de MCP, conversando em pt-BR sobre uma "
    "lista de tarefas (TO-DO). Use as tools disponíveis para criar, listar, "
    "obter, atualizar, concluir/desmarcar e remover tarefas — nunca invente "
    "ids ou dados: sempre confira com uma tool antes de responder. Depois de "
    "usar as tools necessárias, responda em texto curto e claro, em pt-BR, "
    "resumindo o que foi feito ou encontrado."
)

TEXTO_SEM_CHAVE = (
    "Ainda não encontrei uma `LLM_KEY` configurada, então não consigo falar "
    "com um LLM de verdade. Para configurar: copie `.env.example` para "
    "`.env` e preencha `LLM_KEY` (veja os exemplos de provedor no próprio "
    "arquivo). Enquanto isso, rode com `AGENTE_SIMULADO=true` para usar o "
    "agente simulado (sem chave, sem internet)."
)


def _ferramentas_llm(cliente: ClienteMCP) -> list[FerramentaLLM]:
    return [
        FerramentaLLM(nome=t.nome, descricao=t.descricao, parametros=t.parametros)
        for t in cliente.listar_tools()
    ]


class AgenteLLM:
    """Agente que delega o entendimento da mensagem a um LLM real."""

    def processar(self, mensagem: str, cliente: ClienteMCP) -> Iterator[Evento]:
        chave = os.environ.get("LLM_KEY", "").strip()
        if not chave:
            yield EventoTextoFinal(TEXTO_SEM_CHAVE)
            return

        config = ConfiguracaoLLM(
            base_url=os.environ.get("LLM_BASE_URL", "").strip(),
            modelo=os.environ.get("LLM_MODELO", "").strip(),
            chave=chave,
        )
        provedor_forcado = os.environ.get("LLM_PROVIDER", "").strip() or None

        try:
            ferramentas = _ferramentas_llm(cliente)
            llm = criar_cliente_llm(config, INSTRUCOES_SISTEMA, provedor_forcado)
            resposta = llm.iniciar(mensagem, ferramentas)

            passos = 0
            while resposta.pediu_ferramentas and passos < MAX_PASSOS:
                resultados: list[ResultadoFerramenta] = []
                for chamada in resposta.chamadas:
                    yield EventoChamadaTool(nome=chamada.nome, argumentos=chamada.argumentos)
                    resultados.append(_executar_chamada(cliente, chamada))
                    ultimo = resultados[-1]
                    yield EventoResultadoTool(
                        nome=chamada.nome,
                        ok=ultimo.ok,
                        conteudo=ultimo.conteudo if ultimo.ok else ultimo.erro,
                    )
                resposta = llm.continuar(resultados)
                passos += 1

        except ErroLLM as erro:
            yield EventoTextoFinal(f"Não consegui falar com o LLM: {erro}")
            return

        texto = resposta.texto.strip() or "Pronto."
        yield EventoTextoFinal(texto)


def _executar_chamada(cliente: ClienteMCP, chamada: ChamadaFerramenta) -> ResultadoFerramenta:
    try:
        conteudo = cliente.chamar_tool(chamada.nome, chamada.argumentos)
        return ResultadoFerramenta(chamada=chamada, ok=True, conteudo=conteudo)
    except ErroClienteMCP as erro:
        return ResultadoFerramenta(chamada=chamada, ok=False, erro=str(erro))
