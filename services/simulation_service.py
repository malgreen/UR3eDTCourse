import json
import traceback

import numpy as np
import roboticstoolbox as rtb
from communication import protocol
from communication.rabbitmq import Rabbitmq
from spatialmath import SE3
from .utils import get_service_logger


class SimulationService:
    """
    The SimulationService class provides simulation functionality to the digital twin.
    It takes messages that describe which simulation to perform, and the data for it. e.g.:
    ```py
    ctrl: dict = {
        protocol.SimMsgKeys.TYPE: protocol.SimMsgFields.POSITION,
        protocol.SimMsgKeys.ACTUAL_JOINT_POSITIONS: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        protocol.SimMsgKeys.TARGET_JOINT_POSITIONS: [0.0, -np.pi/2, 0.0, -np.pi/2, 0.0, 0.0]
    }
    ```

    After a simulation pass, it publishes the result, i.e.:
    ```py
    state: dict = {
        protocol.SimMsgKeys.POSITION_RESULT: [x, y, z, r, p, y]
    }
    ```
    """

    def __init__(self) -> None:
        # === Logging === #
        self.log = get_service_logger(__name__)
        try:
            self.log.info("Starting SimulationService...")
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
            self.log.info("Connected to RabbitMQ")
            # === Callbacks === #
            self.rmq.subscribe(
                protocol.ROUTING_KEY_SIM_CTRL, self.on_sim_ctrl_message_received
            )
            self.log.info("SimulationService consuming...")
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
            type = body.get(protocol.SimMsgKeys.TYPE)
            actual_joint_positions = body.get(protocol.SimMsgKeys.ACTUAL_JOINT_POSITIONS)
            target_joint_positions = body.get(protocol.SimMsgKeys.TARGET_JOINT_POSITIONS)

            if type == protocol.SimMsgFields.POSITION:
                result = self.simulate_tcp_position(actual_joint_positions, target_joint_positions)
                self.log.info("Sending SIM STATE message with POSITION_RESULT")
                self.rmq.send_message(
                    protocol.ROUTING_KEY_SIM_STATE,
                    {
                        protocol.SimMsgKeys.POSITION_RESULT: result
                    },
                )
            elif type == protocol.SimMsgFields.TRAJECTORY:
                steps = body.get(protocol.SimMsgKeys.TRAJECTORY_STEPS)
                result = self.simulate_trajectory(steps, actual_joint_positions, target_joint_positions)
                self.log.info("Sending SIM STATE message with TRAJECTORY_RESULT")
                self.rmq.send_message(
                    protocol.ROUTING_KEY_SIM_STATE,
                    {
                        protocol.SimMsgKeys.TRAJECTORY_RESULT: result
                    },
                )

        except Exception:
            self.log.error(traceback.format_exc())
    
    def build_model(self) -> rtb.DHRobot:
        links: list[rtb.RevoluteDH] = [
                rtb.RevoluteDH(d=0.15185, a=0, alpha=np.pi / 2),
                rtb.RevoluteDH(d=0, a=-0.24355, alpha=0),
                rtb.RevoluteDH(d=0, a=-0.2132, alpha=0),
                rtb.RevoluteDH(d=0.13105, a=0, alpha=np.pi / 2),
                rtb.RevoluteDH(d=0.08535, a=0, alpha=-np.pi / 2),
                rtb.RevoluteDH(d=0.0921, a=0, alpha=0),
            ]
        return rtb.DHRobot(name="UR3e Model", links=links)


    def simulate_tcp_position(self, q_actual: list, q_target: list) -> list:
        """
        Simulates position of TCP using Forward Kinematics. 
        Returns the TCP pose as a [x,y,z,r,p,y] list
        """
        model = self.build_model()
        model.q = q_actual
        head = model.fkine(q_target)

        return [head.x, head.y, head.z] + head.rpy().tolist()
    

    def simulate_trajectory(self, steps: int, q_actual: list, q_target: list, ) -> list[list]:
        """
        Simulates robotic arm movement trajectory.
        Returns NxM array, where N is the number of timesteps, and M is the amount of joints.
        """
        trajectory = rtb.jtraj(q_actual, q_target, steps)
        return trajectory.q.tolist()


if __name__ == "__main__":
    SimulationService()
