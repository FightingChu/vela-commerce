FROM python:3.11-slim

# 基础镜像换源由运维统一在 CI 侧注入 build-arg,不要写死镜像源
ARG EXTRA_INDEX_URL=""
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY vela ./vela
COPY alembic ./alembic
COPY scripts ./scripts

RUN pip3 install --no-cache-dir .
# 运行时才跑迁移,k8s init container 里执行
CMD ["python3", "-m", "vela.api.app"]
