from math import floor
import traceback
import numpy as np
from communication import protocol
from communication.rabbitmq import Rabbitmq
from .utils import get_service_logger


class ContinuousErrorService:
    """
    The Continuous Error Service intercepts LOAD_PROGRAM messages to the phyiscal twin,
    it then publishes a simulation request for the trajectory need to reach Q_Actual.
    It then continuously steps through the simulation along with the PT moving, reporting the distance
    between the actual joint rotations and the simulated joint rotations.
    """

    ROUND_AMOUNT = 5

    def __init__(self) -> None:
        # === Logging === #
        self.log = get_service_logger(__name__)
        try:
            self.log.info("Starting ContinuousErrorService...")

            self.trajectory_index = 0
            self.trajectory_simulation: list[list] = []

            self.pt_q_actual = []
            self.pt_q_target = []
            self.pt_max_speed = 0.0
            self.pt_max_accel = 0.0

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
                protocol.ROUTING_KEY_CTRL, self.on_pt_ctrl_message_received
            )
            self.rmq.subscribe(
                protocol.ROUTING_KEY_STATE, self.on_pt_state_message_received
            )
            self.rmq.subscribe(
                protocol.ROUTING_KEY_SIM_STATE, self.on_sim_state_message_received
            )

            self.log.info("ContinuousErrorService consuming...")
            self.rmq.start_consuming()
        except KeyboardInterrupt:
            self.log.info("Shutting down ContinuousErrorService...")
        except Exception:
            self.log.error(traceback.format_exc())
        finally:
            self.log.info("ContinuousErrorService has shut down")

    def on_pt_ctrl_message_received(self, channel, method, properties, body) -> None:
        """
        If a LOAD_PROGRAM message is intercepted, start a simulation
        """
        try:
            ctrl_msg_type = body.get(protocol.CtrlMsgKeys.TYPE)

            if ctrl_msg_type == protocol.CtrlMsgFields.LOAD_PROGRAM:
                new_q_target = body.get(protocol.CtrlMsgKeys.JOINT_POSITIONS, [])
                new_max_speed = body.get(protocol.CtrlMsgKeys.MAX_VELOCITY, None)
                new_max_accel = body.get(protocol.CtrlMsgKeys.ACCELERATION, None)

                if new_q_target == []:
                    return
                self.pt_q_target = [
                    round(x, self.ROUND_AMOUNT) for x in new_q_target[0]
                ]
                if new_max_speed is not None:
                    self.pt_max_speed = new_max_speed
                if new_max_accel is not None:
                    self.pt_max_accel = new_max_accel

                self.send_sim_msg()

        except Exception:
            self.log.error(traceback.format_exc())

    def on_pt_state_message_received(self, channel, method, properties, body) -> None:
        """
        The idea here is either:
            - If PT is idle: keep the PT state up to date
            - If PT is running: check the difference to the simulation
        """
        try:
            q_actual = [
                round(x, self.ROUND_AMOUNT)
                for x in body.get(protocol.RobotArmStateKeys.Q_ACTUAL)
            ]
            q_target = [
                round(x, self.ROUND_AMOUNT)
                for x in body.get(protocol.RobotArmStateKeys.Q_TARGET)
            ]
            max_speed = body.get(protocol.RobotArmStateKeys.JOINT_MAX_SPEED)
            max_accel = body.get(protocol.RobotArmStateKeys.JOINT_MAX_ACCELERATION)
            robot_mode = body.get(protocol.RobotArmStateKeys.ROBOT_MODE)

            if robot_mode == protocol.RobotMode.ROBOT_MODE_IDLE:
                self.pt_q_actual = q_actual
                self.pt_q_target = q_target
                self.pt_max_speed = max_speed
                self.pt_max_accel = max_accel

            if robot_mode == protocol.RobotMode.ROBOT_MODE_RUNNING:
                if self.trajectory_index >= len(self.trajectory_simulation):
                    self.trajectory_index = len(self.trajectory_simulation) - 1
                sim_q_actual = [
                    round(x, self.ROUND_AMOUNT)
                    for x in self.trajectory_simulation[self.trajectory_index]
                ]
                distance = []
                for i, _ in enumerate(q_actual):
                    distance.append(
                        round(abs(q_actual[i] - sim_q_actual[i]), self.ROUND_AMOUNT)
                    )
                self.trajectory_index += 1
                self.log.info(f"""Simulation step {self.trajectory_index -1}:
                    Q_ACTUAL:    {q_actual}
                    Q_SIMULATED: {sim_q_actual}
                    Q_DISTANCE:  {distance}
                """)
                self.rmq.send_message(
                    protocol.ROUTING_KEY_CONTINUOUS_ERROR_SERVICE,
                    {
                        protocol.ContinuousErrorMsgKeys.Q_ACTUAL: q_actual,
                        protocol.ContinuousErrorMsgKeys.Q_SIMULATED: sim_q_actual,
                        protocol.ContinuousErrorMsgKeys.Q_DISTANCE: distance,
                    },
                )

        except Exception:
            self.log.error(traceback.format_exc())

    def on_sim_state_message_received(self, channel, method, properties, body) -> None:
        try:
            if body.get(protocol.SimMsgKeys.TRAJECTORY_RESULT, []) == []:
                return  # we only care about the trajectory result

            self.trajectory_simulation = body.get(protocol.SimMsgKeys.TRAJECTORY_RESULT)
            self.trajectory_index = 0
        except Exception:
            self.log.error(traceback.format_exc())

    def send_sim_msg(self):
        """
        Calculates how many time steps are needed for the trajectory simulation.
        This is done by calculating:
            1. distance to travel
            2. how long to reach top speed -> max speed(deg/s) / max acceleration(deg/s^2)
            3. how long to travel at top speed -> distance(deg) / max_speed(deg/s)
        A simulation message is then sent to begin a trajectory simulation.
        """
        highest_distance = 0.0 # needs to be degrees because max speed is given as degrees/second
        for i, _ in enumerate(self.pt_q_actual):
            distance = abs(self.pt_q_target[i] - self.pt_q_actual[i]) * (180 / np.pi) # radians to degrees
            if distance > highest_distance:
                highest_distance = distance

        expected_time_s = (highest_distance / self.pt_max_speed) + 1 * (
            self.pt_max_speed / self.pt_max_accel
        )
        steps = (
            floor(expected_time_s / 0.05) + 1
        )  # the arm publishes state every 0.05 seconds

        self.rmq.send_message(
            routing_key=protocol.ROUTING_KEY_SIM_CTRL,
            message={
                protocol.SimMsgKeys.TYPE: protocol.SimMsgFields.TRAJECTORY,
                protocol.SimMsgKeys.ACTUAL_JOINT_POSITIONS: self.pt_q_actual,
                protocol.SimMsgKeys.TARGET_JOINT_POSITIONS: self.pt_q_target,
                protocol.SimMsgKeys.TRAJECTORY_STEPS: steps,
            },
        )


if __name__ == "__main__":
    ContinuousErrorService()
