# 注：不加 "syntax=docker/dockerfile:1" —— 该声明会让每次构建去 Docker Hub 检查/拉取
# frontend 镜像（走加速器，慢）。本机 Docker Desktop 的默认 frontend 已支持 RUN --mount。
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# jpegtran（libjpeg-turbo）：JPEG 上传前无损重压（app/media/compress.py）
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg-turbo-progs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# 用 BuildKit 缓存挂载保留 pip 下载缓存（wheel）：
# requirements.txt 有增改时只下载新增的包，其余直接命中缓存秒装。
# 注意必须去掉 --no-cache-dir，否则 pip 不写缓存，挂载形同虚设。
# 镜像源：清华 TUNA（国内直连 PyPI 官方源极慢；境外部署可删掉 -i 参数）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 以非 root 运行：默认 root 起进程时，任何一个 RCE/任意文件读都会直接拿到容器内的
# root 权限（可读 .env、可改代码卷）。这里建专用用户并只给它数据目录的写权限。
RUN useradd --create-home --shell /bin/bash suiji \
    && mkdir -p /app/data /app/data/media \
    && chown -R suiji:suiji /app/data

COPY --chown=suiji:suiji app ./app
COPY --chown=suiji:suiji static ./static
COPY --chown=suiji:suiji alembic ./alembic
COPY --chown=suiji:suiji alembic.ini ./alembic.ini

EXPOSE 8000

USER suiji

# 单 worker：会话撤销账本在 Redis 不可用时降级为进程内存，
# 多进程会让「登出即失效」「refresh 重放检测」在不同进程间不一致。
# 要扩容请务必先保证 REDIS_URL 可用（账本回到共享的 Redis），再加 --workers。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
