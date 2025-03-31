FROM ghcr.io/astral-sh/uv:python3.12-bookworm
WORKDIR /app
ENV CHROME_HEADLESS=True
COPY pyproject.toml uv.lock /app/

RUN touch README.md
RUN uv sync

RUN playwright install chromium --only-shell --with-deps

COPY . /app

# 提供两种执行方式
# 默认运行server.py启动API服务器
CMD ["python", "server.py"]

