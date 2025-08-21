import streamlit as st
import json
import threading
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

@st.cache_resource
def load_config():
    with open("config.json") as f:
        return json.load(f)

cfg = load_config()

if "levels" not in st.session_state:
    st.session_state["levels"] = {"baix": 0, "alt": 0}
if "history" not in st.session_state:
    st.session_state["history"] = []

def log_event(tipus, info):
    st.session_state["history"].append(
        {"hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tipus": tipus, "info": info}
    )
    st.session_state["history"] = st.session_state["history"][-100:]

# MQTT
def mqtt_bg():
    def on_connect(client, userdata, flags, rc):
        client.subscribe(cfg["mqtt_topic_baix"])
        client.subscribe(cfg["mqtt_topic_alt"])
    def on_message(client, userdata, msg):
        try:
            val = float(msg.payload.decode())
        except Exception:
            val = 0
        if msg.topic.endswith("baix"):
            st.session_state["levels"]["baix"] = val
        elif msg.topic.endswith("alt"):
            st.session_state["levels"]["alt"] = val
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(cfg["mqtt_broker"], cfg["mqtt_port"], cfg["mqtt_keepalive"])
    client.loop_forever()

if mqtt and "mqtt_started" not in st.session_state:
    threading.Thread(target=mqtt_bg, daemon=True).start()
    st.session_state["mqtt_started"] = True

# Enviar ordres de relé via MQTT
def publish_relay(relay, action):
    if not mqtt:
        log_event("ERROR", "MQTT no disponible")
        return
    client = mqtt.Client()
    client.connect(cfg["mqtt_broker"], cfg["mqtt_port"], cfg["mqtt_keepalive"])
    topic = cfg[f"mqtt_topic_{relay}"]
    payload = "ON" if action == "on" else "OFF"
    client.publish(topic, payload)
    client.disconnect()
    log_event("RELAY", f"{relay} -> {payload}")

# Refresc automàtic - sense dependre de cap paquet extern!
def autorefresh(interval_ms=3000):
    st.markdown(
        f"""
        <script>
        function refresh() {{
            window.location.reload();
        }}
        setTimeout(refresh, {interval_ms});
        </script>
        """,
        unsafe_allow_html=True,
    )
autorefresh(3000)  # refresca cada 3 segons

# UI
st.set_page_config(page_title="Control Bomba d'Aigua", layout="centered")
st.title("Control Bomba d'Aigua")

st.metric("Nivell dipòsit baix (%)", st.session_state["levels"]["baix"])
st.metric("Nivell dipòsit alt (%)", st.session_state["levels"]["alt"])

col1, col2 = st.columns(2)

with col1:
    if st.button("Arrenca MANUAL"):
        publish_relay("relay3", "on")
        publish_relay("relay4", "on")
with col2:
    if st.button("PARADA"):
        publish_relay("relay3", "off")
        publish_relay("relay4", "off")

st.write("### Històric últimes maniobres")
for evt in reversed(st.session_state["history"][-10:]):
    st.write(f"{evt['hora']} | {evt['tipus']} | {evt['info']}")

st.write("---")
st.caption("Dashboard per control remot de bomba d'aigua via MQTT + Streamlit. Refresc automàtic sense dependències!")
