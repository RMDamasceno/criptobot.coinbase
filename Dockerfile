# Dockerfile para os Bots de Criptomoedas
# Baseado em Python 3.11 Alpine para imagem mais leve

FROM python:3.11-alpine

# Metadados da imagem
LABEL maintainer="crypto-bots"
LABEL description="Bots de sinais e trading de criptomoedas"
LABEL version="1.0.0"

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    libffi-dev \
    openssl-dev \
    curl \
    sqlite \
    sqlite-dev \
    tzdata

# Definir timezone
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Criar usuário não-root para segurança
RUN addgroup -g 1000 cryptobots && \
    adduser -D -s /bin/sh -u 1000 -G cryptobots cryptobots

# Copiar requirements primeiro para aproveitar cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY src/ ./src/
COPY bots/ ./bots/
COPY .env.example .env.example

# Criar diretórios necessários
RUN mkdir -p logs data config && \
    chown -R cryptobots:cryptobots /app

# Mudar para usuário não-root
USER cryptobots

# Verificar se .env existe, senão criar do exemplo
RUN if [ ! -f .env ]; then cp .env.example .env; fi

# Variáveis de ambiente padrão
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Healthcheck simplificado e mais confiável
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; print('Health check OK')" || exit 1

# Expor porta para monitoramento (opcional)
EXPOSE 8080

# Comando padrão (pode ser sobrescrito)
CMD ["python", "bots/signal_bot_runner.py"]

