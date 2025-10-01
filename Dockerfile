# =============================================================================
# AI-Native App Architecture - Dockerfile
# =============================================================================
# Multi-stage build using uv (ultra-fast Python package manager)
#
# Best Practices Demonstrated:
#   1. Multi-stage builds (base → prod) for minimal image size
#   2. BuildKit cache mounts for fast rebuilds
#   3. Non-root user for security (uvuser)
#   4. Bind mounts for build-time files (not copied into layers)
#   5. Editable install for hot reload in development
#   6. Layer ordering: most stable → most volatile (maximize cache hits)
#
# Why uv?
#   - 10-100x faster than pip
#   - Lockfile for reproducible builds (uv.lock)
#   - Built-in virtual environment management

FROM python:3.13-slim AS base

# ===========================================================================
# Python Environment Configuration
# ===========================================================================
# PYTHONUNBUFFERED: See prints immediately (don't buffer stdout/stderr)
# PYTHONDONTWRITEBYTECODE: Skip .pyc files (not needed in containers)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ===========================================================================
# Create Non-Root User (Security Best Practice)
# ===========================================================================
# Don't run as root! Create uvuser for runtime execution
# We stay as root during build for permission reasons, switch at the end
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/uvuser" \
    --shell "/bin/bash" \
    --uid "${UID}" \
    uvuser

# ===========================================================================
# Install Build Dependencies
# ===========================================================================
# --mount=type=cache: Persist apt cache across builds (faster rebuilds)
# curl: Download uv installer
# build-essential: gcc, make (some Python packages need compilation)
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get update \
    && apt-get install -y curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# ===========================================================================
# Install uv Package Manager
# ===========================================================================
# UV_CACHE_DIR: Where uv caches downloads (we'll mount this as cache)
# UV_LINK_MODE=copy: Copy files vs symlink (works better in containers)
# UV_COMPILE_BYTECODE: Pre-compile .py → .pyc for faster startup
ENV UV_CACHE_DIR="/var/uv/cache" \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN mkdir -p $UV_CACHE_DIR && chmod -R 777 $UV_CACHE_DIR

# Download and install uv (stay as root for global install)
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# ===========================================================================
# Generate Lockfile (Reproducible Builds)
# ===========================================================================
# Uses bind mounts - these files aren't copied into the image, just mounted
# for the duration of this RUN command. Lockfile generation is deterministic.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=README.md,target=README.md \
    uv lock

# ===========================================================================
# Production Stage
# ===========================================================================
FROM base AS prod

WORKDIR /app

# ===========================================================================
# Install Dependencies Only (Not Project Code)
# ===========================================================================
# Why separate? Dependencies change rarely, code changes often.
# This layer is cached and reused unless dependencies change.
# --frozen: Use uv.lock exactly (don't resolve again)
# --no-dev: Skip development dependencies
# --no-install-project: Only install dependencies, not our code yet
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-dev --no-install-project

# ===========================================================================
# Copy Project Code
# ===========================================================================
# Now copy our actual code (changes frequently = last layer)
COPY pyproject.toml .python-version README.md uv.lock LICENSE ./
COPY src/ ./src/

# ===========================================================================
# Install Project in Editable Mode
# ===========================================================================
# Editable install (-e) means changes to /app/src reflect immediately
# This works with our volume mount in docker-compose.yml for hot reload
RUN --mount=type=cache,target=/root/.cache/uv \
    cd /app && uv pip install -e .

# ===========================================================================
# Switch to Non-Root User (Security)
# ===========================================================================
# Change ownership to uvuser, then switch to that user for runtime
RUN chown -R uvuser:uvuser /app
USER uvuser

# ===========================================================================
# Runtime Configuration
# ===========================================================================
WORKDIR /app
# PYTHONPATH: Ensure `import app` works
# PATH: Add .venv/bin so we can call uvicorn directly
ENV PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# ===========================================================================
# Start Application (Development Mode with Hot Reload)
# ===========================================================================
# --reload: Watch for file changes and restart automatically
# --reload-dir: Only watch src/ (not logs, cache, etc.)
# In production, you'd remove --reload and add --workers N
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]