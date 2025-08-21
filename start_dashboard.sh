#!/bin/bash
# start_dashboard.sh - Script per iniciar el dashboard de control de bomba

echo "Iniciant Dashboard de Control de Bomba d'Aigua..."
echo "Comprova que la configuració a config.json sigui correcta"
echo ""

# Comprovar si existeix l'entorn virtual
if [ ! -d "venv" ]; then
    echo "Creant entorn virtual..."
    python3 -m venv venv
fi

# Activar entorn virtual
echo "Activant entorn virtual..."
source venv/bin/activate

# Instal·lar dependències
echo "Instal·lant dependències..."
pip install -r requirements.txt

# Iniciar dashboard
echo "Iniciant dashboard a http://localhost:8501"
echo "Prem Ctrl+C per aturar"
echo ""

streamlit run app.py --server.port 8501 --server.address 0.0.0.0