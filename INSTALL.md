# Guia d'Instal·lació - Sistema de Control de Bomba d'Aigua

## Requisits del Sistema

### Maquinari
- **Raspberry Pi 4B** amb Raspberry Pi OS
- **HAT PiRelay-V2** de SB Components
- **Venus OS 3.64** amb **GX Tank 140** (opcional per a desenvolupament)
- Connexió de xarxa per comunicació MQTT

### Programari
- **Python 3.7 o superior**
- **pip** (gestor de paquets Python)
- **git** (per clonar el repositori)

## Instal·lació Pas a Pas

### 1. Preparar el Sistema

```bash
# Actualitzar el sistema
sudo apt update && sudo apt upgrade -y

# Instal·lar dependències del sistema
sudo apt install python3 python3-pip git -y
```

### 2. Clonar el Repositori

```bash
# Clonar el projecte
git clone <repository-url>
cd json-streamlit-relay-tank-level
```

### 3. Instal·lar Dependències Python

```bash
# Instal·lar les dependències
pip3 install -r requirements.txt

# Verificar la instal·lació
python3 -c "import streamlit, paho.mqtt, gpiozero, plotly, pandas; print('✅ Totes les dependències instal·lades correctament')"
```

### 4. Configurar el Sistema

#### Configurar `config.json`
Editar el fitxer `config.json` amb els paràmetres del vostre sistema:

```json
{
  "mqtt_broker": "192.168.1.43",        # IP del Venus OS
  "mqtt_port": 1883,
  "victron_device_id": "2ccf6734efd2",  # ID del dispositiu Victron
  "hora_maniobra": "12:00",
  "durada_max_maniobra": 3,
  "durada_max_manual": 10,
  "relay3_gpio": 6,                     # GPIO del relay 3
  "relay4_gpio": 5,                     # GPIO del relay 4
  "periode_manteniment": 10,
  "temps_manteniment": 10
}
```

#### Configurar GPIO (Raspberry Pi)
```bash
# Habilitar GPIO (si no està habilitat)
sudo raspi-config
# Navegar a: Interfacing Options > GPIO > Enable
```

### 5. Testing de la Instal·lació

#### Test Bàsic del Sistema
```bash
python3 test_app.py
```

#### Test de Connexió MQTT (opcional)
```bash
# Només si tens Venus OS disponible
python3 test_mqtt.py
```

### 6. Executar l'Aplicació

#### Opció 1: Script d'Inici (Recomanat)
```bash
chmod +x start_dashboard.sh
./start_dashboard.sh
```

#### Opció 2: Directament amb Streamlit
```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### 7. Accedir al Dashboard

Obrir un navegador web i anar a:
```
http://<IP_RASPBERRY>:8501
```

Per exemple: `http://192.168.1.100:8501`

## Configuració Avançada

### Inici Automàtic al Boot

Per configurar l'aplicació perquè s'iniciï automàticament al boot:

1. **Crear servei systemd**:
```bash
sudo nano /etc/systemd/system/bomba-control.service
```

2. **Contingut del servei**:
```ini
[Unit]
Description=Sistema de Control de Bomba d'Aigua
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/json-streamlit-relay-tank-level
ExecStart=/home/pi/json-streamlit-relay-tank-level/start_dashboard.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. **Habilitar el servei**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bomba-control.service
sudo systemctl start bomba-control.service
```

### Configuració de Xarxa

Per accedir des de qualsevol dispositiu de la xarxa, assegurar-se que:

1. **Firewall** permet el port 8501:
```bash
sudo ufw allow 8501
```

2. **IP estàtica** (recomanat) configurada a la Raspberry Pi

## Solució de Problemes

### Error: "No module named 'xyz'"
```bash
# Reinstal·lar dependències
pip3 install -r requirements.txt --force-reinstall
```

### Error: "Unable to load any default pin factory!"
- Normal en desenvolupament sense hardware GPIO real
- El sistema utilitza mock objects automàticament

### Error de connexió MQTT
- Verificar IP del broker MQTT al `config.json`
- Comprovar que Venus OS té MQTT habilitat
- Provar `python3 test_mqtt.py` per diagnosticar

### Port 8501 ja en ús
```bash
# Trobar procés utilitzant el port
sudo lsof -i :8501

# Matar el procés si cal
sudo kill -9 <PID>
```

### Permisos GPIO
```bash
# Afegir usuari al grup gpio
sudo usermod -a -G gpio $USER

# Reiniciar sessió o reboot
sudo reboot
```

## Verificació de la Instal·lació

### Checklist Final

- [ ] Python 3.7+ instal·lat i funcionant
- [ ] Totes les dependències instal·lades sense errors
- [ ] `config.json` configurat correctament
- [ ] Test bàsic (`test_app.py`) passa correctament
- [ ] L'aplicació s'inicia sense errors
- [ ] Dashboard accessible des del navegador
- [ ] Relés responen (si hardware disponible)
- [ ] Connexió MQTT funcional (si Venus OS disponible)

### Logs i Debug

Per veure logs detallats:
```bash
# Executar amb logs de debug
STREAMLIT_LOGGER_LEVEL=debug streamlit run app.py
```

## Suport

Si teniu problemes durant la instal·lació:

1. Verificar que compliu tots els requisits
2. Consultar la secció de solució de problemes
3. Executar els tests per identificar el problema
4. Crear un issue al repositori amb detalls de l'error
