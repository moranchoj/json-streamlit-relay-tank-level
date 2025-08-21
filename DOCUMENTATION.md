# Sistema de Control de Bomba d'Aigua - Documentació

## Descripció

Aquest projecte implementa un sistema complet de control automàtic d'una bomba d'aigua amb monitorització en temps real, utilitzant **Streamlit** per al dashboard web, **MQTT** per la lectura de nivells des de Venus OS, i **gpiozero** per al control de relés.

## Funcionalitats Implementades

### ✅ Connectivitat MQTT
- Connexió al broker MQTT del Venus OS
- Lectura automàtica dels nivells dels dipòsits via topics específics
- Gestió de reconnexió automàtica
- Validació de dades recents

### ✅ Control de Relés
- Control de GPIO via gpiozero (Relay 3 i 4)
- Activació automàtica segons els nivells:
  - Relay 3: actiu si dipòsit baix > 15%
  - Relay 4: actiu si dipòsit alt < 99%
- Desactivació automàtica quan es compleixen condicions d'aturada

### ✅ Lògica de Control Automàtic
- **Maniobres programades**: Segons l'hora configurada (per defecte 12:00)
- **Condicions d'arrencada**: Nivells adequats dels dipòsits
- **Durada màxima**: Control automàtic amb aturada per temps o condicions
- **Manteniment automàtic**: Execució periòdica si no hi ha maniobres regulars

### ✅ Control Manual
- Botó d'arrencada manual des del dashboard
- Durada màxima configurable (per defecte 10 minuts)
- Botó d'aturada d'emergència
- Validació de condicions abans de l'arrencada

### ✅ Dashboard Streamlit

#### 🔍 Pestanya Monitorització
- **Gauges de nivells**: Dipòsit baix i alt amb indicadors de perill
- **Estat dels sistema**: Relés, maniobres, connexió MQTT
- **Informació temporal**: Hora actual, última maniobra, propera programada
- **Controls manuals**: Botons d'arrencada/aturada amb validacions
- **Indicadors de progrés**: Barres de temps durant les maniobres

#### 📊 Pestanya Històric
- **Gràfics de durada**: Evolució temporal de les maniobres
- **Gràfics de tipus**: Distribució per tipus de maniobra
- **Evolució de nivells**: Tendències dels nivells inicials
- **Estadístiques**: Resum del període seleccionat
- **Taula de dades**: Últims 30 dies amb funcionalitat de descàrrega
- **Manteniment**: Neteja de dades antigues

#### ⚙️ Pestanya Paràmetres
- **Configuració MQTT**: IP del broker i port
- **Temps d'operació**: Hora programada i durades màximes
- **Configuració de manteniment**: Període i durada
- **Retenció de dades**: Anys d'històric a mantenir
- **Ubicació del sistema**: Identificació de la instal·lació

### ✅ Gestió d'Històric
- **Persistència CSV**: Guardat automàtic de totes les maniobres
- **Dades registrades**: Temps, durades, nivells inicials/finals, tipus
- **Retenció configurable**: Neteja automàtica de dades antigues
- **Exportació**: Descàrrega de dades en format CSV

### ✅ Configuració
- **Carrega automàtica**: Des del fitxer `config.json`
- **Modificació en línia**: Via interfície web
- **Guardat persistent**: Actualització del fitxer de configuració
- **Validació**: Rangs adequats per tots els paràmetres

## Estructura del Codi

```
app.py
├── ConfigManager          # Gestió de configuració
├── TankLevelMonitor        # Monitor MQTT de nivells
├── RelayController         # Control dels relés GPIO
├── PumpController          # Lògica principal de control
├── HistoricManager         # Gestió de l'històric
├── Dashboard Functions     # Interfície Streamlit
│   ├── monitoring_tab()    # Pestanya de monitorització
│   ├── history_tab()       # Pestanya d'històric
│   └── parameters_tab()    # Pestanya de paràmetres
└── main()                  # Funció principal i lògica automàtica
```

## Validacions i Seguretat

### ✅ Validacions Implementades
- **Nivells de seguretat**: No arrencada si dipòsit baix ≤ 15% o alt ≥ 99%
- **Dades recents**: Verificació de timestamps MQTT
- **Durades màximes**: Aturada automàtica per temps
- **Connexió MQTT**: Indicadors d'estat i reconnexió
- **Històric**: Validació de dades abans de processar

### ✅ Gestió d'Errors
- **Logging complet**: Informació detallada de totes les operacions
- **Fallbacks**: Objectes mock quan no hi ha hardware disponible
- **Excepcions controlades**: Captura i gestió d'errors de connexió
- **Interfície resilient**: L'aplicació continua funcionant amb dades limitades

## Proves i Test

El sistema inclou:
- **Script de test** (`test_system.py`): Genera dades d'històric de prova
- **Simulació de nivells**: Per proves sense connectivitat MQTT real
- **Validació visual**: Dashboard complet amb dades de mostra
- **Test de funcionalitats**: Botons, configuració, i navegació

## Execució

```bash
# Instal·lació de dependències
pip install -r requirements.txt

# Execució de l'aplicació
streamlit run app.py

# Generar dades de prova (opcional)
python test_system.py
```

## Accés al Dashboard

L'aplicació està disponible a `http://localhost:8501` amb auto-refresh cada 5 segons per a monitorització en temps real.

## Compatibilitat Hardware

- **Development**: Objectes mock per desenvolupament sense hardware
- **Production**: Compatible amb Raspberry Pi i HAT PiRelay-V2
- **MQTT**: Compatible amb Venus OS i qualsevol broker MQTT
- **GPIO**: Utilitzant gpiozero per màxima compatibilitat