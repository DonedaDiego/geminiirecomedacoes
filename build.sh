#!/usr/bin/env bash
# build.sh - Script de build para Render

set -o errexit  # Sair se algum comando falhar

echo "🔨 Iniciando build do Geminii Tech..."

# Atualizar pip
echo "📦 Atualizando pip..."
python -m pip install --upgrade pip

# Instalar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt

# Verificar instalação
echo "✅ Verificando instalação..."
python -c "import flask; print(f'Flask {flask.__version__} instalado')"
python -c "import psycopg2; print('PostgreSQL driver OK')"
python -c "import jwt; print('JWT OK')"
python -c "import gunicorn; print('Gunicorn OK')"

echo "🎉 Build concluído com sucesso!"