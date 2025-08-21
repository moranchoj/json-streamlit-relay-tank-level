#!/bin/bash
# install_autostart_service.sh - Script per instal·lar el servei d'autoarranc

echo "Instal·lant servei d'autoarranc del Dashboard de Control de Bomba..."

# Comprovar si s'executa com a root
if [ "$EUID" -ne 0 ]; then
    echo "Aquest script ha d'executar-se com a root (sudo)"
    exit 1
fi

# Copiar el fitxer de servei
cp autostart.service /etc/systemd/system/pump-control-dashboard.service

# Actualitzar el path si cal
CURRENT_DIR=$(pwd)
sed -i "s|/home/pi/json-streamlit-relay-tank-level|$CURRENT_DIR|g" /etc/systemd/system/pump-control-dashboard.service

# Actualitzar l'usuari actual
CURRENT_USER=$(logname)
sed -i "s|User=pi|User=$CURRENT_USER|g" /etc/systemd/system/pump-control-dashboard.service

# Recarregar systemd
systemctl daemon-reload

# Activar el servei
systemctl enable pump-control-dashboard.service

echo "Servei instal·lat correctament!"
echo ""
echo "Comandes útils:"
echo "  sudo systemctl start pump-control-dashboard    # Iniciar servei"
echo "  sudo systemctl stop pump-control-dashboard     # Aturar servei"
echo "  sudo systemctl status pump-control-dashboard   # Estat del servei"
echo "  sudo systemctl logs pump-control-dashboard     # Veure logs"
echo ""
echo "El dashboard s'iniciarà automàticament al següent reinici"