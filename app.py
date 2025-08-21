#!/usr/bin/env python3
"""
Sistema de Control de Bomba d'Aigua
====================================

Sistema automàtic de control d'una bomba d'aigua amb monitorització en temps real,
gestió de maniobres i registre d'històrics.

- Lectura de nivells de dipòsits via MQTT des de Venus OS
- Control automàtic de relés segons nivells i horaris programats
- Dashboard web amb Streamlit per monitorització i control
- Històric de maniobres en CSV

Autor: Sistema automatitzat per control de bomba
"""

import json
import logging
import csv
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

import streamlit as st
import paho.mqtt.client as mqtt
from gpiozero import LED
from streamlit_autorefresh import st_autorefresh

# Configuració de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestió de la configuració del sistema"""
    
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Carrega la configuració des del fitxer JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"Configuració carregada des de {self.config_file}")
        except FileNotFoundError:
            logger.error(f"Fitxer de configuració {self.config_file} no trobat")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar JSON: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obté un valor de configuració"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Estableix un valor de configuració"""
        self.config[key] = value
    
    def save_config(self) -> None:
        """Guarda la configuració al fitxer JSON"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info("Configuració guardada")
        except Exception as e:
            logger.error(f"Error al guardar configuració: {e}")

class TankLevelMonitor:
    """Monitor de nivells de dipòsits via MQTT"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.client = mqtt.Client()
        self.tank_low_level: float = 0.0
        self.tank_high_level: float = 0.0
        self.connected = False
        self.last_update = None
        
        # Configuració del client MQTT
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Topics MQTT per als nivells dels dipòsits
        device_id = config.get('victron_device_id', '2ccf6734efd2')
        self.topic_low = f"N/{device_id}/tank/3/level"
        self.topic_high = f"N/{device_id}/tank/4/level"
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback quan es connecta al broker MQTT"""
        if rc == 0:
            self.connected = True
            logger.info("Connectat al broker MQTT")
            # Subscriure's als topics dels nivells
            client.subscribe(self.topic_low)
            client.subscribe(self.topic_high)
            logger.info(f"Subscrit als topics: {self.topic_low}, {self.topic_high}")
        else:
            logger.error(f"Error de connexió MQTT: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback quan es rep un missatge MQTT"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Parseja el valor JSON si és possible
            if payload.startswith('{"value":'):
                data = json.loads(payload)
                value = data.get('value', 0)
            else:
                value = float(payload)
            
            # Actualitza el nivell corresponent
            if topic == self.topic_low:
                self.tank_low_level = value
                logger.debug(f"Nivell dipòsit baix: {value:.1f}%")
            elif topic == self.topic_high:
                self.tank_high_level = value
                logger.debug(f"Nivell dipòsit alt: {value:.1f}%")
            
            self.last_update = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processant missatge MQTT: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback quan es desconnecta del broker MQTT"""
        self.connected = False
        logger.warning("Desconnectat del broker MQTT")
    
    def connect(self) -> bool:
        """Connecta al broker MQTT"""
        try:
            broker = self.config.get('mqtt_broker', 'localhost')
            port = self.config.get('mqtt_port', 1883)
            keepalive = self.config.get('mqtt_keepalive_s', 60)
            
            logger.info(f"Connectant a {broker}:{port}")
            self.client.connect(broker, port, keepalive)
            self.client.loop_start()
            
            # Espera un moment per establir la connexió
            time.sleep(1)
            return self.connected
            
        except Exception as e:
            logger.error(f"Error connectant al broker MQTT: {e}")
            return False
    
    def disconnect(self):
        """Desconnecta del broker MQTT"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
    
    def get_levels(self) -> Tuple[float, float]:
        """Retorna els nivells actuals (baix, alt)"""
        return self.tank_low_level, self.tank_high_level
    
    def is_data_fresh(self, max_age_seconds: int = 300) -> bool:
        """Comprova si les dades són recents"""
        if self.last_update is None:
            return False
        return (datetime.now() - self.last_update).total_seconds() < max_age_seconds

class RelayController:
    """Controlador dels relés via GPIO"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.relay3_gpio = config.get('relay3_gpio', 6)
        self.relay4_gpio = config.get('relay4_gpio', 5)
        
        # Inicialitza els relés com a LEDs (compatibilitat amb gpiozero)
        try:
            self.relay3 = LED(self.relay3_gpio)
            self.relay4 = LED(self.relay4_gpio)
            logger.info(f"Relés inicialitzats: GPIO{self.relay3_gpio}, GPIO{self.relay4_gpio}")
        except Exception as e:
            logger.error(f"Error inicialitzant relés: {e}")
            # Crear objectes mock per desenvolupament
            self.relay3 = MockRelay("Relay3")
            self.relay4 = MockRelay("Relay4")
    
    def activate_relays(self, tank_low: float, tank_high: float) -> Tuple[bool, bool]:
        """
        Activa els relés segons les condicions dels nivells
        Relay 3: actiu si dipòsit baix > 15%
        Relay 4: actiu si dipòsit alt < 99%
        """
        relay3_active = tank_low > 15.0
        relay4_active = tank_high < 99.0
        
        if relay3_active:
            self.relay3.on()
        else:
            self.relay3.off()
        
        if relay4_active:
            self.relay4.on()
        else:
            self.relay4.off()
        
        logger.debug(f"Relés - R3: {'ON' if relay3_active else 'OFF'}, "
                    f"R4: {'ON' if relay4_active else 'OFF'}")
        
        return relay3_active, relay4_active
    
    def deactivate_all(self):
        """Desactiva tots els relés"""
        self.relay3.off()
        self.relay4.off()
        logger.info("Tots els relés desactivats")
    
    def get_status(self) -> Tuple[bool, bool]:
        """Retorna l'estat actual dels relés"""
        return self.relay3.is_lit, self.relay4.is_lit

class MockRelay:
    """Relay mock per desenvolupament sense hardware"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_lit = False
    
    def on(self):
        self.is_lit = True
        logger.debug(f"{self.name} activat (mock)")
    
    def off(self):
        self.is_lit = False
        logger.debug(f"{self.name} desactivat (mock)")

class PumpController:
    """Controlador principal de la bomba amb lògica automàtica i manual"""
    
    def __init__(self, config: ConfigManager, tank_monitor: TankLevelMonitor, relay_controller: RelayController):
        self.config = config
        self.tank_monitor = tank_monitor
        self.relay_controller = relay_controller
        
        # Estats del controlador
        self.pump_running = False
        self.manual_mode = False
        self.maintenance_mode = False
        
        # Timestamps
        self.pump_start_time = None
        self.last_operation_date = None
        self.last_maintenance_date = None
        
        # Historic
        self.historic_file = 'historic.csv'
        self.initialize_historic_file()
        
        # Cargar última data d'operació des de l'històric
        self.load_last_operation_date()
    
    def initialize_historic_file(self):
        """Inicialitza el fitxer CSV d'històric si no existeix"""
        if not os.path.exists(self.historic_file):
            with open(self.historic_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([
                    'Data_Inici', 'Hora_Inici', 'Data_Final', 'Hora_Final', 
                    'Durada_min', 'Nivell_Baix_Inicial', 'Nivell_Alt_Inicial',
                    'Nivell_Baix_Final', 'Nivell_Alt_Final', 'Tipus_Maniobra'
                ])
    
    def load_last_operation_date(self):
        """Carrega la data de l'última operació des de l'històric"""
        try:
            if os.path.exists(self.historic_file):
                df = pd.read_csv(self.historic_file, sep=';')
                if not df.empty:
                    # Filtra operacions amb arrencada (no manteniment)
                    ops_with_start = df[df['Tipus_Maniobra'] != 'manteniment']
                    if not ops_with_start.empty:
                        last_date_str = ops_with_start.iloc[-1]['Data_Inici']
                        self.last_operation_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                    
                    # Carrega data de manteniment
                    maintenance_ops = df[df['Tipus_Maniobra'] == 'manteniment']
                    if not maintenance_ops.empty:
                        last_maint_str = maintenance_ops.iloc[-1]['Data_Inici']
                        self.last_maintenance_date = datetime.strptime(last_maint_str, '%Y-%m-%d').date()
        except Exception as e:
            logger.error(f"Error carregant històric: {e}")
    
    def should_run_scheduled_operation(self) -> bool:
        """Comprova si s'ha de fer la maniobra programada"""
        now = datetime.now()
        scheduled_time = self.config.get('hora_maniobra', '12:00')
        scheduled_hour, scheduled_minute = map(int, scheduled_time.split(':'))
        
        # Comprova si és l'hora programada (amb marge de 5 minuts)
        current_time = now.time()
        scheduled_time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
        
        # Marge de 5 minuts
        margin = timedelta(minutes=5)
        scheduled_datetime = datetime.combine(now.date(), scheduled_time_obj)
        start_window = scheduled_datetime - margin
        end_window = scheduled_datetime + margin
        
        in_time_window = start_window.time() <= current_time <= end_window.time()
        
        # Comprova si ja s'ha fet avui
        today = now.date()
        already_done_today = (self.last_operation_date == today)
        
        return in_time_window and not already_done_today and not self.pump_running
    
    def should_run_maintenance(self) -> bool:
        """Comprova si s'ha de fer manteniment"""
        if self.pump_running or self.last_operation_date is None:
            return False
        
        days_since_last_op = (datetime.now().date() - self.last_operation_date).days
        maintenance_period = self.config.get('periode_manteniment', 10)
        
        return days_since_last_op >= maintenance_period
    
    def can_start_pump(self) -> Tuple[bool, str]:
        """Comprova si es pot arrencar la bomba"""
        tank_low, tank_high = self.tank_monitor.get_levels()
        
        # Comprova condicions de nivells
        if tank_low <= 15.0:
            return False, "Nivell dipòsit baix massa baix (≤15%)"
        
        if tank_high >= 99.0:
            return False, "Nivell dipòsit alt massa alt (≥99%)"
        
        # Comprova si les dades són recents
        if not self.tank_monitor.is_data_fresh():
            return False, "Dades de nivells no actualitzades"
        
        return True, "Condicions adequades"
    
    def start_pump(self, mode: str = "programada") -> Tuple[bool, str]:
        """Inicia la bomba"""
        can_start, reason = self.can_start_pump()
        
        if not can_start:
            return False, reason
        
        if self.pump_running:
            return False, "La bomba ja està en funcionament"
        
        # Obtenir nivells inicials
        tank_low, tank_high = self.tank_monitor.get_levels()
        
        # Activar relés
        self.relay_controller.activate_relays(tank_low, tank_high)
        
        # Actualitzar estat
        self.pump_running = True
        self.pump_start_time = datetime.now()
        self.manual_mode = (mode == "manual")
        self.maintenance_mode = (mode == "manteniment")
        
        logger.info(f"Bomba iniciada en mode {mode}")
        return True, f"Bomba iniciada correctament ({mode})"
    
    def stop_pump(self, reason: str = "manual") -> Tuple[bool, str]:
        """Atura la bomba"""
        if not self.pump_running:
            return False, "La bomba no està en funcionament"
        
        # Obtenir nivells finals
        tank_low, tank_high = self.tank_monitor.get_levels()
        
        # Desactivar relés
        self.relay_controller.deactivate_all()
        
        # Calcular durada
        duration = (datetime.now() - self.pump_start_time).total_seconds() / 60.0
        
        # Guardar a l'històric
        self.save_operation_to_historic(duration, tank_low, tank_high)
        
        # Actualitzar estat
        self.pump_running = False
        self.manual_mode = False
        if not self.maintenance_mode:
            self.last_operation_date = datetime.now().date()
        else:
            self.last_maintenance_date = datetime.now().date()
        self.maintenance_mode = False
        self.pump_start_time = None
        
        logger.info(f"Bomba aturada: {reason}")
        return True, f"Bomba aturada: {reason}"
    
    def save_operation_to_historic(self, duration: float, final_low: float, final_high: float):
        """Guarda l'operació a l'històric"""
        try:
            start_time = self.pump_start_time
            end_time = datetime.now()
            
            # Obtenir nivells inicials (es podrien guardar al iniciar)
            tank_low, tank_high = self.tank_monitor.get_levels()
            
            # Determinar tipus de maniobra
            if self.maintenance_mode:
                tipus = "manteniment"
            elif self.manual_mode:
                tipus = "manual"
            else:
                tipus = "programada"
            
            with open(self.historic_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([
                    start_time.strftime('%Y-%m-%d'),
                    start_time.strftime('%H:%M:%S'),
                    end_time.strftime('%Y-%m-%d'),
                    end_time.strftime('%H:%M:%S'),
                    f"{duration:.2f}",
                    f"{tank_low:.1f}",
                    f"{tank_high:.1f}",
                    f"{final_low:.1f}",
                    f"{final_high:.1f}",
                    tipus
                ])
            
            logger.info(f"Operació guardada a l'històric: {tipus}, {duration:.2f} min")
            
        except Exception as e:
            logger.error(f"Error guardant històric: {e}")
    
    def check_automatic_stop_conditions(self) -> Tuple[bool, str]:
        """Comprova si s'ha d'aturar automàticament"""
        if not self.pump_running:
            return False, ""
        
        # Calcular temps de funcionament
        runtime = (datetime.now() - self.pump_start_time).total_seconds() / 60.0
        
        # Comprovar durada màxima
        if self.maintenance_mode:
            max_duration = self.config.get('temps_manteniment', 10) / 60.0  # Convertir segons a minuts
        elif self.manual_mode:
            max_duration = self.config.get('durada_max_manual', 10)
        else:
            max_duration = self.config.get('durada_max_maniobra', 3)
        
        if runtime >= max_duration:
            return True, f"Durada màxima assolida ({max_duration:.1f} min)"
        
        # Comprovar nivells
        tank_low, tank_high = self.tank_monitor.get_levels()
        
        if tank_low <= 15.0:
            return True, "Nivell dipòsit baix massa baix"
        
        if tank_high >= 99.0:
            return True, "Nivell dipòsit alt massa alt"
        
        return False, ""
    
    def get_runtime_minutes(self) -> float:
        """Retorna el temps de funcionament en minuts"""
        if not self.pump_running or self.pump_start_time is None:
            return 0.0
        return (datetime.now() - self.pump_start_time).total_seconds() / 60.0
    
    def get_next_scheduled_time(self) -> str:
        """Retorna la propera hora programada"""
        scheduled_time = self.config.get('hora_maniobra', '12:00')
        today = datetime.now().date()
        
        # Si ja s'ha fet avui, la propera és demà
        if self.last_operation_date == today:
            next_date = today + timedelta(days=1)
            return f"{next_date.strftime('%d/%m/%Y')} {scheduled_time}"
        else:
            return f"{today.strftime('%d/%m/%Y')} {scheduled_time}"

class HistoricManager:
    """Gestor de l'històric de maniobres"""
    
    def __init__(self, historic_file: str = 'historic.csv'):
        self.historic_file = historic_file
    
    def get_historic_data(self, days: int = 365) -> pd.DataFrame:
        """Obté dades històriques dels últims N dies"""
        try:
            if not os.path.exists(self.historic_file):
                return pd.DataFrame()
            
            df = pd.read_csv(self.historic_file, sep=';')
            if df.empty:
                return df
            
            # Convertir dates
            df['Data_Inici'] = pd.to_datetime(df['Data_Inici'])
            
            # Filtrar pels últims N dies
            cutoff_date = datetime.now() - timedelta(days=days)
            df = df[df['Data_Inici'] >= cutoff_date]
            
            return df
            
        except Exception as e:
            logger.error(f"Error carregant històric: {e}")
            return pd.DataFrame()
    
    def get_last_30_days(self) -> pd.DataFrame:
        """Obté dades dels últims 30 dies"""
        return self.get_historic_data(30)
    
    def cleanup_old_data(self, retention_years: int = 5):
        """Neteja dades antigues segons el període de retenció"""
        try:
            df = pd.read_csv(self.historic_file, sep=';')
            if df.empty:
                return
            
            df['Data_Inici'] = pd.to_datetime(df['Data_Inici'])
            cutoff_date = datetime.now() - timedelta(days=retention_years * 365)
            
            # Filtrar dades recents
            df_recent = df[df['Data_Inici'] >= cutoff_date]
            
            # Guardar de nou
            df_recent.to_csv(self.historic_file, sep=';', index=False)
            
            logger.info(f"Històric netejat: {len(df) - len(df_recent)} registres eliminats")
            
        except Exception as e:
            logger.error(f"Error netejant històric: {e}")

# Inicialització de l'aplicació
if 'config' not in st.session_state:
    st.session_state.config = ConfigManager()

if 'tank_monitor' not in st.session_state:
    st.session_state.tank_monitor = TankLevelMonitor(st.session_state.config)
    st.session_state.tank_monitor.connect()

if 'relay_controller' not in st.session_state:
    st.session_state.relay_controller = RelayController(st.session_state.config)

if 'pump_controller' not in st.session_state:
    st.session_state.pump_controller = PumpController(
        st.session_state.config,
        st.session_state.tank_monitor,
        st.session_state.relay_controller
    )

if 'historic_manager' not in st.session_state:
    st.session_state.historic_manager = HistoricManager()

def main():
    """Funció principal de l'aplicació Streamlit"""
    st.set_page_config(
        page_title="Control Bomba d'Aigua", 
        page_icon="💧", 
        layout="wide"
    )
    
    st.title("🏭 Sistema de Control de Bomba d'Aigua")
    
    # Auto-refresh cada 5 segons
    st_autorefresh(interval=5000, key="autorefresh")
    
    # Lògica automàtica en background
    automatic_control_logic()
    
    # Pestanyes del dashboard
    tab1, tab2, tab3 = st.tabs(["🔍 Monitorització", "📊 Històric", "⚙️ Paràmetres"])
    
    with tab1:
        monitoring_tab()
    
    with tab2:
        history_tab()
    
    with tab3:
        parameters_tab()

def automatic_control_logic():
    """Lògica de control automàtic que s'executa a cada refresh"""
    pump_controller = st.session_state.pump_controller
    
    # Comprovar condicions d'aturada automàtica
    if pump_controller.pump_running:
        should_stop, reason = pump_controller.check_automatic_stop_conditions()
        if should_stop:
            pump_controller.stop_pump(reason)
            st.info(f"🛑 Bomba aturada automàticament: {reason}")
    
    # Comprovar maniobra programada
    elif pump_controller.should_run_scheduled_operation():
        success, message = pump_controller.start_pump("programada")
        if success:
            st.success(f"🚀 {message}")
        else:
            st.warning(f"⚠️ No s'ha pogut iniciar la maniobra programada: {message}")
    
    # Comprovar manteniment
    elif pump_controller.should_run_maintenance():
        success, message = pump_controller.start_pump("manteniment")
        if success:
            st.info(f"🔧 Manteniment iniciat: {message}")
        else:
            st.warning(f"⚠️ No s'ha pogut iniciar el manteniment: {message}")

def monitoring_tab():
    """Pestanya de monitorització"""
    st.header("Monitorització en Temps Real")
    
    # Obtenir dades actuals
    config = st.session_state.config
    tank_monitor = st.session_state.tank_monitor
    relay_controller = st.session_state.relay_controller
    pump_controller = st.session_state.pump_controller
    
    tank_low, tank_high = tank_monitor.get_levels()
    relay3_status, relay4_status = relay_controller.get_status()
    
    # Crear columnes per a la interfície
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 Nivells de Dipòsits")
        
        # Gauge del dipòsit baix amb colors
        low_color = "normal" if tank_low > 15 else "off"
        st.metric(
            "Dipòsit Baix", 
            f"{tank_low:.1f}%",
            delta=None,
            help="Nivell actual del dipòsit baix"
        )
        if tank_low <= 15:
            st.error("⚠️ Nivell baix crític!")
        
        # Gauge del dipòsit alt amb colors
        high_color = "normal" if tank_high < 99 else "off"
        st.metric(
            "Dipòsit Alt", 
            f"{tank_high:.1f}%",
            delta=None,
            help="Nivell actual del dipòsit alt"
        )
        if tank_high >= 99:
            st.error("⚠️ Nivell alt crític!")
        
        # Indicador de connexió MQTT
        if tank_monitor.connected and tank_monitor.is_data_fresh():
            st.success("🟢 Connexió MQTT activa")
            if tank_monitor.last_update:
                st.caption(f"Última actualització: {tank_monitor.last_update.strftime('%H:%M:%S')}")
        else:
            st.error("🔴 Connexió MQTT inactiva")
    
    with col2:
        st.subheader("⚡ Estats del Sistema")
        
        # Estat dels relés
        relay3_color = "🟢" if relay3_status else "🔴"
        relay4_color = "🟢" if relay4_status else "🔴"
        
        st.write(f"{relay3_color} **Relé 3 (GPIO{config.get('relay3_gpio', 6)}):** {'Actiu' if relay3_status else 'Inactiu'}")
        st.write(f"{relay4_color} **Relé 4 (GPIO{config.get('relay4_gpio', 5)}):** {'Actiu' if relay4_status else 'Inactiu'}")
        
        # Estat de la maniobra amb informació detallada
        if pump_controller.pump_running:
            runtime = pump_controller.get_runtime_minutes()
            if pump_controller.maintenance_mode:
                st.success(f"🔧 **Manteniment en curs:** {runtime:.1f} min")
            elif pump_controller.manual_mode:
                st.info(f"🎮 **Maniobra manual:** {runtime:.1f} min")
            else:
                st.success(f"🚀 **Maniobra programada:** {runtime:.1f} min")
        else:
            st.write("🔴 **Maniobra:** Parada")
        
        # Hora i data actuals
        now = datetime.now()
        st.write(f"🕐 **Hora actual:** {now.strftime('%H:%M:%S')}")
        st.write(f"📅 **Data:** {now.strftime('%d/%m/%Y')}")
        
        # Informació de l'última maniobra
        if pump_controller.last_operation_date:
            st.write(f"📋 **Última maniobra:** {pump_controller.last_operation_date.strftime('%d/%m/%Y')}")
        
        # Propera maniobra programada
        next_scheduled = pump_controller.get_next_scheduled_time()
        st.write(f"⏰ **Propera maniobra:** {next_scheduled}")
    
    with col3:
        st.subheader("🎮 Control Manual")
        
        # Estat actual i controls
        if not pump_controller.pump_running:
            # Comprovar si es pot iniciar
            can_start, reason = pump_controller.can_start_pump()
            
            if can_start:
                if st.button("▶️ Iniciar Maniobra Manual", key="manual_start", type="primary"):
                    success, message = pump_controller.start_pump("manual")
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            else:
                st.button("▶️ Iniciar Maniobra Manual", key="manual_start_disabled", disabled=True)
                st.warning(f"⚠️ {reason}")
        else:
            # Bomba en funcionament - mostrar botó d'aturada
            if st.button("⏹️ Aturar Maniobra", key="manual_stop", type="secondary"):
                success, message = pump_controller.stop_pump("aturada manual")
                if success:
                    st.success(f"✅ {message}")
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        # Configuració de durada màxima
        durada_max = config.get('durada_max_manual', 10)
        st.write(f"⏱️ **Durada màxima manual:** {durada_max} min")
        
        # Informació adicional
        if pump_controller.pump_running:
            runtime = pump_controller.get_runtime_minutes()
            if pump_controller.manual_mode:
                remaining = durada_max - runtime
                st.write(f"⏰ **Temps restant:** {remaining:.1f} min")
            
            # Barra de progrés
            if pump_controller.manual_mode:
                progress = min(runtime / durada_max, 1.0)
            elif pump_controller.maintenance_mode:
                max_maint = config.get('temps_manteniment', 10) / 60.0
                progress = min(runtime / max_maint, 1.0)
            else:
                max_auto = config.get('durada_max_maniobra', 3)
                progress = min(runtime / max_auto, 1.0)
            
            st.progress(progress)
        
        # Botó de test de connexió MQTT
        if st.button("🔗 Test Connexió MQTT", key="test_mqtt"):
            if tank_monitor.connected:
                st.success("✅ Connexió MQTT activa")
            else:
                st.error("❌ Connexió MQTT fallida")
                if st.button("🔄 Reconnectar", key="reconnect_mqtt"):
                    tank_monitor.connect()

def history_tab():
    """Pestanya d'històric"""
    st.header("📈 Històric de Maniobres")
    
    historic_manager = st.session_state.historic_manager
    
    # Selector de període
    period_options = {
        "1 mes": 30,
        "3 mesos": 90,
        "6 mesos": 180,
        "1 any": 365,
        "3 anys": 365 * 3,
        "5 anys": 365 * 5,
        "10 anys": 365 * 10
    }
    
    period = st.selectbox(
        "Període d'anàlisi:",
        list(period_options.keys()),
        index=3
    )
    
    days = period_options[period]
    df = historic_manager.get_historic_data(days)
    
    if df.empty:
        st.info("📭 No hi ha dades històriques disponibles per al període seleccionat")
        return
    
    # Crear gràfics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Durada Diària de Maniobres")
        
        # Agrupar per dia i sumar durades
        df['Data'] = pd.to_datetime(df['Data_Inici']).dt.date
        daily_data = df.groupby('Data')['Durada_min'].sum().reset_index()
        
        if not daily_data.empty:
            st.line_chart(
                daily_data.set_index('Data')['Durada_min'],
                use_container_width=True
            )
        else:
            st.info("No hi ha dades per mostrar")
    
    with col2:
        st.subheader("🔄 Tipus de Maniobres")
        
        # Comptar tipus de maniobres
        tipus_counts = df['Tipus_Maniobra'].value_counts()
        
        if not tipus_counts.empty:
            st.bar_chart(tipus_counts, use_container_width=True)
        else:
            st.info("No hi ha dades per mostrar")
    
    # Gràfic de nivells inicials
    st.subheader("📈 Evolució de Nivells Inicials")
    
    if len(df) > 1:
        df_sorted = df.sort_values('Data_Inici')
        chart_data = pd.DataFrame({
            'Dipòsit Baix': df_sorted['Nivell_Baix_Inicial'],
            'Dipòsit Alt': df_sorted['Nivell_Alt_Inicial']
        }, index=pd.to_datetime(df_sorted['Data_Inici']))
        
        st.line_chart(chart_data, use_container_width=True)
    
    # Estadístiques resumides
    st.subheader("📊 Estadístiques del Període")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_operations = len(df)
        st.metric("Total Maniobres", total_operations)
    
    with col2:
        avg_duration = df['Durada_min'].mean() if not df.empty else 0
        st.metric("Durada Mitjana", f"{avg_duration:.1f} min")
    
    with col3:
        total_runtime = df['Durada_min'].sum() if not df.empty else 0
        st.metric("Temps Total", f"{total_runtime:.1f} min")
    
    with col4:
        programmed_ops = len(df[df['Tipus_Maniobra'] == 'programada'])
        st.metric("Maniobres Programades", programmed_ops)
    
    # Taula de dades dels darrers 30 dies
    st.subheader("📋 Darrers 30 Dies")
    
    recent_df = historic_manager.get_last_30_days()
    
    if not recent_df.empty:
        # Preparar dades per mostrar
        display_df = recent_df[['Data_Inici', 'Hora_Inici', 'Durada_min', 
                               'Nivell_Baix_Inicial', 'Nivell_Alt_Inicial', 'Tipus_Maniobra']].copy()
        
        display_df.columns = ['Data', 'Hora', 'Durada (min)', 
                             'Nivell Baix (%)', 'Nivell Alt (%)', 'Tipus']
        
        # Ordenar per data descendent
        display_df = display_df.sort_values('Data', ascending=False)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Botó per descarregar dades
        csv = recent_df.to_csv(sep=';', index=False)
        st.download_button(
            label="💾 Descarregar CSV",
            data=csv,
            file_name=f"historic_bomba_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("📭 No hi ha dades dels darrers 30 dies")
    
    # Botó per netejar històric antic
    st.subheader("🧹 Manteniment de l'Històric")
    
    retention_years = st.session_state.config.get('retencio_historic_anys', 5)
    st.write(f"Retenció configurada: {retention_years} anys")
    
    if st.button("🗑️ Netejar Dades Antigues"):
        historic_manager.cleanup_old_data(retention_years)
        st.success("✅ Històric netejat correctament")
        st.rerun()

def parameters_tab():
    """Pestanya de paràmetres"""
    st.header("⚙️ Configuració del Sistema")
    
    config = st.session_state.config
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🌐 Configuració MQTT")
        mqtt_broker = st.text_input("Adreça IP Broker MQTT", value=config.get('mqtt_broker', ''))
        mqtt_port = st.number_input("Port MQTT", value=config.get('mqtt_port', 1883), min_value=1, max_value=65535)
        
        st.subheader("⏰ Configuració de Temps")
        hora_maniobra = st.time_input("Hora de Maniobra", value=datetime.strptime(config.get('hora_maniobra', '12:00'), '%H:%M').time())
        durada_max_maniobra = st.slider("Durada Màxima Maniobra (min)", min_value=2, max_value=5, value=config.get('durada_max_maniobra', 3))
        durada_max_manual = st.slider("Durada Màxima Manual (min)", min_value=5, max_value=30, value=config.get('durada_max_manual', 10))
    
    with col2:
        st.subheader("🔧 Configuració de Manteniment")
        periode_manteniment = st.slider("Període Manteniment (dies)", min_value=7, max_value=15, value=config.get('periode_manteniment', 10))
        temps_manteniment = st.slider("Temps Manteniment (s)", min_value=5, max_value=15, value=config.get('temps_manteniment', 10))
        
        st.subheader("💾 Configuració d'Històric")
        retencio_historic = st.slider("Retenció Històric (anys)", min_value=2, max_value=10, value=config.get('retencio_historic_anys', 5))
        
        st.subheader("📍 Ubicació")
        ubicacio = st.text_input("Ubicació del Sistema", value=config.get('ubicacio', ''))
    
    # Botó per guardar configuració
    if st.button("💾 Guardar Configuració"):
        config.set('mqtt_broker', mqtt_broker)
        config.set('mqtt_port', mqtt_port)
        config.set('hora_maniobra', hora_maniobra.strftime('%H:%M'))
        config.set('durada_max_maniobra', durada_max_maniobra)
        config.set('durada_max_manual', durada_max_manual)
        config.set('periode_manteniment', periode_manteniment)
        config.set('temps_manteniment', temps_manteniment)
        config.set('retencio_historic_anys', retencio_historic)
        config.set('ubicacio', ubicacio)
        
        config.save_config()
        st.success("✅ Configuració guardada correctament!")

if __name__ == "__main__":
    main()