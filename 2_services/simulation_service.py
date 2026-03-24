# Configure python path to load incubator modules
import sys
import os
import logging
import logging.config
import time
import numpy as np

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
sys.path.append(parent_dir)

from communication import protocol
from communication.rabbitmq import Rabbitmq

class SimulationService:
    def __init__(self):
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
        try:
            msg_type = body.get(protocol.CtrlMsgKeys.TYPE)

            print(f"✓ Message type: {msg_type}")
            print(body)
            joint_positions = body.get(protocol.CtrlMsgKeys.JOINT_POSITIONS)
            print(f"✓ Joint positions: {joint_positions}")
            # load the model with the joint positions

        except Exception as e:
            print(f"✗ Error: {e}")

    def start(self):
        self.rmq.subscribe(
            routing_key=protocol.ROUTING_KEY_CTRL,
            on_message_callback=self.on_message_received,
        )


        print("✓ Listening for messages...")
        self.rmq.start_consuming()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🚀 Starting Simulation Service...")

    service = SimulationService()
    service.start()

"""
This is the recieved signal format being sent by the user:
✓ Listening for messages...
✓ Message type: load_program
{'type': 'load_program', 'joint_positions': [[0.0, -1.5707963267948966, 1.5707963267948966, -1.5707963267948966, -1.5707963267948966, 0.0]], 'max_velocity': 60, 'acceleration': 80}
✓ Message type: play
{'type': 'play'}

For the model it needs to be loaded with only the joint positions.
"""