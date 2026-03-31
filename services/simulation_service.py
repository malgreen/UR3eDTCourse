import json
import logging
import traceback
from os import path

import numpy as np
import roboticstoolbox as rtb
from communication import protocol
from communication.rabbitmq import Rabbitmq
from spatialmath import SE3
from .utils import get_service_logger


class SimulationService:
    """
    The SimulationService class provides simulation functionality to the digital twin.
    It takes control messages resembling the messages for the mockup:
    ```py
    ctrl: dict = {
        protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
        protocol.CtrlMsgKeys.JOINT_POSITIONS: [0, np.pi/2, 0, 0, 0, 0]
    }
    ```
    NOTE: it does not require a `START` message. It simulates when receiving `LOAD_PROGRAM`.

    After a simulation pass, it publishes the state. The message structure for the state
    resembles the structure of the mockup state messages:
    ```py
    state: dict = {
        protocol.RobotArmStateKeys.Q_ACTUAL: [0, 0, 0, 0, 0, 0],
        protocol.RobotArmStateKeys.TCP_POSE: [x, y, z, r, p, y]
    }
    ```
    """

    def __init__(self) -> None:
        # === Logging === #
        self.log = get_service_logger(__name__)
        # === RabbitMQ === #
        try:
            self.log.info("Starting SimulationService...")
            self.rmq: Rabbitmq = Rabbitmq(
                ip="localhost",
                port=5672,
                username="ur3e",
                password="ur3e",
                vhost="/",
                exchange="UR3E_AMQP",
                type="topic",
            )
            self.rmq.connect_to_server()
            self.log.info("Connected to RabbitMQ")
            # === Model === #
            self.links: list[rtb.RevoluteDH] = [
                rtb.RevoluteDH(d=0.15185, a=0, alpha=np.pi / 2),
                rtb.RevoluteDH(d=0, a=-0.24355, alpha=0),
                rtb.RevoluteDH(d=0, a=-0.2132, alpha=0),
                rtb.RevoluteDH(d=0.13105, a=0, alpha=np.pi / 2),
                rtb.RevoluteDH(d=0.08535, a=0, alpha=-np.pi / 2),
                rtb.RevoluteDH(d=0.0921, a=0, alpha=0),
            ]
            self.model: rtb.DHRobot = rtb.DHRobot(name="UR3e Model", links=self.links)
            self.head: SE3
            # === Callbacks === #
            self.rmq.subscribe(
                protocol.ROUTING_KEY_SIM_CTRL, self.on_sim_ctrl_message_received
            )
            self.log.info("Start consuming")
            self.rmq.start_consuming()
        except KeyboardInterrupt:
            self.log.info("Shutting down SimulationService...")
        except Exception:
            self.log.error(traceback.format_exc())
        finally:
            self.log.info("SimulationService has shut down")

    def on_sim_ctrl_message_received(self, channel, method, properties, body) -> None:
        try:
            self.log.info(
                f"Received SIM CTRL message with body: {json.dumps(body, indent=4)}"
            )
            if (
                body.get(protocol.SimCtrlMsgKeys.TYPE)
                == protocol.CtrlMsgFields.LOAD_PROGRAM
            ):
                target_joint_positions = body.get(
                    protocol.SimCtrlMsgKeys.JOINT_POSITIONS
                )
                self.head = self.model.fkine(target_joint_positions)
                self.log.info("Sending SIM STATE message")
                self.rmq.send_message(
                    protocol.ROUTING_KEY_SIM_STATE,
                    {
                        protocol.RobotArmStateKeys.Q_ACTUAL: self.model.q.tolist(),
                        protocol.RobotArmStateKeys.TCP_POSE: [
                            self.head.x,
                            self.head.y,
                            self.head.z,
                        ]
                        + self.head.rpy().tolist(),
                    },
                )
        except Exception:
            self.log.error(traceback.format_exc())


if __name__ == "__main__":
    SimulationService()
