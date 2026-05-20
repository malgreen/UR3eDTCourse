import traceback
from enum import StrEnum, auto

from communication import protocol
from communication.rabbitmq import Rabbitmq

from .utils import get_service_logger


class SimpleErrorServiceState(StrEnum):
    WAIT_FOR_LOAD = auto()
    WAIT_FOR_PLAY = auto()
    WAIT_FOR_SIM = auto()
    WAIT_FOR_PT = auto()


class SimpleErrorService:
    """
    The SimpleErrorService listens along for Control messages to the Physical Twin.

    Whenever a `LOAD_PROGRAM` is intercepted, it saves the requested joint positions.

    Whenever a `PLAY` is intercepted, it starts a simulation and wait for both the robot
    and the simulation to finish, and it checks for differences in the position of the TCP.

    If the difference is above some threshold, a message is sent with the error status.
    The message format is as follows:
    ```py
    msg = {
        'status': True,
        'actual_position': [x, y, z],
        'simulated_position': [x, y, z]
    }
    ```
    """

    def __init__(self) -> None:
        # === Logging === #
        self.log = get_service_logger(__name__)
        try:
            self.log.info("Starting SimpleErrorService...")
            # === fields === #
            self.state: SimpleErrorServiceState = SimpleErrorServiceState.WAIT_FOR_LOAD
            self.actual_joint_positions = []
            self.loaded_joint_positions = []
            self.latest_sim_tcp_pose = []  # format: [x, y, z, r, p, y]
            self.latest_pt_tcp_pose = []  # format: [x, y, z, r, p, y]
            self.max_diff = 0.05  # TODO
            # === RabbitMQ === # TODO: use config
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
                protocol.ROUTING_KEY_CTRL, self.on_pt_ctrl_message_received
            )
            self.rmq.subscribe(
                protocol.ROUTING_KEY_STATE, self.on_pt_state_message_received
            )
            self.rmq.subscribe(
                protocol.ROUTING_KEY_SIM_STATE, self.on_sim_state_message_received
            )

            self.log.info("SimpleErrorService consuming...")
            self.rmq.start_consuming()
        except KeyboardInterrupt:
            self.log.info("Shutting down SimpleErrorService...")
        except Exception:
            self.log.error(traceback.format_exc())
        finally:
            self.log.info("SimpleErrorService has shut down")

    def on_pt_ctrl_message_received(self, channel, method, properties, body) -> None:
        try:
            self.log.info(f"Intercepted PT CTRL message (in state: {self.state})")
            ctrl_msg_type = body.get(protocol.CtrlMsgKeys.TYPE)

            if (
                ctrl_msg_type == protocol.CtrlMsgFields.LOAD_PROGRAM
                and (self.state == SimpleErrorServiceState.WAIT_FOR_LOAD or self.state == SimpleErrorServiceState.WAIT_FOR_PLAY)
            ):  # if we are waiting for a LOAD_PROGRAM or PLAY: set class field to the request JOINT_POSITION
                self.loaded_joint_positions = body.get(
                    protocol.CtrlMsgKeys.JOINT_POSITIONS
                )[0]  # we have to index because it is sent as [[x, y, ...]]
                self.state = SimpleErrorServiceState.WAIT_FOR_PLAY
                self.log.info(
                    f"Handled PT LOAD_PROGRAM, settings state to {self.state}"
                )

            elif (
                ctrl_msg_type == protocol.CtrlMsgFields.PLAY
                and self.state == SimpleErrorServiceState.WAIT_FOR_PLAY
            ):  # if we are waiting for PLAY: start a simulation
                self.rmq.send_message(
                    protocol.ROUTING_KEY_SIM_CTRL,
                    {
                        protocol.SimMsgKeys.TYPE: protocol.SimMsgFields.POSITION,
                        protocol.SimMsgKeys.ACTUAL_JOINT_POSITIONS: self.actual_joint_positions,
                        protocol.SimMsgKeys.TARGET_JOINT_POSITIONS: self.loaded_joint_positions,
                    },
                )
                self.log.info("Sent SIM CTRL message")
                self.state = SimpleErrorServiceState.WAIT_FOR_SIM
                self.log.info(f"Handled PT PLAY, settings state to {self.state}")
        except Exception:
            self.log.error(traceback.format_exc())

    def on_pt_state_message_received(self, channel, method, properties, body) -> None:
        try:

            if (
                body.get(protocol.RobotArmStateKeys.ROBOT_MODE)
                == protocol.RobotMode.ROBOT_MODE_RUNNING
            ):  # we only care about PT state when it has finished moving
                return

            if self.state != SimpleErrorServiceState.WAIT_FOR_PT:
                self.actual_joint_positions = body.get(protocol.RobotArmStateKeys.Q_ACTUAL)
                return

            self.latest_pt_tcp_pose = body.get(protocol.RobotArmStateKeys.TCP_POSE)
            self.log.info(f"""Received PT state, calculating error for:
                real TCP position: {self.latest_pt_tcp_pose[:3]}
                sim  TCP position: {self.latest_sim_tcp_pose[:3]}
            """)

            position_diff = []
            error_found = False
            for i in range(3):  # check the X, Y, and Z differences
                diff = abs(self.latest_pt_tcp_pose[i] - self.latest_sim_tcp_pose[i])
                if diff > self.max_diff:
                    error_found = True
                position_diff.append(diff)
                

            self.rmq.send_message(
                protocol.ROUTING_KEY_SIMPLE_ERROR_SERVICE,
                {
                    protocol.SimpleErrorMsgKeys.STATUS: error_found,
                    protocol.SimpleErrorMsgKeys.ACTUAL_POSITION: self.latest_pt_tcp_pose[
                        :3
                    ],
                    protocol.SimpleErrorMsgKeys.SIMULATED_POISITION: self.latest_sim_tcp_pose[
                        :3
                        
                    ],
                    protocol.SimpleErrorMsgKeys.POSITION_DIFFERENCE: position_diff
                },
            )

            self.state = SimpleErrorServiceState.WAIT_FOR_LOAD
            self.log.info(f"Handled PT STATE message, setting state to {self.state}")
        except Exception:
            self.log.error(traceback.format_exc())

    def on_sim_state_message_received(self, channel, method, properties, body) -> None:
        try:
            if self.state != SimpleErrorServiceState.WAIT_FOR_SIM:
                return  # we only care about the sim state if we are currently waiting for it
            sim_result = body.get(protocol.SimMsgKeys.POSITION_RESULT, None)
            if sim_result is None:
                return # this means that it was a different simulation type
            self.latest_sim_tcp_pose = sim_result
            self.state = SimpleErrorServiceState.WAIT_FOR_PT
            self.log.info(f"Handled SIM STATE message, setting state to {self.state}")
        except Exception:
            self.log.error(traceback.format_exc())


if __name__ == "__main__":
    SimpleErrorService()
