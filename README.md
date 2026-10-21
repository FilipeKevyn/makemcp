# Minicurso MCP — API de Tarefas + Servidor MCP + UI Streamlit

Projeto didático, de ponta a ponta, para ensinar o **Model Context Protocol (MCP)**.
São três peças executáveis que se conversam em camadas bem separadas:

1. **API de tarefas** — FastAPI, CRUD de tarefas (título, descrição e situação concluída) com armazenamento em memória.
2. **Servidor MCP** — expõe tools que operam a API por HTTP; transporte **stdio**.
3. **UI Streamlit** — chat à esquerda rodando um **agente** que chama as tools do MCP
   (um **LLM real** por padrão, ou o **agente simulado** com `AGENTE_SIMULADO=true`) e lista
   de tarefas somente leitura à direita. Cada chamada de tool aparece no chat **antes** da resposta final.

---

## Quickstart

Pré-requisitos: **Python ≥ 3.11**, [`uv`](https://docs.astral.sh/uv/) e, para os atalhos

`make`, o **GNU Make**.

### 0. Instalar as ferramentas

#### Linux e macOS

**`make`** — geralmente já vem instalado; se não:

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y make
```

**`uv`** — instalador oficial:

```bash
# Ubuntu
curl -LsSf https://astral.sh/uv/install.sh | sh
# Alternativa via pip: pip install uv
```

Confirme com `make --version` e `uv --version`. Pode ser preciso reabrir o terminal para
o `PATH` valer (no `bash`/`zsh`, `source ~/.local/bin/env` costuma resolver).

#### Windows

**`make`** — o Windows não traz `make`; instale por um gerenciador de pacotes (escolha um):

```powershell
# winget
winget install --id GnuWin32.Make -e
```

**`uv`** — no PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Alternativas: winget install --id astral-sh.uv -e   |   pip install uv
```

Confirme com `make --version` e `uv --version` em um terminal novo.

### 1. Instalar as dependências e criar o `.env`

Na raiz do projeto:

```bash
uv sync                 # Equivalente: make install
cp .env.example .env    # Windows (cmd): copy .env.example .env
```

O `.env` guarda as variáveis locais (ex.: `API_URL`) e **não** vai para o git — só o
modelo `.env.example` é versionado. Se preferir, exporte as variáveis no shell e o
`.env` fica opcional.

Nesse mesmo `.env` você escolhe **como o agente responde** (veja
[Agentes: LLM real × simulado](#agentes-llm-real--simulado)):

- com uma `LLM_KEY` válida, o chat responde por um **LLM real**;
- com `AGENTE_SIMULADO=true`, o chat usa as **respostas padrão do agente simulado**
  (por regras, sem chave e sem internet) — ideal para laboratório.

### 2. Subir a API e a UI

Em **dois terminais**, com `make` (veja a tabela de atalhos abaixo):

```bash
# Terminal 1 — API de tarefas (http://localhost:8000, Swagger em /docs)
make api

# Terminal 2 — UI Streamlit (http://localhost:8501)
make ui
```

Ou, sem `make`, chamando o `uv` direto:

```bash
uv run fastapi dev api/main.py     # Terminal 1 (API)
uv run streamlit run ui/app.py     # Terminal 2 (UI)
```

Abra a UI em **http://localhost:8501** e comece a conversar com o agente.
Para explorar a API sozinha, abra o Swagger em **http://localhost:8000/docs**.

> O servidor MCP **não** precisa de um terceiro terminal: a UI o inicia sozinha via stdio.
> Subir a UI **antes** da API também funciona — a lista mostra um aviso e volta sozinha
> quando a API subir.

### Atalhos com `make`

O `Makefile` abstrai os comandos de inicialização das três peças. Rode `make` (ou
`make ajuda`) para listar os alvos:

| Alvo | O que faz |
|------|-----------|
| `make install`   | Instala as dependências (`uv sync`). |
| `make api`       | Sobe a API de tarefas (`--port` configurável). |
| `make ui`        | Sobe a UI Streamlit (sobe o servidor MCP sozinha). |
| `make mcp`       | Sobe o servidor MCP standalone (stdio), para inspeção. |
| `make inspector` | Abre o MCP Inspector (opcional; exige Node). |

No Linux/macOS também dá para ajustar variáveis de ambiente na mesma linha
(`API_URL=http://localhost:9000 make ui`); no PowerShell/cmd, use
`$env:API_URL="http://localhost:9000"; make ui`.

---

## Ordem de leitura sugerida (didática)

O código foi escrito para ser lido nesta ordem, comentado em pt-BR:

| # | Módulo | O que ler |
|---|--------|-----------|
| 1 | `api/` | `modelos.py` → `armazenamento.py` → `main.py` (o contrato HTTP e o "banco" em memória) |
| 2 | `servidor_mcp/` | `cliente_api.py` (HTTP + erros amigáveis) → `servidor.py` (FastMCP + as 6 tools) |
| 3 | `ui/` | `cliente_mcp.py` (sessão MCP stdio) → `agente.py` (agente simulado + eventos) → `agente_llm.py` (agente com LLM) → `app.py` (tela) |

> A **interface de eventos** de `ui/agente.py` (chamada de tool → resultado → texto final) é a
> costura de substituição: os dois agentes — `AgenteSimulado` e `AgenteLLM` — implementam a
> mesma assinatura `processar(...)`, então `app.py` só precisa escolher quem usar.

---

## Arquitetura

### Fluxo da demo (2 processos)

```
Terminal 1                        Terminal 2
┌───────────────────┐             ┌─────────────────────────────────────────────┐
│  uv run fastapi   │             │  uv run streamlit run ui/app.py             │
│  dev api/main.py  │             │                                             │
│                   │             │   ┌── agente (LLM/simulado) ─> MCP ──┐   │
│  API FastAPI      │◄─── HTTP ───┼───┘        (stdio)         │          │   │
│  /tarefas         │             │                            ▼          │   │
│  (em memória)     │             │              servidor MCP (subprocesso) │   │
│  /docs (Swagger)  │             │             ┌──────────────┐           │   │
└───────────────────┘             │             │ POST /tarefas│           │   │
        ▲                         │             │ GET  /tarefas│  (HTTP)   │   │
        └──────────── HTTP ───────┼─────────────│ PATCH/DELETE │           │   │
                    (só leitura)  │             └──────────────┘           │   │
                                  │   lista à direita (polling ~2s)          │   │
                                  └─────────────────────────────────────────┘
```

### Estrutura de diretórios

```
makemcp/
├── pyproject.toml          # projeto único gerenciado por uv
├── Makefile                # atalhos: make install/api/ui/mcp/inspector
├── .env.example            # modelo das variáveis de ambiente (versionado)
├── .env                    # suas variáveis locais (NÃO versionado)
├── .gitignore              # .venv/, __pycache__/, .streamlit/, .env
├── README.md               # este arquivo
├── SPEC.md                 # especificação
├── PLAN.md                 # plano de implementação
├── api/
│   ├── modelos.py          # Tarefa, TarefaCriar, TarefaAtualizar (Pydantic)
│   ├── armazenamento.py    # ArmazenamentoTarefas (dict em memória + contador)
│   └── main.py             # app FastAPI + rotas CRUD
├── servidor_mcp/
│   ├── cliente_api.py      # acesso HTTP à API (httpx) + mapeamento de erros
│   └── servidor.py         # FastMCP + as 6 tools + main() stdio
└── ui/
    ├── app.py              # layout (chat à esquerda, lista à direita) + escolha do agente
    ├── agente.py           # agente simulado + interface de eventos
    ├── agente_llm.py       # agente com LLM real (tool calling via MCP)
    └── cliente_mcp.py      # sessão MCP stdio (thread de loop + cache_resource)
```

---

## Tools do servidor MCP

O servidor `tarefas-mcp` publica **6 tools** (nomes em pt-BR, com prefixo `tarefas_`):

| Tool | Argumentos | O que faz |
|------|-----------|-----------|
| `tarefas_criar` | `titulo` (str), `descricao` (str, opcional) | Cria uma tarefa e devolve a tarefa com o `id` gerado. |
| `tarefas_listar` | — | Lista todas as tarefas, em ordem de criação. |
| `tarefas_obter` | `id` (int) | Devolve a tarefa com o `id` informado. |
| `tarefas_atualizar` | `id` (int), `titulo` e/ou `descricao` | Atualiza parcialmente (pelo menos um campo). |
| `tarefas_concluir` | `id` (int), `concluido` (bool, opcional) | Marca (`true`), desmarca (`false`) ou alterna a conclusão (omitido). |
| `tarefas_remover` | `id` (int) | Remove a tarefa pelo `id`. |

Toda falha vira uma mensagem amigável em pt-BR (nunca traceback cru):

- id inexistente → `Tarefa N não encontrada`;
- validação (ex.: título vazio) → resumo do erro da API;
- API fora do ar → `API indisponível em http://localhost:8000`.

Cada chamada de tool é registrada em **log no stderr** (`tool tarefas_criar chamada com {...}`).

### Contrato da API (FastAPI)

| Método | Rota | Resposta |
|--------|------|----------|
| `POST`   | `/tarefas`        | `201` com a tarefa criada |
| `GET`    | `/tarefas`        | `200` com a lista em ordem de criação |
| `GET`    | `/tarefas/{id}`   | `200` ou `404` |
| `PATCH`  | `/tarefas/{id}`   | `200`, aceitando `titulo` e/ou `descricao`; `404` / `422` |
| `PATCH`  | `/tarefas/{id}/concluido` | `200`, aceitando `concluido` (`true`/`false`); sem corpo **alterna**; `404` |
| `DELETE` | `/tarefas/{id}`   | `204` ou `404` |

Ao reiniciar a API, o "banco" em memória é zerado — cada exercício começa limpo.

---

## Rodando o servidor MCP standalone (para inspeção)

Com a API no ar, você pode subir só o servidor MCP (transporte stdio):

```bash
make mcp
# Equivalente: uv run python -m servidor_mcp.servidor
```

Isso é útil para mostrar o "lado do servidor" na aula. **Opcional** (exige Node instalado),
dá para inspecionar as tools no MCP Inspector:

```bash
make inspector
# Equivalente: uv run mcp dev servidor_mcp/servidor.py
```