FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend ./backend
COPY frontend ./frontend
COPY phase1 ./phase1

EXPOSE 8501

CMD uv run streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port ${PORT:-8501} --server.enableCORS false --server.enableXsrfProtection false

