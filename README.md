# Sistema de Control de Bomba d'Aigua

Sistema de control automàtic d'una bomba d'aigua amb monitorització en temps real, gestió de maniobres i registre d'històrics. Combina **Venus OS GX Tank 140** per la lectura dels nivells de dipòsits, una **Raspberry Pi 4B** per la lògica de control i un **HAT PiRelay-V2** per al control físic dels relés.

## 🚀 Característiques

- **Control Automàtic**: Maniobres programades per hora configurable (per defecte 12:00)
- **Control Manual**: Activació des del dashboard amb durada configurable
- **Monitorització MQTT**: Connexió amb Venus OS per llegir nivells dels dipòsits
- **Control de Relés**: Gestió de 2 relés via GPIO (GPIO 6 i 5)
- **Dashboard Web**: Interfície Streamlit amb 3 pestanyes
- **Seguretat**: Aturada automàtica segons nivells dels dipòsits
- **Històric**: Registre complet de totes les maniobres
- **Manteniment**: Operacions periòdiques automàtiques

## 📋 Requisits

### Maquinari
- **Venus OS 3.64** amb **GX Tank 140**
- **Raspberry Pi 4B** amb Raspberry Pi OS
- **HAT PiRelay-V2** de SB Components

### Programari
- Python 3.7+
- Dependències: `streamlit`, `paho-mqtt`, `gpiozero`, `plotly`, `pandas`

## 🔧 Instal·lació

1. **Clonar el repositori**
   ```bash
   git clone <repository-url>
   cd json-streamlit-relay-tank-level
   ```

2. **Instal·lar dependències**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar el sistema**
   - Editar `config.json` amb la configuració apropiada
   - Verificar la connexió MQTT amb `python test_mqtt.py`

4. **Executar l'aplicació**
   ```bash
   ./start_dashboard.sh
   # o directament:
   streamlit run app.py
   ```

## 📊 Dashboard

### 🔹 Monitorització
- Gauges dels nivells dels dipòsits (baix i alt)
- Indicadors LED de l'estat de la maniobra i relés
- Informació de la darrera maniobra i propera programada
- Botons per control manual (iniciar/aturar)

### 🔹 Històric
- Gràfic amb durada de maniobres i nivells inicials
- Taula amb registres dels darrers 30 dies
- Filtratge per tipus de maniobra

### 🔹 Paràmetres
- Visualització de la configuració actual
- Informació de l'estat del sistema
- Funcions de manteniment

## ⚙️ Configuració (`config.json`)

```json
{
  "mqtt_broker": "192.168.1.43",
  "mqtt_port": 1883,
  "victron_device_id": "2ccf6734efd2",
  "hora_maniobra": "12:00",
  "durada_max_maniobra": 3,
  "durada_max_manual": 10,
  "relay3_gpio": 6,
  "relay4_gpio": 5,
  "periode_manteniment": 10,
  "temps_manteniment": 10
}
```

## 🔧 Lògica de Control

### Control Automàtic
- **Arrencada programada**: Per defecte a les 12:00 (configurable)
- **Condicions d'arrencada**: Dipòsit baix > 15% i dipòsit alt < 99%
- **Durada màxima**: 3 minuts (configurable 2-5 min)
- **Aturada automàtica**: Per temps màxim o condicions de nivells

### Control Manual
- **Activació**: Botó al dashboard
- **Durada màxima**: 10 minuts (configurable 5-30 min)
- **Aturada**: Manual o automàtica per temps/nivells

### Manteniment
- **Freqüència**: Cada 10 dies sense maniobra amb arrencada
- **Durada**: 10 segons (configurable 5-15 s)

## 🧪 Testing

```bash
# Test de funcionalitat bàsica
python test_app.py

# Test de connexió MQTT
python test_mqtt.py
```

## 📁 Estructura del Projecte

```
├── app.py                 # Aplicació principal
├── config.json           # Configuració del sistema
├── requirements.txt      # Dependències Python
├── start_dashboard.sh    # Script d'inici
├── test_app.py          # Tests de funcionalitat
├── test_mqtt.py         # Test de connexió MQTT
└── README.md            # Documentació
```

## 🔗 Accés

Dashboard disponible a: `http://<IP_RASPBERRY>:8501`

## 🛠️ Desenvolupament

El sistema està dissenyat de manera modular per facilitar ampliacions futures:

- **Estructura de classes**: `WaterPumpController`, `TankLevels`, `ManeuverRecord`
- **Gestió d'errors**: Validació completa i gestió d'excepcions
- **Mock objects**: Desenvolupament sense hardware real
- **Logging**: Registre detallat d'esdeveniments
- **Threading**: Operacions MQTT i control en threads separats

## 📞 Suport

Per a problemes o suggeriments, consultar la documentació del projecte o crear un issue al repositori.
