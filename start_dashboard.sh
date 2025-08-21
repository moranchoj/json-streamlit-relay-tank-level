#!/bin/bash
# Script per iniciar el dashboard del sistema de control de bomba

echo "🚀 Iniciant Dashboard de Control de Bomba d'Aigua..."

# Verificar que Python està disponible
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 no està instal·lat"
    exit 1
fi

# Verificar que Streamlit està disponible
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "❌ Error: Streamlit no està instal·lat"
    echo "Instal·la les dependències amb: pip install -r requirements.txt"
    exit 1
fi

# Verificar que el fitxer de configuració existeix
if [ ! -f "config.json" ]; then
    echo "❌ Error: Fitxer config.json no trobat"
    exit 1
fi

# Verificar que app.py existeix
if [ ! -f "app.py" ]; then
    echo "❌ Error: Fitxer app.py no trobat"
    exit 1
fi

echo "✅ Verificacions completades"
echo "📊 Iniciant dashboard Streamlit..."

# Iniciar l'aplicació Streamlit
python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --browser.serverAddress localhost

echo "🏁 Dashboard aturat"