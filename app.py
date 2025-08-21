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

class PumpController:
    """Controlador principal de la bomba"""
    
    def __init__(self, config: ConfigManager, relay_controller: RelayController, mqtt_client: MQTTClient):
        self.config = config
        self.relay_controller = relay_controller
        self.mqtt_client = mqtt_client
        
        # Inicialitzar estat de la bomba
        if 'pump_state' not in st.session_state:
            st.session_state.pump_state = {
                'running': False,
                'mode': 'stopped',  # stopped, auto, manual, maintenance
                'start_time': None,
                'duration_limit': 0,
                'last_operation': None
            }
    
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
                
                # Actualitzar estat
                start_time = st.session_state.pump_state.get('start_time')
                duration = 0
                if start_time:
                    duration = (datetime.now() - start_time).total_seconds()
                
                st.session_state.pump_state.update({
                    'running': False,
                    'mode': 'stopped',
                    'start_time': None,
                    'duration_limit': 0,
                    'last_operation': {
                        'end_time': datetime.now(),
                        'duration': duration,
                        'reason': reason
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
            'pump': pump_controller
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
    
    col1, col2 = st.columns(2)
    
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
        st.write(f"**Última actualització:** {last_update.strftime('%H:%M:%S')}")
        if pump_state.get('last_operation'):
            last_op = pump_state['last_operation']
            st.write(f"**Última operació:** {last_op['end_time'].strftime('%H:%M:%S')}")
            st.write(f"**Durada:** {last_op['duration']:.1f}s")

def render_history_tab(controllers):
    """Renderitza la pestanya d'històric"""
    st.header("Històric d'Operacions")
    st.info("Funcionalitat d'històric en desenvolupament")
    
    # Placeholder per gràfics i taules històriques
    st.subheader("Gràfic de Tendències")
    st.write("Aquí es mostraran els gràfics amb les tendències dels nivells i durades de maniobres")
    
    st.subheader("Taula de Dades")
    st.write("Aquí es mostrarà la taula amb les dades dels darrers 30 dies")

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