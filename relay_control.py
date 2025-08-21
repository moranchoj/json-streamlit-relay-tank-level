"""
Control del relé mitjançant MQTT.
"""
class RelayControl:
    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client

    def activate(self):
        pass

    def deactivate(self):
        pass

    def status(self):
        pass
