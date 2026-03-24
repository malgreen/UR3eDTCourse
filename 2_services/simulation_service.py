# Configure python path to load incubator modules
import sys
import os
import logging
import logging.config
import time
import numpy as np

from communication import protocol
from communication.rabbitmq import Rabbitmq


# Get the current working directory. Should be 1-Incubator-Service
current_dir = os.getcwd()
print("Current directory: " + current_dir)
assert os.path.basename(current_dir) == '2_services', 'Current directory is not 2_services but ' + os.path.basename(current_dir)

# Get the parent directory. Should be the root of the repository
parent_dir = os.path.dirname(current_dir)

# The root of the repo should contain the incubator_dt folder. Otherwise something went wrong in 0-Pre-requisites.
assert os.path.basename(parent_dir) == 'UR3eDTCourse', \
    'Expected parent directory to be UR3eDTCourse but got ' + os.path.basename(parent_dir)

incubator_dt_startup_dir = os.path.join(parent_dir, 'startup')

assert os.path.exists(incubator_dt_startup_dir), 'incubator_dt startup directory not found'

incubator_dt_communication_dir = os.path.join(parent_dir, 'communication')

assert os.path.exists(incubator_dt_communication_dir), 'incubator_dt communication directory not found'


# Add the parent directory to sys.path
sys.path.append(incubator_dt_startup_dir)
sys.path.append(incubator_dt_communication_dir)


class SimulationService:
    def __init__(self, config):
        try:
            self.rmq = Rabbitmq(
                ip="localhost",
                port=5672,
                username="ur3e",
                password="ur3e",
                vhost="/",
                exchange="UR3E_AMQP",
                type="topic",
            )
            self.rmq.connect_to_server()
            print("✓ Connected to RabbitMQ successfully")
        except Exception as e:
            print(f"✗ Failed to connect to RabbitMQ: {e}")

    def on_message_received(self, ch, method, properties, body):
        import json
        try:
            data = json.loads(body)
            print("✓ Received message:")
            print(data)
        except Exception as e:
            print(f"✗ Failed to decode the message: {e}")

    def start(self):
        self.rmq.subscribe(
            routing_key=protocol.ROUTING_KEY_STATE,
            on_message_callback=self.on_message_received,
        )


        print("✓ Listening for messages...")
        self.rmq.start_consuming()