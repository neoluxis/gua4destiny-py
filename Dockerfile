FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# 系统依赖（用于 cairosvg / Pillow 等）
# 使用更通用的 libjpeg 包名并加入常用运行时/构建依赖
RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         ca-certificates \
         build-essential \
        libcairo2 \
        libpango-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
         libffi-dev \
         libjpeg62-turbo-dev \
         zlib1g-dev \
         fonts-dejavu-core \
     && rm -rf /var/lib/apt/lists/*

# 复制并安装 python 依赖
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制项目文件
COPY . /app

EXPOSE 8000

# 默认命令（开发时可在 compose 中改为 --reload）
CMD ["uvicorn", "gua4destiny.fastapi.app:app", "--host", "0.0.0.0", "--port", "8000"]
