FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Install the project into `/app`
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

# Install the project's dependencies using the lockfile and settings
COPY uv.lock pyproject.toml /app/
RUN uv sync --locked --no-install-project --no-dev --no-cache

COPY spc_notifier /app/spc_notifier
RUN uv sync --locked --no-dev --no-cache

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

CMD ["python", "-u", "-m", "spc_notifier.main", "--loop"]
