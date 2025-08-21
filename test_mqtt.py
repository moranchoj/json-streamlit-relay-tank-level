#!/usr/bin/env python3
"""
Script de test per verificar la connexió MQTT i la recepció de nivells des de Venus OS.
"""

import json
import time
import datetime
import paho.mqtt.client as mqtt

def load_config():
    """Carrega la configuració des del fitxer config.json"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error carregant configuració: {e}")
        return None

def on_connect(client, userdata, flags, rc):
    """Callback quan es connecta al broker MQTT"""
    if rc == 0:
        print("✅ Connectat al broker MQTT")
        config = userdata
        device_id = config["victron_device_id"]
        
        # Subscriure's als topics dels nivells
        topics = [
            f"N/{device_id}/tank/3/Level",  # dipòsit baix
            f"N/{device_id}/tank/4/Level"   # dipòsit alt
        ]
        
        for topic in topics:
            client.subscribe(topic)
            print(f"📡 Subscrit al topic: {topic}")
            
    else:
        print(f"❌ Error connectant al MQTT broker. Codi: {rc}")

def on_message(client, userdata, msg):
    """Callback per processar missatges MQTT"""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        value = payload.get("value", 0)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if "tank/3/Level" in topic:
            level_percent = float(value) * 100
            print(f"[{timestamp}] 💧 Dipòsit BAIX: {level_percent:.1f}%")
        elif "tank/4/Level" in topic:
            level_percent = float(value) * 100
            print(f"[{timestamp}] 💧 Dipòsit ALT:  {level_percent:.1f}%")
        else:
            print(f"[{timestamp}] 📥 Topic desconegut: {topic} = {value}")
            
    except Exception as e:
        print(f"❌ Error processant missatge: {e}")
        print(f"   Topic: {msg.topic}")
        print(f"   Payload: {msg.payload}")

def on_disconnect(client, userdata, rc):
    """Callback quan es desconnecta"""
    print(f"🔌 Desconnectat del broker MQTT (codi: {rc})")

def test_mqtt_connection():
    """Test principal de connexió MQTT"""
    print("🧪 Test de connexió MQTT i recepció de nivells")
    print("=" * 50)
    
    # Carregar configuració
    config = load_config()
    if not config:
        return False
        
    print(f"📋 Configuració carregada:")
    print(f"   Broker: {config['mqtt_broker']}:{config['mqtt_port']}")
    print(f"   Device ID: {config['victron_device_id']}")
    print(f"   Keepalive: {config['mqtt_keepalive_s']}s")
    print()
    
    # Configurar client MQTT
    client = mqtt.Client()
    client.user_data_set(config)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        print("🔌 Connectant al broker MQTT...")
        client.connect(
            config["mqtt_broker"], 
            config["mqtt_port"], 
            config["mqtt_keepalive_s"]
        )
        
        print("⏳ Escoltant missatges MQTT...")
        print("   (Prem Ctrl+C per aturar)")
        print()
        
        # Iniciar el loop
        client.loop_start()
        
        # Mantenir el script funcionant
        start_time = time.time()
        message_count = 0
        
        while True:
            time.sleep(1)
            
            # Mostrar estadístiques cada 30 segons
            elapsed = time.time() - start_time
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                print(f"📊 Temps transcorregut: {int(elapsed)}s, Missatges rebuts: {message_count}")
                
    except KeyboardInterrupt:
        print("\n🛑 Interromput per l'usuari")
    except Exception as e:
        print(f"❌ Error durant la connexió: {e}")
        return False
    finally:
        print("🔌 Tancant connexió MQTT...")
        client.loop_stop()
        client.disconnect()
        
    return True

if __name__ == "__main__":
    success = test_mqtt_connection()
    if success:
        print("✅ Test completat")
    else:
        print("❌ Test fallit")