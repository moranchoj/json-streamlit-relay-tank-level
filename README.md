# Sistema de Control de Bomba d'Aigua

Sistema de control automàtic d'una bomba d'aigua amb monitorització en temps real, gestió de maniobres i registre d'històrics.

## Descripció

Aquest projecte implementa un dashboard web per al control d'una bomba d'aigua que integra:

- **Venus OS GX Tank 140** per la lectura dels nivells de dipòsits via MQTT
- **Raspberry Pi 4B** per la lògica de control i dashboard
- **HAT PiRelay-V2** per al control físic dels relés

## Característiques Principals

### ✅ Funcionalitats Implementades

- **Inicialització única per sessió**: GPIO i MQTT només s'inicialitzen una vegada, evitant errors de GPIOPinInUse
- **Actualització automàtica**: Els nivells es refresquen cada 3 segons en temps real
- **Sincronització correcta**: Estat sincronitzat entre el thread MQTT i la interfície d'usuari
- **Lògica inversa de relés**: Suport per lògica directa/inversa segons paràmetre `active_high` en configuració
- **Maniobres manual i automàtica**: Funcionalitat completa amb controls de seguretat
- **Gestió d'estat de relés**: Evita estats inconsistents amb gestió adequada
- **Robustesa del codi**: Gestió d'errors i codi modularitzat amb comentaris

### 🎛️ Dashboard amb 3 Pestanyes

1. **🔍 Monitorització**: Nivells en temps real, estat relés, controls manuals
2. **📊 Històric**: Gràfics de tendències i taules de dades històriques  
3. **⚙️ Paràmetres**: Configuració completa del sistema

### 🔒 Característiques de Seguretat

- No inicia si dipòsit baix ≤ 15% o dipòsit alt ≥ 99%
- Aturada automàtica per temps límit o condicions de seguretat
- Neteja adequada dels recursos GPIO
- Persistència de sessió evita múltiples inicialitzacions

## Instal·lació

1. **Clonar el repositori**
   ```bash
   git clone https://github.com/moranchoj/json-streamlit-relay-tank-level.git
   cd json-streamlit-relay-tank-level
   ```

2. **Instal·lar dependències**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar el sistema**
   - Editar `config.json` amb la configuració del vostre sistema
   - Configurar broker MQTT, GPIO pins i paràmetres operacionals

4. **Executar l'aplicació**
   ```bash
   streamlit run app.py
   ```
   
   O utilitzar l'script d'inici:
   ```bash
   ./start_dashboard.sh
   ```

## Configuració

### Paràmetres Principals (`config.json`)

```json
{
  "mqtt_broker": "192.168.1.43",
  "victron_device_id": "2ccf6734efd2",
  "relay3_gpio": 6,
  "relay3_active_high": false,
  "relay4_gpio": 5, 
  "relay4_active_high": false,
  "hora_maniobra": "12:00",
  "durada_max_maniobra": 3,
  "durada_max_manual": 10
}
```

### Lògica dels Relés

- **Relay 3**: S'activa si dipòsit baix > 15%
- **Relay 4**: S'activa si dipòsit alt < 99%
- **active_high**: `true` = lògica directa, `false` = lògica inversa

## Ús del Sistema

### Maniobra Automàtica
- Programada diàriament (per defecte 12:00)
- Durada màxima configurable (2-5 min)
- Aturada automàtica per temps o nivells crítics

### Maniobra Manual  
- Activació des del dashboard
- Durada màxima configurable (5-30 min)
- Controls de seguretat abans d'iniciar

### Manteniment
- Maniobres curtes per evitar bloquejos
- Activació automàtica si no hi ha hagut operació recent

## Scripts Auxiliars

- **`test_mqtt.py`**: Verificar connexió MQTT i recepció de nivells
- **`demo_mode.py`**: Mode demostració sense hardware real
- **`start_dashboard.sh`**: Script d'inici amb entorn virtual
- **`install_autostart_service.sh`**: Instal·lar servei systemd per autoarranc

## Autoarranc (Systemd)

Per configurar l'inici automàtic al boot:

```bash
sudo ./install_autostart_service.sh
```

El servei es pot gestionar amb:
```bash
sudo systemctl start pump-control-dashboard
sudo systemctl stop pump-control-dashboard  
sudo systemctl status pump-control-dashboard
```

## Mode Demostració

Per provar l'aplicació sense hardware:

1. Executar el simulador:
   ```bash
   python3 demo_mode.py
   ```

2. En un altre terminal, iniciar l'aplicació:
   ```bash
   streamlit run app.py
   ```

## Arquitectura

### Classes Principals

- **ConfigManager**: Gestió de configuració JSON
- **RelayController**: Control GPIO amb lògica directa/inversa
- **MQTTClient**: Comunicació amb Venus OS en thread separat
- **PumpController**: Coordinació de totes les operacions
- **HistoryLogger**: Registre d'operacions en CSV

### Característiques Tècniques

- **Detecció automàtica de Raspberry Pi**: Mode simulació si no detecta hardware
- **Gestió de sessió Streamlit**: Evita reinicialitzacions
- **Threading per MQTT**: No bloqueja la interfície d'usuari
- **Logging complet**: Registre d'events i errors
- **Persistència de dades**: Històric en format CSV

## Resolució de Problemes

### Errors Comuns

1. **GPIOPinInUse**: El sistema inicialitza GPIO només una vegada per sessió
2. **MQTT desconnectat**: Verificar broker i xarxa amb `test_mqtt.py`  
3. **Permisos GPIO**: Executar com a usuari amb permisos GPIO o afegir a grup `gpio`

### Debug

- Logs disponibles a `pump_control.log`
- Mode verbose activat per defecte
- Dashboard mostra estat de connexions en temps real

## Contribució

1. Fork del repositori
2. Crear branch de funcionalitat
3. Commit dels canvis
4. Push al branch
5. Crear Pull Request

## Llicència

Aquest projecte està sota llicència MIT.

## Suport

Per problemes o preguntes, crear un issue al repositori GitHub.
