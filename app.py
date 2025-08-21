#!/usr/bin/env python3
"""
Dashboard de Control de Bomba d'Aigua
Sistema de control automàtic d'una bomba d'aigua amb monitorització en temps real.

Sistema integrat per:
- Venus OS GX Tank 140 (lectura nivells via MQTT)
- Raspberry Pi 4B (lògica control i dashboard)
- HAT PiRelay-V2 (control físic relés)
"""

import streamlit as st
import json
import logging
import time
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pump_control.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuració de la pàgina Streamlit
st.set_page_config(
    page_title="Control Bomba d'Aigua",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

class ConfigManager:
    """Gestor de configuració del sistema"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Carrega la configuració des del fitxer JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info("Configuració carregada correctament")
            return config
        except Exception as e:
            logger.error(f"Error carregant configuració: {e}")
            return self.get_default_config()
    
    def save_config(self) -> bool:
        """Guarda la configuració al fitxer JSON"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info("Configuració guardada correctament")
            return True
        except Exception as e:
            logger.error(f"Error guardant configuració: {e}")
            return False
    
    def get_default_config(self) -> Dict[str, Any]:
        """Retorna configuració per defecte"""
        return {
            "mqtt_broker": "192.168.1.43",
            "mqtt_port": 1883,
            "mqtt_keepalive_s": 3,
            "victron_device_id": "2ccf6734efd2",
            "hora_maniobra": "12:00",
            "durada_max_maniobra": 3,
            "durada_max_manual": 10,
            "periode_manteniment": 10,
            "temps_manteniment": 10,
            "retencio_historic_anys": 5,
            "relay3_gpio": 6,
            "relay3_active_high": False,
            "relay4_gpio": 5,
            "relay4_active_high": False,
            "email_enabled": False,
            "email_smtp": "smtp.gmail.com",
            "email_port": 465,
            "email_user": "usuari@gmail.com",
            "email_pass": "contrasenya",
            "email_to": "destinatari@gmail.com",
            "ubicacio": "Instal·lació A"
        }
    
    def get(self, key: str, default=None):
        """Obté un valor de configuració"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Estableix un valor de configuració"""
        self.config[key] = value

class RelayController:
    """Controlador dels relés amb suport per lògica directa/inversa"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.gpio_initialized = False
        self.relays = {}
        
        # Inicialitzar GPIO només una vegada
        if not st.session_state.get('gpio_initialized', False):
            self._initialize_gpio()
            st.session_state.gpio_initialized = True
    
    def _initialize_gpio(self):
        """Inicialitza els pins GPIO dels relés"""
        try:
            # Importar RPi.GPIO només si estem en Raspberry Pi
            if self._is_raspberry_pi():
                import RPi.GPIO as GPIO
                
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                
                # Configurar pins dels relés
                relay3_pin = self.config.get('relay3_gpio', 6)
                relay4_pin = self.config.get('relay4_gpio', 5)
                
                GPIO.setup(relay3_pin, GPIO.OUT)
                GPIO.setup(relay4_pin, GPIO.OUT)
                
                # Establir estat inicial (apagat)
                self.set_relay_state(3, False)
                self.set_relay_state(4, False)
                
                self.relays[3] = {'pin': relay3_pin, 'active_high': self.config.get('relay3_active_high', False)}
                self.relays[4] = {'pin': relay4_pin, 'active_high': self.config.get('relay4_active_high', False)}
                
                logger.info("GPIO inicialitzat correctament")
                self.gpio_initialized = True
            else:
                logger.warning("No s'està executant en Raspberry Pi - mode simulació")
                self.gpio_initialized = True
                
        except Exception as e:
            logger.error(f"Error inicialitzant GPIO: {e}")
    
    def _is_raspberry_pi(self) -> bool:
        """Detecta si s'està executant en Raspberry Pi"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                return 'raspberry pi' in f.read().lower()
        except:
            return False
    
    def set_relay_state(self, relay_num: int, active: bool):
        """Estableix l'estat d'un relé tenint en compte la lògica directa/inversa"""
        try:
            if not self.gpio_initialized:
                logger.warning("GPIO no inicialitzat")
                return
            
            if relay_num not in self.relays:
                logger.error(f"Relé {relay_num} no configurat")
                return
            
            relay_info = self.relays[relay_num]
            pin = relay_info['pin']
            active_high = relay_info['active_high']
            
            # Aplicar lògica directa/inversa
            gpio_value = active if active_high else not active
            
            if self._is_raspberry_pi():
                import RPi.GPIO as GPIO
                GPIO.output(pin, GPIO.HIGH if gpio_value else GPIO.LOW)
            
            # Actualitzar estat en session_state
            if 'relay_states' not in st.session_state:
                st.session_state.relay_states = {}
            st.session_state.relay_states[relay_num] = active
            
            logger.info(f"Relé {relay_num} {'activat' if active else 'desactivat'} (GPIO {pin} = {'HIGH' if gpio_value else 'LOW'})")
            
        except Exception as e:
            logger.error(f"Error establint estat relé {relay_num}: {e}")
    
    def get_relay_state(self, relay_num: int) -> bool:
        """Obté l'estat actual d'un relé"""
        if 'relay_states' not in st.session_state:
            st.session_state.relay_states = {}
        return st.session_state.relay_states.get(relay_num, False)
    
    def cleanup(self):
        """Neteja resources GPIO"""
        try:
            if self.gpio_initialized and self._is_raspberry_pi():
                import RPi.GPIO as GPIO
                GPIO.cleanup()
                logger.info("GPIO netejat")
        except Exception as e:
            logger.error(f"Error netejant GPIO: {e}")

class MQTTClient:
    """Client MQTT per rebre nivells dels dipòsits"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.client = None
        self.connected = False
        self.tank_levels = {'low': 0.0, 'high': 0.0}
        
        # Inicialitzar MQTT només una vegada per sessió
        if not st.session_state.get('mqtt_initialized', False):
            self._initialize_mqtt()
            st.session_state.mqtt_initialized = True
    
    def _initialize_mqtt(self):
        """Inicialitza la connexió MQTT"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            broker = self.config.get('mqtt_broker', 'localhost')
            port = self.config.get('mqtt_port', 1883)
            keepalive = self.config.get('mqtt_keepalive_s', 60)
            
            self.client.connect(broker, port, keepalive)
            self.client.loop_start()
            
            logger.info(f"Connexió MQTT iniciada amb {broker}:{port}")
            
        except Exception as e:
            logger.error(f"Error inicialitzant MQTT: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback quan es connecta al broker MQTT"""
        if rc == 0:
            self.connected = True
            device_id = self.config.get('victron_device_id', '')
            
            # Subscriure's als tòpics dels nivells dels dipòsits
            topics = [
                f"N/{device_id}/tank/3/Level",  # Dipòsit baix
                f"N/{device_id}/tank/4/Level"   # Dipòsit alt
            ]
            
            for topic in topics:
                client.subscribe(topic)
                logger.info(f"Subscrit a {topic}")
                
            st.session_state.mqtt_connected = True
            
        else:
            logger.error(f"Error connectant MQTT: {rc}")
            self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback quan es rep un missatge MQTT"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            
            # Parsejar el JSON del missatge
            data = json.loads(payload)
            value = data.get('value', 0)
            
            # Determinar quin dipòsit és segons el tòpic
            if '/tank/3/Level' in topic:
                self.tank_levels['low'] = value * 100  # Convertir a percentatge
                st.session_state.tank_low_level = value * 100
            elif '/tank/4/Level' in topic:
                self.tank_levels['high'] = value * 100  # Convertir a percentatge
                st.session_state.tank_high_level = value * 100
            
            # Actualitzar timestamp última actualització
            st.session_state.last_update = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processant missatge MQTT: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback quan es desconnecta del broker MQTT"""
        self.connected = False
        st.session_state.mqtt_connected = False
        logger.warning("Desconnectat del broker MQTT")
    
    def get_tank_levels(self) -> Dict[str, float]:
        """Obté els nivells actuals dels dipòsits"""
        return {
            'low': st.session_state.get('tank_low_level', 0.0),
            'high': st.session_state.get('tank_high_level', 0.0)
        }
    
    def is_connected(self) -> bool:
        """Comprova si la connexió MQTT està activa"""
        return st.session_state.get('mqtt_connected', False)

class HistoryLogger:
    """Gestor de l'històric d'operacions"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.csv_file = "historic.csv"
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Assegura que el fitxer CSV existeixi amb capçaleres"""
        if not os.path.exists(self.csv_file):
            headers = [
                "data_inici", "hora_inici", "data_final", "hora_final", 
                "durada_segons", "nivell_baix_inici", "nivell_alt_inici",
                "nivell_baix_final", "nivell_alt_final", "tipus_maniobra",
                "motiu_aturada", "ubicacio"
            ]
            
            try:
                with open(self.csv_file, 'w', encoding='utf-8') as f:
                    f.write(";".join(headers) + "\n")
                logger.info("Fitxer històric CSV creat")
            except Exception as e:
                logger.error(f"Error creant fitxer CSV: {e}")
    
    def log_operation(self, start_time: datetime, end_time: datetime, 
                     start_levels: Dict[str, float], end_levels: Dict[str, float],
                     operation_type: str, stop_reason: str):
        """Registra una operació a l'històric"""
        try:
            duration = (end_time - start_time).total_seconds()
            ubicacio = self.config.get('ubicacio', 'N/A')
            
            record = [
                start_time.strftime('%Y-%m-%d'),
                start_time.strftime('%H:%M:%S'),
                end_time.strftime('%Y-%m-%d'), 
                end_time.strftime('%H:%M:%S'),
                str(duration),
                str(start_levels.get('low', 0)),
                str(start_levels.get('high', 0)),
                str(end_levels.get('low', 0)),
                str(end_levels.get('high', 0)),
                operation_type,
                stop_reason,
                ubicacio
            ]
            
            with open(self.csv_file, 'a', encoding='utf-8') as f:
                f.write(";".join(record) + "\n")
            
            logger.info(f"Operació registrada: {operation_type} - {duration:.1f}s")
            
        except Exception as e:
            logger.error(f"Error registrant operació: {e}")
    
    def get_recent_history(self, days: int = 30) -> pd.DataFrame:
        """Obté l'històric recent en format DataFrame"""
        try:
            if not os.path.exists(self.csv_file):
                return pd.DataFrame()
            
            df = pd.read_csv(self.csv_file, sep=';', encoding='utf-8')
            
            # Filtrar per dies recents
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['data_inici'] + ' ' + df['hora_inici'])
                cutoff_date = datetime.now() - timedelta(days=days)
                df = df[df['datetime'] >= cutoff_date]
                df = df.sort_values('datetime', ascending=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Error llegint històric: {e}")
            return pd.DataFrame()
    
    def cleanup_old_records(self):
        """Neteja registres antics segons la configuració de retenció"""
        try:
            retention_years = self.config.get('retencio_historic_anys', 5)
            cutoff_date = datetime.now() - timedelta(days=retention_years * 365)
            
            df = pd.read_csv(self.csv_file, sep=';', encoding='utf-8')
            
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['data_inici'] + ' ' + df['hora_inici'])
                df_filtered = df[df['datetime'] >= cutoff_date]
                
                if len(df_filtered) < len(df):
                    df_filtered.drop('datetime', axis=1).to_csv(self.csv_file, sep=';', index=False, encoding='utf-8')
                    removed_count = len(df) - len(df_filtered)
                    logger.info(f"Netejats {removed_count} registres antics de l'històric")
                    
        except Exception as e:
            logger.error(f"Error netejant històric: {e}")

class PumpController:
    """Controlador principal de la bomba"""
    
    def __init__(self, config: ConfigManager, relay_controller: RelayController, mqtt_client: MQTTClient):
        self.config = config
        self.relay_controller = relay_controller
        self.mqtt_client = mqtt_client
        self.history_logger = HistoryLogger(config)
        
        # Inicialitzar estat de la bomba
        if 'pump_state' not in st.session_state:
            st.session_state.pump_state = {
                'running': False,
                'mode': 'stopped',  # stopped, auto, manual, maintenance
                'start_time': None,
                'duration_limit': 0,
                'last_operation': None,
                'next_scheduled': None,
                'auto_enabled': True
            }
            
        # Calcular propera maniobra programada
        self._update_next_scheduled_time()
    
    def start_manual_operation(self):
        """Inicia maniobra manual"""
        try:
            levels = self.mqtt_client.get_tank_levels()
            
            # Comprovar condicions per iniciar
            if levels['low'] <= 15:
                st.error("No es pot iniciar: dipòsit baix ≤ 15%")
                return False
            
            if levels['high'] >= 99:
                st.error("No es pot iniciar: dipòsit alt ≥ 99%")
                return False
            
            # Configurar estat
            duration_minutes = self.config.get('durada_max_manual', 10)
            
            st.session_state.pump_state.update({
                'running': True,
                'mode': 'manual',
                'start_time': datetime.now(),
                'duration_limit': duration_minutes * 60,  # convertir a segons
                'start_levels': levels.copy()
            })
            
            # Activar relés segons nivells
            self._update_relays()
            
            logger.info(f"Maniobra manual iniciada (durada màx: {duration_minutes} min)")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciant maniobra manual: {e}")
            return False
    
    def stop_operation(self, reason: str = "manual"):
        """Atura la maniobra actual"""
        try:
            if st.session_state.pump_state['running']:
                # Desactivar tots els relés
                self.relay_controller.set_relay_state(3, False)
                self.relay_controller.set_relay_state(4, False)
                
                # Obtenir dades per l'històric
                start_time = st.session_state.pump_state.get('start_time')
                start_levels = st.session_state.pump_state.get('start_levels', {'low': 0, 'high': 0})
                end_time = datetime.now()
                end_levels = self.mqtt_client.get_tank_levels()
                operation_mode = st.session_state.pump_state.get('mode', 'unknown')
                
                duration = 0
                if start_time:
                    duration = (end_time - start_time).total_seconds()
                    
                    # Registrar a l'històric
                    self.history_logger.log_operation(
                        start_time, end_time, start_levels, end_levels,
                        operation_mode, reason
                    )
                
                # Actualitzar estat
                st.session_state.pump_state.update({
                    'running': False,
                    'mode': 'stopped',
                    'start_time': None,
                    'duration_limit': 0,
                    'last_operation': {
                        'end_time': end_time,
                        'duration': duration,
                        'reason': reason,
                        'mode': operation_mode
                    }
                })
                
                logger.info(f"Maniobra aturada ({reason}) - durada: {duration:.1f}s")
                return True
        
        except Exception as e:
            logger.error(f"Error aturant maniobra: {e}")
            return False
    
    def _update_relays(self):
        """Actualitza l'estat dels relés segons les condicions"""
        try:
            if not st.session_state.pump_state['running']:
                return
            
            levels = self.mqtt_client.get_tank_levels()
            
            # Lògica dels relés
            # Relay 3: activa si dipòsit baix > 15%
            relay3_should_be_active = levels['low'] > 15
            self.relay_controller.set_relay_state(3, relay3_should_be_active)
            
            # Relay 4: activa si dipòsit alt < 99%
            relay4_should_be_active = levels['high'] < 99
            self.relay_controller.set_relay_state(4, relay4_should_be_active)
            
            # Comprovar condicions d'aturada automàtica
            self._check_auto_stop_conditions(levels)
            
        except Exception as e:
            logger.error(f"Error actualitzant relés: {e}")
    
    def _check_auto_stop_conditions(self, levels: Dict[str, float]):
        """Comprova les condicions d'aturada automàtica"""
        try:
            if not st.session_state.pump_state['running']:
                return
            
            start_time = st.session_state.pump_state.get('start_time')
            duration_limit = st.session_state.pump_state.get('duration_limit', 0)
            
            if start_time:
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Aturada per temps límit
                if elapsed >= duration_limit:
                    self.stop_operation("temps_limit")
                    return
                
                # Aturada per nivells
                if levels['low'] <= 15:
                    self.stop_operation("nivell_baix")
                    return
                
                if levels['high'] >= 99:
                    self.stop_operation("nivell_alt")
                    return
                    
        except Exception as e:
            logger.error(f"Error comprovant condicions aturada: {e}")
    
    def update(self):
        """Actualitza l'estat del controlador (cridar periòdicament)"""
        if st.session_state.pump_state['running']:
            self._update_relays()
        else:
            # Comprovar si cal executar maniobra automàtica
            self._check_scheduled_operation()
    
    def _update_next_scheduled_time(self):
        """Actualitza l'hora de la propera maniobra programada"""
        try:
            hora_config = self.config.get('hora_maniobra', '12:00')
            hour, minute = map(int, hora_config.split(':'))
            
            now = datetime.now()
            scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Si ja ha passat l'hora d'avui, programar per demà
            if scheduled_today <= now:
                scheduled_next = scheduled_today + timedelta(days=1)
            else:
                scheduled_next = scheduled_today
            
            st.session_state.pump_state['next_scheduled'] = scheduled_next
            logger.info(f"Propera maniobra programada: {scheduled_next.strftime('%Y-%m-%d %H:%M')}")
            
        except Exception as e:
            logger.error(f"Error calculant propera maniobra: {e}")
    
    def _check_scheduled_operation(self):
        """Comprova si cal executar la maniobra programada"""
        try:
            if not st.session_state.pump_state.get('auto_enabled', True):
                return
            
            next_scheduled = st.session_state.pump_state.get('next_scheduled')
            if not next_scheduled:
                return
            
            now = datetime.now()
            
            # Comprovar si és hora de la maniobra (amb marge de 1 minut)
            time_diff = abs((now - next_scheduled).total_seconds())
            if time_diff <= 60:  # Dins del marge d'1 minut
                logger.info("Iniciant maniobra automàtica programada")
                self.start_auto_operation()
                
        except Exception as e:
            logger.error(f"Error comprovant maniobra programada: {e}")
    
    def start_auto_operation(self):
        """Inicia maniobra automàtica"""
        try:
            levels = self.mqtt_client.get_tank_levels()
            
            # Comprovar condicions per iniciar
            if levels['low'] <= 15:
                logger.warning("Maniobra automàtica cancel·lada: dipòsit baix ≤ 15%")
                self._reschedule_operation()
                return False
            
            if levels['high'] >= 99:
                logger.warning("Maniobra automàtica cancel·lada: dipòsit alt ≥ 99%")
                self._reschedule_operation()
                return False
            
            # Configurar estat
            duration_minutes = self.config.get('durada_max_maniobra', 3)
            
            st.session_state.pump_state.update({
                'running': True,
                'mode': 'auto',
                'start_time': datetime.now(),
                'duration_limit': duration_minutes * 60,  # convertir a segons
                'start_levels': levels.copy()
            })
            
            # Activar relés segons nivells
            self._update_relays()
            
            # Programar propera maniobra
            self._update_next_scheduled_time()
            
            logger.info(f"Maniobra automàtica iniciada (durada màx: {duration_minutes} min)")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciant maniobra automàtica: {e}")
            return False
    
    def start_maintenance_operation(self):
        """Inicia maniobra de manteniment"""
        try:
            levels = self.mqtt_client.get_tank_levels()
            
            # El manteniment és menys restrictiu en condicions
            if levels['low'] <= 10:  # Límit més baix per manteniment
                logger.warning("Maniobra manteniment cancel·lada: dipòsit baix ≤ 10%")
                return False
            
            # Configurar estat
            duration_seconds = self.config.get('temps_manteniment', 10)
            
            st.session_state.pump_state.update({
                'running': True,
                'mode': 'maintenance',
                'start_time': datetime.now(),
                'duration_limit': duration_seconds,  # ja en segons
                'start_levels': levels.copy()
            })
            
            # Activar tots els relés per manteniment
            self.relay_controller.set_relay_state(3, True)
            self.relay_controller.set_relay_state(4, True)
            
            logger.info(f"Maniobra manteniment iniciada (durada: {duration_seconds}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciant maniobra manteniment: {e}")
            return False
    
    def _reschedule_operation(self):
        """Reprograma la maniobra per demà"""
        self._update_next_scheduled_time()
        logger.info("Maniobra reprogramada per demà")
    
    def enable_auto_mode(self, enabled: bool):
        """Activa/desactiva el mode automàtic"""
        st.session_state.pump_state['auto_enabled'] = enabled
        logger.info(f"Mode automàtic {'activat' if enabled else 'desactivat'}")
    
    def get_next_scheduled_time(self) -> Optional[datetime]:
        """Obté l'hora de la propera maniobra programada"""
        return st.session_state.pump_state.get('next_scheduled')
    
    def is_auto_enabled(self) -> bool:
        """Comprova si el mode automàtic està activat"""
        return st.session_state.pump_state.get('auto_enabled', True)

# Funcions d'inicialització globals
def initialize_session_state():
    """Inicialitza l'estat de sessió de Streamlit"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.gpio_initialized = False
        st.session_state.mqtt_initialized = False
        st.session_state.mqtt_connected = False
        st.session_state.tank_low_level = 0.0
        st.session_state.tank_high_level = 0.0
        st.session_state.last_update = datetime.now()
        st.session_state.relay_states = {3: False, 4: False}

def get_system_controllers():
    """Obté els controladors del sistema (singleton per sessió)"""
    if 'controllers' not in st.session_state:
        config = ConfigManager()
        relay_controller = RelayController(config)
        mqtt_client = MQTTClient(config)
        pump_controller = PumpController(config, relay_controller, mqtt_client)
        
        st.session_state.controllers = {
            'config': config,
            'relay': relay_controller,
            'mqtt': mqtt_client,
            'pump': pump_controller,
            'history': pump_controller.history_logger
        }
    
    return st.session_state.controllers

def main():
    """Funció principal de l'aplicació"""
    # Inicialitzar estat de sessió
    initialize_session_state()
    
    # Obter controladors
    controllers = get_system_controllers()
    
    # Auto-refresh cada 3 segons
    st_autorefresh(interval=3000, key="auto_refresh")
    
    # Actualitzar controlador de bomba
    controllers['pump'].update()
    
    # Títol principal
    st.title("💧 Control Bomba d'Aigua")
    
    # Crear pestanyes
    tab_monitoring, tab_history, tab_parameters = st.tabs(["🔍 Monitorització", "📊 Històric", "⚙️ Paràmetres"])
    
    with tab_monitoring:
        render_monitoring_tab(controllers)
    
    with tab_history:
        render_history_tab(controllers)
    
    with tab_parameters:
        render_parameters_tab(controllers)

def render_monitoring_tab(controllers):
    """Renderitza la pestanya de monitorització"""
    st.header("Monitorització en Temps Real")
    
    # Obtenir dades actuals
    mqtt_client = controllers['mqtt']
    pump_controller = controllers['pump']
    relay_controller = controllers['relay']
    
    levels = mqtt_client.get_tank_levels()
    pump_state = st.session_state.pump_state
    last_update = st.session_state.get('last_update', datetime.now())
    
    # Layout en columnes
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Dipòsit Baix")
        st.metric(
            label="Nivell (%)",
            value=f"{levels['low']:.1f}%",
            delta=None
        )
        
        # Indicador visual
        color = "🔴" if levels['low'] <= 15 else "🟡" if levels['low'] <= 50 else "🟢"
        st.write(f"{color} {levels['low']:.1f}%")
    
    with col2:
        st.subheader("Dipòsit Alt")
        st.metric(
            label="Nivell (%)",
            value=f"{levels['high']:.1f}%",
            delta=None
        )
        
        # Indicador visual
        color = "🟢" if levels['high'] < 99 else "🔴"
        st.write(f"{color} {levels['high']:.1f}%")
    
    with col3:
        st.subheader("Estat Sistema")
        
        # Estat bomba
        if pump_state['running']:
            st.write("🟢 **Bomba en marxa**")
            st.write(f"Mode: {pump_state['mode']}")
            
            if pump_state.get('start_time'):
                elapsed = datetime.now() - pump_state['start_time']
                st.write(f"Temps: {elapsed}")
        else:
            st.write("🔴 **Bomba parada**")
        
        # Estat MQTT
        if mqtt_client.is_connected():
            st.write("🟢 **MQTT connectat**")
        else:
            st.write("🔴 **MQTT desconnectat**")
    
    # Informació de programació automàtica
    st.subheader("Programació Automàtica")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        auto_enabled = pump_controller.is_auto_enabled()
        if st.checkbox("Mode automàtic activat", value=auto_enabled):
            pump_controller.enable_auto_mode(True)
        else:
            pump_controller.enable_auto_mode(False)
    
    with col2:
        next_scheduled = pump_controller.get_next_scheduled_time()
        if next_scheduled:
            st.write("**Propera maniobra:**")
            st.write(next_scheduled.strftime('%d/%m/%Y %H:%M'))
        else:
            st.write("**Propera maniobra:** No programada")
    
    with col3:
        if pump_state.get('last_operation'):
            last_op = pump_state['last_operation']
            st.write("**Última operació:**")
            st.write(f"{last_op['end_time'].strftime('%d/%m/%Y %H:%M')}")
            st.write(f"Durada: {last_op['duration']:.1f}s")
            st.write(f"Motiu aturada: {last_op['reason']}")
    
    # Estat dels relés
    st.subheader("Estat Relés")
    col1, col2 = st.columns(2)
    
    with col1:
        relay3_state = relay_controller.get_relay_state(3)
        icon = "🟢" if relay3_state else "🔴"
        st.write(f"{icon} **Relé 3**: {'Actiu' if relay3_state else 'Inactiu'}")
    
    with col2:
        relay4_state = relay_controller.get_relay_state(4)
        icon = "🟢" if relay4_state else "🔴"
        st.write(f"{icon} **Relé 4**: {'Actiu' if relay4_state else 'Inactiu'}")
    
    # Control manual
    st.subheader("Control Manual")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not pump_state['running']:
            if st.button("🚀 Iniciar Maniobra Manual", type="primary"):
                if pump_controller.start_manual_operation():
                    st.success("Maniobra manual iniciada!")
                    st.rerun()
        else:
            if st.button("⏹️ Aturar Maniobra", type="secondary"):
                if pump_controller.stop_operation("manual"):
                    st.success("Maniobra aturada!")
                    st.rerun()
    
    with col2:
        if not pump_state['running'] and auto_enabled:
            if st.button("🔄 Forçar Maniobra Auto", type="secondary"):
                if pump_controller.start_auto_operation():
                    st.success("Maniobra automàtica forçada iniciada!")
                    st.rerun()
    
    with col3:
        if not pump_state['running']:
            if st.button("🔧 Maniobra Manteniment", type="secondary"):
                if pump_controller.start_maintenance_operation():
                    st.success("Maniobra manteniment iniciada!")
                    st.rerun()
    
    # Informació adicional
    st.subheader("Informació del Sistema")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Última actualització:** {last_update.strftime('%H:%M:%S')}")
        config = controllers['config']
        st.write(f"**Hora programada:** {config.get('hora_maniobra', '12:00')}")
        st.write(f"**Durada màx auto:** {config.get('durada_max_maniobra', 3)} min")
        st.write(f"**Durada màx manual:** {config.get('durada_max_manual', 10)} min")
    
    with col2:
        st.write(f"**Relay 3 GPIO:** {config.get('relay3_gpio', 6)} ({'Directa' if config.get('relay3_active_high', False) else 'Inversa'})")
        st.write(f"**Relay 4 GPIO:** {config.get('relay4_gpio', 5)} ({'Directa' if config.get('relay4_active_high', False) else 'Inversa'})")
        st.write(f"**MQTT Broker:** {config.get('mqtt_broker', 'N/A')}")
        st.write(f"**Dispositiu Victron:** {config.get('victron_device_id', 'N/A')}")

def render_history_tab(controllers):
    """Renderitza la pestanya d'històric"""
    st.header("Històric d'Operacions")
    
    history_logger = controllers['history']
    
    # Selector de període
    col1, col2 = st.columns([1, 3])
    
    with col1:
        period_options = {
            "1 mes": 30,
            "3 mesos": 90,
            "6 mesos": 180,
            "1 any": 365,
            "3 anys": 1095,
            "5 anys": 1825
        }
        
        selected_period = st.selectbox(
            "Període de visualització:",
            options=list(period_options.keys()),
            index=3  # Default: 1 any
        )
        
        days = period_options[selected_period]
    
    with col2:
        if st.button("🗑️ Neteja registres antics"):
            history_logger.cleanup_old_records()
            st.success("Registres antics netejats segons configuració de retenció")
    
    # Obtenir dades històriques
    df = history_logger.get_recent_history(days)
    
    if df.empty:
        st.info("No hi ha dades històriques disponibles per al període seleccionat")
        return
    
    # Estadístiques generals
    st.subheader("Resum del Període")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_operations = len(df)
        st.metric("Total operacions", total_operations)
    
    with col2:
        avg_duration = df['durada_segons'].mean()
        st.metric("Durada mitjana", f"{avg_duration:.1f}s")
    
    with col3:
        auto_operations = len(df[df['tipus_maniobra'] == 'auto'])
        st.metric("Maniobres automàtiques", auto_operations)
    
    with col4:
        manual_operations = len(df[df['tipus_maniobra'] == 'manual'])
        st.metric("Maniobres manual", manual_operations)
    
    # Gràfic de durades
    if len(df) > 1:
        st.subheader("Evolució Temporal")
        
        # Preparar dades per al gràfic
        df_plot = df.copy()
        df_plot['data'] = pd.to_datetime(df_plot['data_inici'])
        df_plot = df_plot.sort_values('data')
        
        # Crear gràfic amb Streamlit
        chart_data = pd.DataFrame({
            'Data': df_plot['data'],
            'Durada (min)': df_plot['durada_segons'] / 60,
            'Nivell Baix Inici (%)': df_plot['nivell_baix_inici'],
            'Nivell Alt Inici (%)': df_plot['nivell_alt_inici']
        })
        
        st.line_chart(chart_data.set_index('Data'))
    
    # Taula detallada
    st.subheader("Detall d'Operacions (30 registres més recents)")
    
    # Preparar columnes per mostrar
    display_columns = [
        'data_inici', 'hora_inici', 'durada_segons', 
        'nivell_baix_inici', 'nivell_alt_inici',
        'tipus_maniobra', 'motiu_aturada'
    ]
    
    if len(df) > 0:
        df_display = df[display_columns].head(30).copy()
        
        # Formatjar columnes
        df_display['durada_segons'] = df_display['durada_segons'].apply(lambda x: f"{x:.1f}s")
        df_display['nivell_baix_inici'] = df_display['nivell_baix_inici'].apply(lambda x: f"{x:.1f}%")
        df_display['nivell_alt_inici'] = df_display['nivell_alt_inici'].apply(lambda x: f"{x:.1f}%")
        
        # Renombrar columnes
        df_display.columns = [
            'Data', 'Hora', 'Durada', 'Nivell Baix (%)', 'Nivell Alt (%)',
            'Tipus', 'Motiu Aturada'
        ]
        
        st.dataframe(df_display, use_container_width=True)
    
    # Anàlisi per tipus de maniobra
    if len(df) > 0:
        st.subheader("Anàlisi per Tipus de Maniobra")
        
        analysis = df.groupby('tipus_maniobra').agg({
            'durada_segons': ['count', 'mean', 'max'],
            'nivell_baix_inici': 'mean',
            'nivell_alt_inici': 'mean'
        }).round(2)
        
        analysis.columns = ['Nombre', 'Durada Mitjana (s)', 'Durada Màxima (s)', 
                           'Nivell Baix Mitjà (%)', 'Nivell Alt Mitjà (%)']
        
        st.dataframe(analysis, use_container_width=True)

def render_parameters_tab(controllers):
    """Renderitza la pestanya de paràmetres"""
    st.header("Configuració del Sistema")
    
    config = controllers['config']
    
    # Configuració MQTT
    st.subheader("Configuració MQTT")
    
    col1, col2 = st.columns(2)
    with col1:
        mqtt_broker = st.text_input("Broker MQTT", value=config.get('mqtt_broker', ''))
        mqtt_port = st.number_input("Port MQTT", value=config.get('mqtt_port', 1883), min_value=1, max_value=65535)
    
    with col2:
        device_id = st.text_input("ID Dispositiu Victron", value=config.get('victron_device_id', ''))
        keepalive = st.number_input("Keepalive (s)", value=config.get('mqtt_keepalive_s', 60), min_value=3, max_value=300)
    
    # Configuració operacional
    st.subheader("Configuració Operacional")
    
    col1, col2 = st.columns(2)
    with col1:
        hora_maniobra = st.time_input("Hora maniobra automàtica", value=datetime.strptime(config.get('hora_maniobra', '12:00'), '%H:%M').time())
        durada_auto = st.slider("Durada màx maniobra auto (min)", min_value=2, max_value=5, value=config.get('durada_max_maniobra', 3))
        durada_manual = st.slider("Durada màx maniobra manual (min)", min_value=5, max_value=30, value=config.get('durada_max_manual', 10))
    
    with col2:
        periode_manteniment = st.slider("Període manteniment (dies)", min_value=7, max_value=15, value=config.get('periode_manteniment', 10))
        temps_manteniment = st.slider("Temps manteniment (s)", min_value=5, max_value=15, value=config.get('temps_manteniment', 10))
        retencio_historic = st.slider("Retenció històric (anys)", min_value=2, max_value=10, value=config.get('retencio_historic_anys', 5))
    
    # Configuració relés
    st.subheader("Configuració Relés")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Relé 3**")
        relay3_gpio = st.number_input("GPIO Relé 3", value=config.get('relay3_gpio', 6), min_value=1, max_value=27)
        relay3_active_high = st.checkbox("Lògica directa Relé 3", value=config.get('relay3_active_high', False))
    
    with col2:
        st.write("**Relé 4**")
        relay4_gpio = st.number_input("GPIO Relé 4", value=config.get('relay4_gpio', 5), min_value=1, max_value=27)
        relay4_active_high = st.checkbox("Lògica directa Relé 4", value=config.get('relay4_active_high', False))
    
    # Altres configuracions
    st.subheader("Altres Configuracions")
    ubicacio = st.text_input("Ubicació del sistema", value=config.get('ubicacio', ''))
    
    # Botó per guardar configuració
    if st.button("💾 Guardar Configuració", type="primary"):
        # Actualitzar configuració
        config.set('mqtt_broker', mqtt_broker)
        config.set('mqtt_port', mqtt_port)
        config.set('victron_device_id', device_id)
        config.set('mqtt_keepalive_s', keepalive)
        config.set('hora_maniobra', hora_maniobra.strftime('%H:%M'))
        config.set('durada_max_maniobra', durada_auto)
        config.set('durada_max_manual', durada_manual)
        config.set('periode_manteniment', periode_manteniment)
        config.set('temps_manteniment', temps_manteniment)
        config.set('retencio_historic_anys', retencio_historic)
        config.set('relay3_gpio', relay3_gpio)
        config.set('relay3_active_high', relay3_active_high)
        config.set('relay4_gpio', relay4_gpio)
        config.set('relay4_active_high', relay4_active_high)
        config.set('ubicacio', ubicacio)
        
        if config.save_config():
            st.success("Configuració guardada correctament!")
            st.info("Reinicia l'aplicació per aplicar tots els canvis")
        else:
            st.error("Error guardant la configuració")

if __name__ == "__main__":
    main()