FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cache-bust: force re-copy of application code
ARG CACHEBUST=1
COPY . .

# Expõe a porta da API
EXPOSE 8000

# Railway sets $PORT dynamically; default to 8000 for local dev
# Shell form allows $PORT expansion
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
