UV ?= uv
API_PORT ?= 8000
UI_PORT ?= 8501

.PHONY: ajuda help install api mcp ui inspector

ajuda help:
	@echo "Alvos disponíveis:"
	@echo "  make install    -> instala as dependências (uv sync)"
	@echo "  make api        -> sobe a API de tarefas (http://localhost:$(API_PORT))"
	@echo "  make ui         -> sobe a UI Streamlit (http://localhost:$(UI_PORT))"
	@echo "  make mcp        -> sobe o servidor MCP standalone (stdio)"
	@echo "  make inspector  -> abre o MCP Inspector (opcional; exige Node)"
	@echo ""
	@echo "Sobrescreva variáveis na linha de comando, ex.: make api API_PORT=9000"

install:
	$(UV) sync

api:
	$(UV) run fastapi dev api/main.py --port $(API_PORT)

ui:
	$(UV) run streamlit run ui/app.py --server.port $(UI_PORT)

mcp:
	$(UV) run python -m servidor_mcp.servidor

inspector:
	$(UV) run mcp dev servidor_mcp/servidor.py
