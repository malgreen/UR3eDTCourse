import time
import numpy as np

from communication.rabbitmq import Rabbitmq
from communication import protocol


def main():
    # Connect to RabbitMQ
    rmq = Rabbitmq(
        ip="localhost",
        port=5672,
        username="ur3e",
        password="ur3e",
        vhost="/",
        exchange="UR3E_AMQP",
        type="topic",
    )

    rmq.connect_to_server()
    print("Connected to RabbitMQ")

    # --- Step 1: LOAD PROGRAM ---
    print("Sending LOAD_PROGRAM...")
    rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message={
            protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
            protocol.CtrlMsgKeys.JOINT_POSITIONS: [[
                0.0,
                -np.pi / 2,
                np.pi / 2,
                -np.pi / 2,
                -np.pi / 2,
                0.0
            ]],
        },
    )

    time.sleep(1)  # small delay

    # --- Step 2: PLAY ---
    print("Sending PLAY...")
    rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message={
            protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.PLAY,
        },
    )

    print("Motion triggered!")

    # Optional: wait so you can observe logs
    time.sleep(5)


if __name__ == "__main__":
    main()