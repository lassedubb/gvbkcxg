FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
# YouTube challenge handling needs yt-dlp-ejs plus a current JS runtime (Deno).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
ENV DENO_INSTALL=/opt/deno
ENV PATH="${DENO_INSTALL}/bin:${PATH}"
RUN curl -fsSL https://deno.land/install.sh | sh
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py index.html ./
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"]
