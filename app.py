#!/usr/bin/env python3
"""
App principal per al control de bomba d'aigua amb Streamlit.

Sistema de control automàtic d'una bomba d'aigua amb monitorització en temps real,
gestió de maniobres i registre d'històrics.

Funcionalitats:
- Connexió MQTT per llegir nivells de dipòsits des de Venus OS
- Control automàtic programat per hora
- Control manual via dashboard
- Gestió de relés via gpiozero
- Dashboard Streamlit amb 3 pestanyes: Monitorització, Històric, Paràmetres
- Històric temporal en memòria
"""

import json
import datetime
import time
import threading
import queue
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import paho.mqtt.client as mqtt
from gpiozero import OutputDevice

# Configuració de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TankLevels:
    """Estructura per emmagatzemar nivells dels dipòsits"""
    baix: Optional[float] = None
    alt: Optional[float] = None
    timestamp: Optional[datetime.datetime] = None

@dataclass
class ManeuverRecord:
    """Registre d'una maniobra"""
    inici: datetime.datetime
    final: Optional[datetime.datetime] = None
    durada: Optional[float] = None  # en minuts
    nivell_baix_inicial: Optional[float] = None
    nivell_alt_inicial: Optional[float] = None
    nivell_baix_final: Optional[float] = None
    nivell_alt_final: Optional[float] = None
    tipus: str = "automatica"  # automatica, manual, manteniment
    arrencada: bool = False

class WaterPumpController:
    """Controlador principal del sistema de bomba d'aigua"""
    
    def __init__(self, config_path: str = "config.json"):
        """Inicialitza el controlador amb la configuració especificada"""
        self.config = self._load_config(config_path)
        self.tank_levels = TankLevels()
        self.history: List[ManeuverRecord] = []
        self.current_maneuver: Optional[ManeuverRecord] = None
        self.is_running = False
        self.manual_mode = False
        self.last_maneuver_date: Optional[datetime.date] = None
        
        # Cues per comunicació entre threads
        self.mqtt_queue = queue.Queue()
        self.control_queue = queue.Queue()
        
        # Inicialitzar relés
        self._init_relays()
        
        # Inicialitzar connexió MQTT
        self._init_mqtt()
        
        # Thread de control
        self.control_thread = None
        self.mqtt_thread = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Carrega la configuració des del fitxer JSON"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuració carregada des de {config_path}")
            return config
        except Exception as e:
            logger.error(f"Error carregant configuració: {e}")
            raise
            
    def _init_relays(self):
        """Inicialitza els relés GPIO"""
        try:
            self.relay3 = OutputDevice(self.config["relay3_gpio"])
            self.relay4 = OutputDevice(self.config["relay4_gpio"])
            logger.info(f"Relés inicialitzats: GPIO{self.config['relay3_gpio']} i GPIO{self.config['relay4_gpio']}")
        except Exception as e:
            logger.error(f"Error inicialitzant relés: {e}")
            # En cas d'error, crear mock objects per desenvolupament
            class MockRelay:
                def __init__(self):
                    self.is_active = False
                def on(self):
                    self.is_active = True
                def off(self):
                    self.is_active = False
            self.relay3 = MockRelay()
            self.relay4 = MockRelay()
            
    def _init_mqtt(self):
        """Inicialitza la connexió MQTT"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.keepalive = self.config["mqtt_keepalive_s"]
            logger.info("Client MQTT inicialitzat")
        except Exception as e:
            logger.error(f"Error inicialitzant MQTT: {e}")
            
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback quan es connecta al broker MQTT"""
        if rc == 0:
            logger.info("Connectat al broker MQTT")
            # Subscriure's als topics dels nivells dels dipòsits
            device_id = self.config["victron_device_id"]
            client.subscribe(f"N/{device_id}/tank/3/Level")  # dipòsit baix
            client.subscribe(f"N/{device_id}/tank/4/Level")  # dipòsit alt
        else:
            logger.error(f"Error connectant al MQTT broker: {rc}")
            
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback per processar missatges MQTT"""
        try:
            topic = msg.topic
            value = json.loads(msg.payload.decode())["value"]
            
            if "tank/3/Level" in topic:  # dipòsit baix
                self.tank_levels.baix = float(value) * 100  # convertir a percentatge
            elif "tank/4/Level" in topic:  # dipòsit alt
                self.tank_levels.alt = float(value) * 100   # convertir a percentatge
                
            self.tank_levels.timestamp = datetime.datetime.now()
            logger.debug(f"Nivells actualitzats: Baix={self.tank_levels.baix}%, Alt={self.tank_levels.alt}%")
            
        except Exception as e:
            logger.error(f"Error processant missatge MQTT: {e}")
            
    def start_mqtt_connection(self):
        """Inicia la connexió MQTT en un thread separat"""
        try:
            self.mqtt_client.connect(self.config["mqtt_broker"], self.config["mqtt_port"], 60)
            self.mqtt_client.loop_start()
            logger.info("Connexió MQTT iniciada")
        except Exception as e:
            logger.error(f"Error connectant a MQTT: {e}")
            
    def stop_mqtt_connection(self):
        """Atura la connexió MQTT"""
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("Connexió MQTT aturada")
        except Exception as e:
            logger.error(f"Error aturant MQTT: {e}")
            
    def _check_levels_for_operation(self) -> bool:
        """Comprova si els nivells permeten l'operació"""
        if self.tank_levels.baix is None or self.tank_levels.alt is None:
            return False
        return self.tank_levels.baix > 15 and self.tank_levels.alt < 99
        
    def _should_stop_operation(self) -> bool:
        """Comprova si l'operació s'ha d'aturar per nivells"""
        if self.tank_levels.baix is None or self.tank_levels.alt is None:
            return True
        return self.tank_levels.baix <= 15 or self.tank_levels.alt >= 99
        
    def start_maneuver(self, tipus: str = "automatica", durada_max: Optional[int] = None):
        """Inicia una maniobra"""
        if self.current_maneuver is not None:
            logger.warning("Ja hi ha una maniobra en curs")
            return False
            
        # Comprovar nivells abans d'iniciar
        if not self._check_levels_for_operation():
            logger.info("Maniobra sense arrencada: nivells no permeten operació")
            # Registrar maniobra sense arrencada
            record = ManeuverRecord(
                inici=datetime.datetime.now(),
                final=datetime.datetime.now(),
                durada=0,
                nivell_baix_inicial=self.tank_levels.baix,
                nivell_alt_inicial=self.tank_levels.alt,
                nivell_baix_final=self.tank_levels.baix,
                nivell_alt_final=self.tank_levels.alt,
                tipus=tipus,
                arrencada=False
            )
            self.history.append(record)
            return False
            
        # Iniciar maniobra amb arrencada
        self.current_maneuver = ManeuverRecord(
            inici=datetime.datetime.now(),
            nivell_baix_inicial=self.tank_levels.baix,
            nivell_alt_inicial=self.tank_levels.alt,
            tipus=tipus,
            arrencada=True
        )
        
        # Activar relés
        self.relay3.on()
        self.relay4.on()
        self.is_running = True
        
        logger.info(f"Maniobra {tipus} iniciada amb arrencada")
        
        # Configurar durada màxima
        if durada_max is None:
            if tipus == "manual":
                durada_max = self.config["durada_max_manual"]
            elif tipus == "manteniment":
                durada_max = self.config["temps_manteniment"] / 60  # convertir segons a minuts
            else:
                durada_max = self.config["durada_max_maniobra"]
                
        # Programar aturada automàtica
        threading.Timer(durada_max * 60, self._auto_stop_maneuver).start()
        
        return True
        
    def stop_maneuver(self):
        """Atura la maniobra actual"""
        if self.current_maneuver is None:
            return
            
        # Desactivar relés
        self.relay3.off()
        self.relay4.off()
        self.is_running = False
        
        # Completar registre
        self.current_maneuver.final = datetime.datetime.now()
        self.current_maneuver.durada = (
            self.current_maneuver.final - self.current_maneuver.inici
        ).total_seconds() / 60  # en minuts
        self.current_maneuver.nivell_baix_final = self.tank_levels.baix
        self.current_maneuver.nivell_alt_final = self.tank_levels.alt
        
        # Afegir a l'historial
        self.history.append(self.current_maneuver)
        self.last_maneuver_date = self.current_maneuver.inici.date()
        
        logger.info(f"Maniobra aturada. Durada: {self.current_maneuver.durada:.1f} min")
        
        self.current_maneuver = None
        
    def _auto_stop_maneuver(self):
        """Aturada automàtica de maniobra per temps màxim"""
        if self.current_maneuver is not None:
            logger.info("Aturada automàtica per temps màxim")
            self.stop_maneuver()
            
    def check_scheduled_operation(self):
        """Comprova si cal executar l'operació programada"""
        now = datetime.datetime.now()
        hora_config = self.config["hora_maniobra"]
        hora_programada = datetime.datetime.strptime(hora_config, "%H:%M").time()
        
        # Comprovar si és l'hora programada i no s'ha fet avui
        if (now.time().hour == hora_programada.hour and 
            now.time().minute == hora_programada.minute and
            (self.last_maneuver_date is None or self.last_maneuver_date != now.date())):
            
            logger.info("Executant maniobra programada")
            self.start_maneuver("automatica")
            return True
            
        return False
        
    def check_maintenance_operation(self):
        """Comprova si cal executar maniobra de manteniment"""
        if self.last_maneuver_date is None:
            return False
            
        dies_sense_maniobra = (datetime.date.today() - self.last_maneuver_date).days
        
        if dies_sense_maniobra >= self.config["periode_manteniment"]:
            logger.info("Executant maniobra de manteniment")
            self.start_maneuver("manteniment")
            return True
            
        return False
        
    def get_status(self) -> Dict[str, Any]:
        """Retorna l'estat actual del sistema"""
        return {
            "is_running": self.is_running,
            "manual_mode": self.manual_mode,
            "tank_levels": {
                "baix": self.tank_levels.baix,
                "alt": self.tank_levels.alt,
                "timestamp": self.tank_levels.timestamp
            },
            "current_maneuver": self.current_maneuver is not None,
            "relay3_active": hasattr(self.relay3, 'is_active') and self.relay3.is_active,
            "relay4_active": hasattr(self.relay4, 'is_active') and self.relay4.is_active,
            "last_maneuver_date": self.last_maneuver_date,
            "history_count": len(self.history)
        }


def create_gauge(value: float, title: str, max_value: float = 100) -> go.Figure:
    """Crea un gauge per mostrar valors"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value if value is not None else 0,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        gauge={
            'axis': {'range': [None, max_value]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 25], 'color': "lightgray"},
                {'range': [25, 75], 'color': "yellow"},
                {'range': [75, max_value], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig.update_layout(height=300)
    return fig


def create_history_chart(history: List[ManeuverRecord]) -> go.Figure:
    """Crea gràfic de l'històric de maniobres"""
    if not history:
        return go.Figure()
        
    df_data = []
    for record in history[-30:]:  # últims 30 registres
        df_data.append({
            'data': record.inici.date(),
            'durada': record.durada or 0,
            'nivell_baix': record.nivell_baix_inicial or 0,
            'nivell_alt': record.nivell_alt_inicial or 0,
            'tipus': record.tipus
        })
        
    df = pd.DataFrame(df_data)
    
    if df.empty:
        return go.Figure()
        
    fig = go.Figure()
    
    # Durada
    fig.add_trace(go.Scatter(
        x=df['data'], y=df['durada'],
        mode='lines+markers',
        name='Durada (min)',
        line=dict(color='blue')
    ))
    
    # Nivell baix
    fig.add_trace(go.Scatter(
        x=df['data'], y=df['nivell_baix'],
        mode='lines+markers',
        name='Nivell Baix (%)',
        line=dict(color='red'),
        yaxis='y2'
    ))
    
    # Nivell alt
    fig.add_trace(go.Scatter(
        x=df['data'], y=df['nivell_alt'],
        mode='lines+markers',
        name='Nivell Alt (%)',
        line=dict(color='green'),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='Històric de Maniobres (Últims 30 dies)',
        xaxis_title='Data',
        yaxis=dict(title='Durada (min)', side='left'),
        yaxis2=dict(title='Nivell (%)', side='right', overlaying='y'),
        height=400
    )
    
    return fig


def main():
    """Funció principal de l'aplicació Streamlit"""
    st.set_page_config(
        page_title="Control Bomba d'Aigua",
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Inicialitzar controlador en session state
    if 'controller' not in st.session_state:
        try:
            st.session_state.controller = WaterPumpController()
            st.session_state.controller.start_mqtt_connection()
        except Exception as e:
            st.error(f"Error inicialitzant el sistema: {e}")
            return
            
    controller = st.session_state.controller
    
    # Auto-refresh cada 5 segons
    st_autorefresh(interval=5000, key="main_refresh")
    
    # Títol principal
    st.title("🏭 Centre de Control - Bomba d'Aigua")
    
    # Crear pestanyes
    tab_monitor, tab_historic, tab_params = st.tabs(
        ["📊 Monitorització", "📈 Històric", "⚙️ Paràmetres"]
    )
    
    # Obtenir estat actual
    status = controller.get_status()
    
    with tab_monitor:
        st.header("Monitorització en temps real")
        
        # Fila superior amb gauges
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Dipòsit Baix")
            if status["tank_levels"]["baix"] is not None:
                fig_baix = create_gauge(status["tank_levels"]["baix"], "Nivell Baix (%)")
                st.plotly_chart(fig_baix, use_container_width=True)
            else:
                st.warning("Sense dades del dipòsit baix")
                
        with col2:
            st.subheader("Dipòsit Alt")
            if status["tank_levels"]["alt"] is not None:
                fig_alt = create_gauge(status["tank_levels"]["alt"], "Nivell Alt (%)")
                st.plotly_chart(fig_alt, use_container_width=True)
            else:
                st.warning("Sense dades del dipòsit alt")
        
        # Fila amb indicadors d'estat
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Estat Maniobra",
                "🟢 En marxa" if status["is_running"] else "🔴 Parada",
                delta=None
            )
            
        with col2:
            st.metric(
                "Relé 3 (GPIO6)",
                "🟢 Actiu" if status["relay3_active"] else "🔴 Inactiu",
                delta=None
            )
            
        with col3:
            st.metric(
                "Relé 4 (GPIO5)",
                "🟢 Actiu" if status["relay4_active"] else "🔴 Inactiu",
                delta=None
            )
            
        with col4:
            now = datetime.datetime.now()
            st.metric(
                "Data/Hora",
                now.strftime("%d/%m/%Y %H:%M:%S"),
                delta=None
            )
        
        # Informació de la darrera maniobra
        st.subheader("Informació de Maniobres")
        col1, col2 = st.columns(2)
        
        with col1:
            if controller.history:
                last_maneuver = controller.history[-1]
                st.write(f"**Darrera maniobra:** {last_maneuver.inici.strftime('%d/%m/%Y %H:%M')}")
                st.write(f"**Durada:** {last_maneuver.durada:.1f} min")
                st.write(f"**Tipus:** {last_maneuver.tipus}")
            else:
                st.write("Cap maniobra registrada")
                
        with col2:
            # Propera maniobra programada
            hora_programada = controller.config["hora_maniobra"]
            st.write(f"**Propera maniobra:** {hora_programada}")
            
        # Controls manuals
        st.subheader("Control Manual")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Iniciar Maniobra Manual", disabled=status["is_running"]):
                if controller.start_maneuver("manual"):
                    st.success("Maniobra manual iniciada")
                    st.rerun()
                else:
                    st.error("No es pot iniciar: condicions de nivells no adequades")
                    
        with col2:
            if st.button("⏹️ Aturar Maniobra", disabled=not status["is_running"]):
                controller.stop_maneuver()
                st.success("Maniobra aturada")
                st.rerun()
    
    with tab_historic:
        st.header("Històric de Maniobres")
        
        if controller.history:
            # Gràfic de l'històric
            fig_history = create_history_chart(controller.history)
            st.plotly_chart(fig_history, use_container_width=True)
            
            # Taula amb les dades dels darrers 30 dies
            st.subheader("Registres dels darrers 30 dies")
            
            recent_records = controller.history[-30:]
            table_data = []
            
            for record in reversed(recent_records):  # més recent primer
                table_data.append({
                    "Data": record.inici.strftime("%d/%m/%Y"),
                    "Hora": record.inici.strftime("%H:%M"),
                    "Durada (min)": f"{record.durada:.1f}" if record.durada else "0",
                    "Tipus": record.tipus,
                    "Arrencada": "Sí" if record.arrencada else "No",
                    "Nivell Baix Inici (%)": f"{record.nivell_baix_inicial:.1f}" if record.nivell_baix_inicial else "-",
                    "Nivell Alt Inici (%)": f"{record.nivell_alt_inicial:.1f}" if record.nivell_alt_inicial else "-"
                })
                
            if table_data:
                df_table = pd.DataFrame(table_data)
                st.dataframe(df_table, use_container_width=True)
            
        else:
            st.info("No hi ha registres d'històric disponibles")
    
    with tab_params:
        st.header("Paràmetres del Sistema")
        
        # Mostrar configuració actual
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Configuració MQTT")
            st.write(f"**Broker:** {controller.config['mqtt_broker']}")
            st.write(f"**Port:** {controller.config['mqtt_port']}")
            st.write(f"**Device ID:** {controller.config['victron_device_id']}")
            
            st.subheader("Configuració Maniobres")
            st.write(f"**Hora maniobra:** {controller.config['hora_maniobra']}")
            st.write(f"**Durada màx. automàtica:** {controller.config['durada_max_maniobra']} min")
            st.write(f"**Durada màx. manual:** {controller.config['durada_max_manual']} min")
            
        with col2:
            st.subheader("Configuració Relés")
            st.write(f"**Relay 3 GPIO:** {controller.config['relay3_gpio']}")
            st.write(f"**Relay 4 GPIO:** {controller.config['relay4_gpio']}")
            
            st.subheader("Configuració Manteniment")
            st.write(f"**Període manteniment:** {controller.config['periode_manteniment']} dies")
            st.write(f"**Temps manteniment:** {controller.config['temps_manteniment']} s")
            
        # Informació del sistema
        st.subheader("Estat del Sistema")
        st.write(f"**Total maniobres:** {len(controller.history)}")
        if status["tank_levels"]["timestamp"]:
            st.write(f"**Darrera actualització nivells:** {status['tank_levels']['timestamp'].strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Funcions de manteniment
        st.subheader("Funcions de Manteniment")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔧 Maniobra de Manteniment"):
                if controller.start_maneuver("manteniment"):
                    st.success("Maniobra de manteniment iniciada")
                    st.rerun()
                else:
                    st.error("No es pot iniciar maniobra de manteniment")
                    
        with col2:
            if st.button("🗑️ Netejar Històric"):
                controller.history.clear()
                st.success("Històric netejat")
                st.rerun()
    
    # Sidebar amb informació ràpida
    with st.sidebar:
        st.header("Estat Ràpid")
        
        if status["tank_levels"]["baix"] is not None:
            st.metric("Dipòsit Baix", f"{status['tank_levels']['baix']:.1f}%")
        else:
            st.metric("Dipòsit Baix", "Sense dades")
            
        if status["tank_levels"]["alt"] is not None:
            st.metric("Dipòsit Alt", f"{status['tank_levels']['alt']:.1f}%")
        else:
            st.metric("Dipòsit Alt", "Sense dades")
            
        st.metric("Maniobres Totals", len(controller.history))
        
        # Executar comprovacions automàtiques
        controller.check_scheduled_operation()
        controller.check_maintenance_operation()
        
        # Comprovar si cal aturar per nivells durant operació
        if status["is_running"] and controller._should_stop_operation():
            controller.stop_maneuver()
            st.warning("Maniobra aturada automàticament per nivells")


if __name__ == "__main__":
    main()