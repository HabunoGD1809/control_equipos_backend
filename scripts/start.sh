#!/bin/bash

ENV_DIR=".CtrlEqEnv"

echo "🔧 Creando entorno virtual en $ENV_DIR..."
# Usar python3 o python según tu sistema
python3 -m venv $ENV_DIR || python -m venv $ENV_DIR

echo "✅ Entorno virtual creado."

# Activar el entorno virtual
# Nota: La activación puede variar ligeramente entre shells (bash, zsh, fish, etc.)
# Esta línea es para bash/zsh en Linux/macOS
source "$ENV_DIR/bin/activate"
# Para Windows Git Bash, sería similar.
# Para Windows CMD: %ENV_DIR%\Scripts\activate.bat
# Para Windows PowerShell: $ENV_DIR\Scripts\Activate.ps1

echo "📦 Instalando dependencias más recientes desde requirements.txt..."
# Asegurarse que pip está actualizado dentro del venv
"$ENV_DIR/bin/python" -m pip install --upgrade pip
# Instalar requerimientos
"$ENV_DIR/bin/pip" install -r requirements.txt

echo "✅ Instalación completa. Entorno activado."
echo "📌 Para reactivar el entorno más tarde, usa el comando de activación apropiado para tu shell."
echo "   Ejemplo (bash/zsh): source $ENV_DIR/bin/activate"
