import time
import numpy as np

from communication.rabbitmq import Rabbitmq
from communication import protocol


def main():
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
    rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message={
            protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
            protocol.CtrlMsgKeys.JOINT_POSITIONS: [[
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,

                # -np.pi / 2,
                # np.pi / 2,
                # -np.pi / 2,
                # -np.pi / 2,
                # 0.0
            ]],
            protocol.CtrlMsgKeys.MAX_VELOCITY: 60,
            protocol.CtrlMsgKeys.ACCELERATION: 80,
        },
    )

    time.sleep(1)

    # --- Step 2: STRONG FAULT ---
    print("Injecting STRONG FAULT...")
    rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message={
            protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.INJECT_FAULT,
            protocol.CtrlMsgKeys.FAULT_TYPE: protocol.FaultTypes.STUCK_JOINT,
            protocol.CtrlMsgKeys.JOINTS: [1, 2, 3],   # multiple joints
            protocol.CtrlMsgKeys.DURATION: 10         # longer duration
        },
    )

    time.sleep(1)

    # --- Step 3: PLAY ---
    rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message={
            protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.PLAY,
        },
    )

    print("BIG FAULT motion triggered!")

    time.sleep(10)


if __name__ == "__main__":
    main()