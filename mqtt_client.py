"""
Client MQTT per connectar-se al broker i gestionar missatges.
"""
class MQTTClient:
    def __init__(self, broker, port):
        self.broker = broker
        self.port = port

    def connect(self):
        pass

    def subscribe(self, topic):
        pass

    def publish(self, topic, message):
        pass
