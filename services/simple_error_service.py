
import json
from communication import protocol
from communication.rabbitmq import Rabbitmq


class SimpleErrorService:
    """
    TODO: not fully implemented or tested...
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
        # not sure if these subscribe calls are consuming...
        self.rmq.subscribe(protocol.ROUTING_KEY_CTRL, self.on_pt_ctrl_message_received)
        self.rmq.subscribe(protocol.ROUTING_KEY_STATE, self.on_pt_state_message_received)
        # === misc === #
        self.sim_queue: list[dict] = []
        self.latest_sim_tcp_pose = [] # should be in [x, y, z, r, p, y]
        self.latest_pt_tcp_pose = []
        self.check_for_error = False


    def on_pt_ctrl_message_received(self, channel, method, properties, body) -> None:
        print("pt ctrl")
        if not body.get(protocol.CtrlMsgKeys.TYPE) == protocol.CtrlMsgFields.LOAD_PROGRAM:
            return
        target_joint_positions = body.get(protocol.CtrlMsgKeys.JOINT_POSITIONS)
        self.rmq.subscribe(protocol.ROUTING_KEY_SIM_STATE, self.on_sim_state_message_received)
        self.rmq.send_message(protocol.ROUTING_KEY_SIM_CTRL, {
            protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
            protocol.CtrlMsgKeys.JOINT_POSITIONS: target_joint_positions
        })


    def on_pt_state_message_received(self, channel, method, properties, body) -> None:
        print("pt state")
        if body.get(protocol.RobotArmStateKeys.ROBOT_MODE == protocol.RobotMode.ROBOT_MODE_RUNNING):
            return # we only care about the state when it has finished moving

        self.latest_pt_tcp_pose = body.get(protocol.RobotArmStateKeys.TCP_POSE)
        if self.check_for_error:
            print(f"""
            Simulation TCP position: {self.latest_sim_tcp_pose}
            Actual TCP position: {body.get(protocol.RobotArmStateKeys.TCP_POSE)}
            """)



    def on_sim_state_message_received(self, channel, method, properties, body) -> None:
        print("sim state")
        
