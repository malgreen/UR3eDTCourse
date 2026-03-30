from enum import StrEnum, auto

from communication import protocol
from communication.rabbitmq import Rabbitmq


class SimpleErrorServiceState(StrEnum):
    IDLE = auto()
    WAIT_FOR_PLAY = auto()
    WAIT_FOR_SIM = auto()
    WAIT_FOR_PT = auto()


class SimpleErrorService:
    """
    TODO: not fully implemented or tested...
    The SimpleErrorService listens along for Control messages to the Physical Twin.
    
    Whenever a `LOAD_PROGRAM` is intercepted, it saves the requested joint positions.
    
    Whenever a `PLAY` is intercepted, it starts a simulation and wait for both the robot
    and the simulation to finish, and it checks for differences in the position of the TCP.
    
    If the difference is above some threshold, a message is sent with the error status.
    The message format is as follows:
    ```py
    msg = {
        'status': True, 
        'actual_position': [x, y, z, r, p, y], 
        'simulated_position': [x, y, z, r, p, y]
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
        self.rmq.subscribe(protocol.ROUTING_KEY_CTRL, self.on_pt_ctrl_message_received)
        self.rmq.subscribe(
            protocol.ROUTING_KEY_STATE, self.on_pt_state_message_received
        )
        self.rmq.subscribe(
            protocol.ROUTING_KEY_SIM_STATE, self.on_sim_state_message_received
        )
        # === fields === #
        self.state: SimpleErrorServiceState = SimpleErrorServiceState.IDLE
        self.loaded_joint_positions = []
        self.latest_sim_tcp_pose = []  # format: [x, y, z, r, p, y]
        self.latest_pt_tcp_pose = []  # format: [x, y, z, r, p, y]
        self.max_diff = 0.01  # TODO

        self.rmq.start_consuming()

    def on_pt_ctrl_message_received(self, channel, method, properties, body) -> None:
        print(f"state: {self.state}")
        ctrl_msg_type = body.get(protocol.CtrlMsgKeys.TYPE)

        if (
            ctrl_msg_type == protocol.CtrlMsgFields.LOAD_PROGRAM
            and (
                self.state == SimpleErrorServiceState.IDLE
                or self.state == SimpleErrorServiceState.WAIT_FOR_PLAY
            )
        ):  # if we are waiting for a LOAD_PROGRAM or PLAY: set class field to the request JOINT_POSITION
            self.loaded_joint_positions = body.get(
                protocol.CtrlMsgKeys.JOINT_POSITIONS
            )[0]  # we have to index because it is sent as [[x, y, ...]]
            self.state = SimpleErrorServiceState.WAIT_FOR_PLAY

        elif (
            ctrl_msg_type == protocol.CtrlMsgFields.PLAY
            and self.state == SimpleErrorServiceState.WAIT_FOR_PLAY
        ):  # if we are waiting for PLAY: start a simulation
            self.rmq.send_message(
                protocol.ROUTING_KEY_SIM_CTRL,
                {
                    protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
                    protocol.CtrlMsgKeys.JOINT_POSITIONS: self.loaded_joint_positions,
                },
            )
            self.state = SimpleErrorServiceState.WAIT_FOR_SIM

    def on_pt_state_message_received(self, channel, method, properties, body) -> None:
        if self.state != SimpleErrorServiceState.WAIT_FOR_PT:
            return  # we only care about PT state if SIM is finished

        if (
            body.get(protocol.RobotArmStateKeys.ROBOT_MODE)
            == protocol.RobotMode.ROBOT_MODE_RUNNING
        ):  # we only care about PT state when it has finished moving
            return

        self.latest_pt_tcp_pose = body.get(protocol.RobotArmStateKeys.TCP_POSE)

        print(f"""
        real TCP: {self.latest_pt_tcp_pose[:3]}
        sim  TCP: {self.latest_sim_tcp_pose[:3]}
        """)

        for i in range(3):  # check the X, Y, and Z differences
            if (
                abs(self.latest_pt_tcp_pose[i] - self.latest_sim_tcp_pose[i])
                > self.max_diff
            ):
                self.rmq.send_message(
                    protocol.ROUTING_KEY_SIMPLE_ERROR_SERVICE,
                    {
                        protocol.SimpleErrorMsgKeys.STATUS: True,
                        protocol.SimpleErrorMsgKeys.ACTUAL_POSITION: self.latest_pt_tcp_pose[:3],
                        protocol.SimpleErrorMsgKeys.SIMULATED_POISITION: self.latest_sim_tcp_pose[:3],
                    },
                )

        self.state = SimpleErrorServiceState.IDLE

    def on_sim_state_message_received(self, channel, method, properties, body) -> None:
        if self.state != SimpleErrorServiceState.WAIT_FOR_SIM:
            return  # we only care about the sim state if we are currently waiting for it
        self.latest_sim_tcp_pose = body.get(protocol.RobotArmStateKeys.TCP_POSE)
        self.state = SimpleErrorServiceState.WAIT_FOR_PT


if __name__ == "__main__":
    SimpleErrorService()
