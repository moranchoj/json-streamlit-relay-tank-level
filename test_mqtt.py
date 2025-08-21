#!/usr/bin/env python3
"""
test_mqtt.py - Script per verificar la connexió MQTT i la recepció de nivells

Aquest script es connecta al broker MQTT i escolta els missatges dels nivells
dels dipòsits per verificar que la comunicació funcioni correctament.
"""

import json
import time
import logging
import paho.mqtt.client as mqtt
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MQTTTester:
    def __init__(self, config_file="config.json"):
        self.config = self.load_config(config_file)
        self.client = None
        self.messages_received = 0
        
    def load_config(self, config_file):
        """Carrega la configuració"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error carregant configuració: {e}")
            return {}
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback de connexió"""
        if rc == 0:
            logger.info("Connectat al broker MQTT correctament")
            
            # Subscriure's als tòpics
            device_id = self.config.get('victron_device_id', '')
            topics = [
                f"N/{device_id}/tank/3/Level",  # Dipòsit baix
                f"N/{device_id}/tank/4/Level"   # Dipòsit alt
            ]
            
            for topic in topics:
                client.subscribe(topic)
                logger.info(f"Subscrit a: {topic}")
                
        else:
            logger.error(f"Error de connexió MQTT: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Callback de missatge rebut"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            
            # Parsejar JSON
            data = json.loads(payload)
            value = data.get('value', 0)
            
            # Determinar tipus de dipòsit
            tank_type = "baix" if "/tank/3/" in topic else "alt" if "/tank/4/" in topic else "desconegut"
            percentage = value * 100
            
            self.messages_received += 1
            
            logger.info(f"Dipòsit {tank_type}: {percentage:.1f}% (missatge #{self.messages_received})")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Dipòsit {tank_type}: {percentage:.1f}%")
            
        except Exception as e:
            logger.error(f"Error processant missatge: {e}")
            print(f"Missatge raw: {msg.topic} -> {msg.payload}")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback de desconnexió"""
        logger.warning("Desconnectat del broker MQTT")
    
    def run_test(self, duration=60):
        """Executa el test durant el temps especificat"""
        try:
            # Configurar client MQTT
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect
            
            # Conectar
            broker = self.config.get('mqtt_broker', 'localhost')
            port = self.config.get('mqtt_port', 1883)
            keepalive = self.config.get('mqtt_keepalive_s', 60)
            
            print(f"Connectant a {broker}:{port}...")
            self.client.connect(broker, port, keepalive)
            
            # Iniciar bucle
            self.client.loop_start()
            
            print(f"Test en execució durant {duration} segons...")
            print("Prem Ctrl+C per aturar abans")
            print("-" * 50)
            
            # Esperar
            time.sleep(duration)
            
        except KeyboardInterrupt:
            print("\nTest aturat per l'usuari")
        except Exception as e:
            logger.error(f"Error durant el test: {e}")
        finally:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
            
            print("-" * 50)
            print(f"Test finalitzat. Missatges rebuts: {self.messages_received}")

def main():
    print("=== Test de Connexió MQTT ===")
    print("Aquest script verifica la comunicació amb el broker MQTT")
    print()
    
    tester = MQTTTester()
    
    # Mostrar configuració
    config = tester.config
    print("Configuració carregada:")
    print(f"  Broker: {config.get('mqtt_broker', 'N/A')}")
    print(f"  Port: {config.get('mqtt_port', 'N/A')}")
    print(f"  Device ID: {config.get('victron_device_id', 'N/A')}")
    print()
    
    # Executar test
    duration = 60  # segons
    tester.run_test(duration)

if __name__ == "__main__":
    main()