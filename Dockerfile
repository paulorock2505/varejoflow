FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o projeto
COPY . .

# Garante existência e permissões corretas para Flask-Session
RUN mkdir -p /app/flask_session \
    && chmod 700 /app/flask_session

EXPOSE 8000

