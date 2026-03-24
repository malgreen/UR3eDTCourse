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
            print(type(body))
            if body.get(protocol.CtrlMsgKeys.TYPE) == protocol.CtrlMsgFields.LOAD_PROGRAM:
                target_joint_positions = body.get(protocol.CtrlMsgKeys.JOINT_POSITIONS)
                self.head = self.model.fkine(target_joint_positions)
                self.rmq.send_message(protocol.ROUTING_KEY_SIM_STATE, {
                    protocol.RobotArmStateKeys.Q_ACTUAL: self.model.q.tolist(),
                    protocol.RobotArmStateKeys.TCP_POSE: [self.head.x, self.head.y, self.head.z] + self.head.rpy().tolist()
                    
                })
        except Exception as e:
            print(e)


    # def on_state_message_received(self, channel, method, properties, body) -> None:
    #     try:
            
    #     except Exception as e:
    #         print(e)



class UR3eControllerModel:
    pass


class UR3eRoboticArmModel:
    def __init__(self) -> None:
        self.links: list[rtb.RevoluteDH] = [
            rtb.RevoluteDH(d=0.15185, a=0, alpha=np.pi/2),
            rtb.RevoluteDH(d=0, a=-0.24355, alpha=0),
            rtb.RevoluteDH(d=0, a=-0.2132, alpha=0),
            rtb.RevoluteDH(d=0.13105, a=0, alpha=np.pi/2),
            rtb.RevoluteDH(d=0.08535, a=0, alpha=-np.pi/2),
            rtb.RevoluteDH(d=0.0921, a=0, alpha=0),
        ]
        self.model: rtb.DHRobot = rtb.DHRobot(name="UR3e Model", links=self.links)
        self.joints: list[int | float] = [0, 0, 0, 0, 0, 0] # TODO
        self.trajectory: Trajectory
        self.counter: int = 0
    

    def do_fk(self, rotations: list[int | float]) -> SE3:
        assert len(rotations) == len(self.model.links), "Length of joint rotations must match length of model links"
        self.joints = rotations
        return self.model.fkine(rotations)
    

    # def do_ik(self) -> None:
    def start_trajectory(self, start: list[int | float], end: list[int | float], steps: int) -> None:
        self.trajectory = rtb.jtraj(start, end, steps)


    def do_step(self) -> _UnknownType:
        current = self.trajectory.q[self.counter]
        self.counter += 1
        return current
