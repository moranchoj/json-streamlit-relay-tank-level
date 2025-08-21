#!/usr/bin/env python3
"""
demo_mode.py - Mode de demostració per provar l'aplicació sense hardware

Aquest script simula els nivells dels dipòsits i permet provar tota la funcionalitat
del dashboard sense necessitat de tenir el hardware real.
"""

import json
import time
import random
import threading
from datetime import datetime

class TankLevelSimulator:
    """Simulador dels nivells dels dipòsits"""
    
    def __init__(self, config_file="config.json"):
        self.config = self.load_config(config_file)
        self.running = False
        self.tank_low = 45.0  # Nivell inicial dipòsit baix
        self.tank_high = 75.0  # Nivell inicial dipòsit alt
        
    def load_config(self, config_file):
        """Carrega configuració"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def start_simulation(self):
        """Inicia la simulació"""
        self.running = True
        thread = threading.Thread(target=self._simulation_loop, daemon=True)
        thread.start()
        print("Simulació iniciada")
        
    def stop_simulation(self):
        """Atura la simulació"""
        self.running = False
        print("Simulació aturada")
        
    def _simulation_loop(self):
        """Bucle principal de simulació"""
        while self.running:
            # Simular variacions naturals dels nivells
            self.tank_low += random.uniform(-0.5, 0.3)  # Tendència lleugerament baixa
            self.tank_high += random.uniform(-0.2, 0.4)  # Tendència lleugerament alta
            
            # Mantenir límits realistes
            self.tank_low = max(0, min(100, self.tank_low))
            self.tank_high = max(0, min(100, self.tank_high))
            
            # Mostrar nivells simulats
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Simulació - Baix: {self.tank_low:.1f}%, Alt: {self.tank_high:.1f}%")
            
            time.sleep(5)  # Actualitzar cada 5 segons
    
    def get_levels(self):
        """Obté els nivells actuals simulats"""
        return {
            'low': self.tank_low,
            'high': self.tank_high
        }

def create_demo_config():
    """Crea una configuració de demostració"""
    demo_config = {
        "mqtt_broker": "localhost",  # No connecta realment
        "mqtt_port": 1883,
        "mqtt_keepalive_s": 60,
        "victron_device_id": "demo_device",
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
        "email_user": "demo@demo.com",
        "email_pass": "demo",
        "email_to": "user@demo.com",
        "ubicacio": "Demostració"
    }
    
    with open('config_demo.json', 'w', encoding='utf-8') as f:
        json.dump(demo_config, f, indent=2, ensure_ascii=False)
    
    print("Configuració de demostració creada: config_demo.json")

def main():
    print("=== Mode Demostració Dashboard Control Bomba ===")
    print()
    print("Aquest mode simula el funcionament del sistema sense hardware real")
    print()
    
    # Crear configuració demo
    create_demo_config()
    
    # Iniciar simulador
    simulator = TankLevelSimulator("config_demo.json")
    
    try:
        simulator.start_simulation()
        
        print()
        print("Simulació en execució...")
        print("Inicia l'aplicació principal en un altre terminal amb:")
        print("  streamlit run app.py")
        print()
        print("Prem Ctrl+C per aturar la simulació")
        
        # Mantenir viu fins que l'usuari aturi
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nAturant simulació...")
        simulator.stop_simulation()

if __name__ == "__main__":
    main()