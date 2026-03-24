import json
from communication import protocol
from communication.rabbitmq import Rabbitmq
from numpy._typing import _UnknownType
from numpy.typing import NDArray
import roboticstoolbox as rtb
import numpy as np
from roboticstoolbox.tools.trajectory import Trajectory
from spatialmath import SE3

class SimulationService:
    """
    The SimulationService class provides simulation functionality to the digital win.
    It takes control messages resembling the messages for the mockup:
    ```py
    ctrl: dict = {
        protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
        protocol.CtrlMsgKeys.JOINT_POSITIONS: [0, np.pi/2, 0, 0, 0, 0]
    }
    ```
    NOTE: it does not require a `START` message. It simulates when receiving `LOAD_PROGRAM`.\\
    After a simulation pass, it publishes the state. The message structure for the state,
    resembles the structure of the mockup state messages:
    ```py
    state: dict = {
        protocol.RobotArmStateKeys.Q_ACTUAL: [0, 0, 0, 0, 0, 0],
        protocol.RobotArmStateKeys.TCP_POSE: [x, y, z, r, p, y]            
    }
    ```
    """
    def __init__(self) -> None:
        # === RabbitMQ === #
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
        # === Model === #
        self.links: list[rtb.RevoluteDH] = [
            rtb.RevoluteDH(d=0.15185, a=0, alpha=np.pi/2),
            rtb.RevoluteDH(d=0, a=-0.24355, alpha=0),
            rtb.RevoluteDH(d=0, a=-0.2132, alpha=0),
            rtb.RevoluteDH(d=0.13105, a=0, alpha=np.pi/2),
            rtb.RevoluteDH(d=0.08535, a=0, alpha=-np.pi/2),
            rtb.RevoluteDH(d=0.0921, a=0, alpha=0),
        ]
        self.model: rtb.DHRobot = rtb.DHRobot(name="UR3e Model", links=self.links)
        self.head: SE3
        # === Callbacks === #
        self.rmq.subscribe(protocol.ROUTING_KEY_SIM_CTRL, self.on_ctrl_message_received)
        self.rmq.start_consuming()
    

    def on_ctrl_message_received(self, channel, method, properties, body) -> None:
        try:
            if body.get(protocol.CtrlMsgKeys.TYPE) == protocol.CtrlMsgFields.LOAD_PROGRAM:
                target_joint_positions = body.get(protocol.CtrlMsgKeys.JOINT_POSITIONS)
                self.head = self.model.fkine(target_joint_positions)
                self.rmq.send_message(protocol.ROUTING_KEY_SIM_STATE, {
                    protocol.RobotArmStateKeys.Q_ACTUAL: self.model.q.tolist(),
                    protocol.RobotArmStateKeys.TCP_POSE: [self.head.x, self.head.y, self.head.z] + self.head.rpy().tolist()
                })
        except Exception as e:
            print(e)
