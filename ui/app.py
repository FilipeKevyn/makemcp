"""Tela do minicurso: chat (agente + MCP) à esquerda, lista de tarefas à direita.

Dois pontos centrais, que o restante do README explica em detalhe:

- o chat **não fala direto com a API** — ele só conhece ``ui.cliente_mcp``, que
  fala MCP (stdio) com o servidor, que fala HTTP com a API;
- a lista à direita é **somente leitura** e se atualiza sozinha por polling
  (``st.fragment(run_every=...)``); quem escreve é sempre o agente, via MCP.

Rode a partir da raiz do projeto: ``uv run streamlit run ui/app.py``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

from agente import (
    AgenteSimulado,
    EventoChamadaTool,
    EventoResultadoTool,
    EventoTextoFinal,
)
from cliente_mcp import ErroClienteMCP, obter_cliente_mcp

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_LISTA = 3.0
INTERVALO_POLLING = "2s"

st.set_page_config(page_title="Minicurso MCP — Tarefas", layout="wide")


def _agente_simulado_ativo() -> bool:
    return os.environ.get("AGENTE_SIMULADO", "false").strip().lower() in (
        "1", "true", "sim",
    )


def _criar_agente():
    if _agente_simulado_ativo():
        return AgenteSimulado(), "Agente simulado (regras, sem LLM)"
    from agente_llm import AgenteLLM

    return AgenteLLM(), "Agente com LLM real"


# --- Estado do chat (persiste entre reruns, story 23) ---

if "historico" not in st.session_state:
    st.session_state.historico = []  # lista de blocos renderizáveis, em ordem


def _adicionar_bloco(tipo: str, **dados: Any) -> None:
    st.session_state.historico.append({"tipo": tipo, **dados})


def _renderizar_bloco(bloco: dict[str, Any]) -> None:
    tipo = bloco["tipo"]
    if tipo == "usuario":
        with st.chat_message("user"):
            st.markdown(bloco["texto"])
    elif tipo == "resultado_tool":
        estado = "complete" if bloco["ok"] else "error"
        icone = "✅" if bloco["ok"] else "⚠️"
        with st.status(f"{icone} tool `{bloco['nome']}`", state=estado, expanded=True):
            st.caption("argumentos")
            st.json(bloco["argumentos"])
            st.caption("resultado" if bloco["ok"] else "erro")
            conteudo = bloco["conteudo"]
            if isinstance(conteudo, (dict, list)):
                st.json(conteudo)
            else:
                st.write(conteudo)
    elif tipo == "texto_agente":
        with st.chat_message("assistant"):
            st.markdown(bloco["texto"])


def _rodar_turno(mensagem: str) -> None:
    _adicionar_bloco("usuario", texto=mensagem)

    try:
        cliente = obter_cliente_mcp()
    except ErroClienteMCP as erro:
        _adicionar_bloco("texto_agente", texto=f"Não consegui falar com o MCP: {erro}")
        return

    agente, _ = _criar_agente()
    # O cartão de tool (nome + argumentos + resultado) só é adicionado ao
    # histórico quando o par chamada/resultado estiver completo — isso
    # garante que ele fique, na ordem do histórico, sempre antes do texto
    # final do mesmo turno (stories 4 e 5 do spec).
    pendente: dict[str, Any] | None = None
    for evento in agente.processar(mensagem, cliente):
        if isinstance(evento, EventoChamadaTool):
            pendente = {"nome": evento.nome, "argumentos": evento.argumentos}
        elif isinstance(evento, EventoResultadoTool):
            argumentos = pendente["argumentos"] if pendente else {}
            _adicionar_bloco(
                "resultado_tool",
                nome=evento.nome,
                argumentos=argumentos,
                ok=evento.ok,
                conteudo=evento.conteudo,
            )
        elif isinstance(evento, EventoTextoFinal):
            _adicionar_bloco("texto_agente", texto=evento.texto)


@st.fragment(run_every=INTERVALO_POLLING)
def _lista_tarefas() -> None:
    st.subheader("Tarefas (somente leitura)")
    try:
        resposta = httpx.get(f"{API_URL}/tarefas", timeout=TIMEOUT_LISTA)
        resposta.raise_for_status()
        tarefas = resposta.json()
    except httpx.HTTPError:
        st.warning(f"API indisponível em {API_URL}. Tentando novamente...")
        return

    if not tarefas:
        st.info("Nenhuma tarefa ainda — peça ao agente para criar uma no chat.")
        return

    for tarefa in tarefas:
        marcador = "✅" if tarefa.get("concluido") else "⬜"
        with st.container(border=True):
            st.markdown(f"{marcador} **#{tarefa['id']} — {tarefa['titulo']}**")
            if tarefa.get("descricao"):
                st.caption(tarefa["descricao"])


# --- Layout ---

st.title("Minicurso MCP — Agente de Tarefas")

_, nome_agente = _criar_agente()
st.caption(f"Modo do agente: **{nome_agente}** (variável `AGENTE_SIMULADO`)")

coluna_chat, coluna_lista = st.columns([2, 3])

with coluna_chat:
    st.subheader("Chat")

    with st.container(height=520, border=True, autoscroll=True):
        for bloco in st.session_state.historico:
            _renderizar_bloco(bloco)

    mensagem = st.chat_input("Converse com o agente sobre suas tarefas...")
    if mensagem:
        _rodar_turno(mensagem)
        st.rerun()

with coluna_lista:
    _lista_tarefas()
