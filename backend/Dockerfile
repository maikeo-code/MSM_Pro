FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema (incluindo supervisor para gerenciar processos)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia configuração do supervisor
COPY supervisord.conf /etc/supervisor/conf.d/msm_pro.conf

# Cache-bust: force re-copy of application code
ARG CACHEBUST=1
COPY . .

# Garante que o start.sh seja executável
RUN chmod +x start.sh

# Expõe a porta da API
EXPOSE 8000

# start.sh roda migrations e depois sobe supervisord (uvicorn + worker + beat)
CMD ["bash", "start.sh"]
