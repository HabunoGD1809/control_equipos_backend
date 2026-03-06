#!/bin/bash
set -e

ENV_DIR=".CtrlEqEnv"

echo "🚀 Iniciando configuración ultrarrápida con 'uv'..."

# 1. Verificar si uv está instalado
if ! command -v uv &> /dev/null; then
    echo "❌ 'uv' no está instalado en tu sistema."
    echo "👉 Para instalarlo en Linux/Mac/WSL ejecuta:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "👉 En Windows PowerShell:"
    echo "   powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    exit 1
fi

# 2. Le indicamos a uv que use tu directorio personalizado
export UV_PROJECT_ENVIRONMENT=$ENV_DIR

echo "📦 Resolviendo dependencias y sincronizando entorno..."
# uv sync lee pyproject.toml, crea el entorno (si no existe), 
# genera un uv.lock y descarga los paquetes en paralelo.
uv sync --all-extras

echo "✅ Entorno virtual sincronizado y listo."
echo "📌 Para activar el entorno, usa tu comando habitual:"
echo "   source $ENV_DIR/bin/activate"
