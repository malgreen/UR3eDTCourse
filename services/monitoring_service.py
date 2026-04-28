import traceback

from datetime import datetime, timezone

from communication import protocol
from communication.rabbitmq import Rabbitmq
#from docker import client
from influxdb_client import InfluxDBClient, Point, WritePrecision # pip install influxdb-client
from influxdb_client.client.write_api import SYNCHRONOUS
from startup.utils import load_config_w_setuptools
from .utils import get_service_logger
import mstlo_python as mstlo


class MonitoringService:
    """Monitoring Service for handling InfluxDB operations"""
    def __init__(self) -> None:
        self.log = get_service_logger(__name__)
        try:
            config = load_config_w_setuptools("startup.conf")

            # === InfluxDB === #
            self.client = InfluxDBClient(url=config["influxdb.url"], token=config["influxdb.token"], org=config["influxdb.org"])
            self.bucket = config["influxdb.bucket"]
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

            # STL atomic monitor: joint speed must stay below the maximum allowed speed
            MAX_SPEED_degpsec = 60.0  # placeholder
            self.speed_vars = mstlo.Variables()
            self.speed_vars.set("max_speed", MAX_SPEED_degpsec)

            self.speed_monitors = [
                mstlo.Monitor(
                    formula=mstlo.parse_formula("qd <= $max_speed"),
                    semantics="Rosi",
                    variables=self.speed_vars,
                )
                for _ in range(6)
            ]


            # === RabbitMQ === #
            self.rmq: Rabbitmq = Rabbitmq(
                ip=config["rabbitmq.ip"],
                port=config["rabbitmq.port"],
                username=config["rabbitmq.username"],
                password=config["rabbitmq.password"],
                vhost=config["rabbitmq.vhost"],
                exchange=config["rabbitmq.exchange"],
                type="topic",
            )
            self.rmq.connect_to_server()
            self.log.info("Connected to RabbitMQ")
            
            # === Callbacks === #
            self.rmq.subscribe(
                protocol.ROUTING_KEY_STATE, self.on_state_msg_received
            )
            self.rmq.subscribe(
                protocol.ROUTING_KEY_SIMPLE_ERROR_SERVICE, self.on_error_msg_received
            )
            self.log.info(f"{__name__} consuming...")
            self.rmq.start_consuming()
        except KeyboardInterrupt:
            self.log.info("Shutting down MonitoringService...")
        except Exception:
            self.log.error(traceback.format_exc())
        finally:
            self.log.info("MonitoringService has shut down")

    def write_data(self, body: dict):
        "Write data to InfluxDB server"
        # Get timestamp for now in UTC
        now = datetime.now(timezone.utc)

        # Create a point with a measurement, tag, field, and a timestamp
        point = Point("_ur3e_pt_state") \
            .tag("source", "monitoring_service") \
            .field(protocol.RobotArmStateKeys.ROBOT_MODE, body.get(protocol.RobotArmStateKeys.ROBOT_MODE)) \
            .field(protocol.RobotArmStateKeys.TIMESTAMP, body.get(protocol.RobotArmStateKeys.TIMESTAMP)) \
            .field(protocol.RobotArmStateKeys.JOINT_MAX_SPEED, body.get(protocol.RobotArmStateKeys.JOINT_MAX_SPEED)) \
            .field(protocol.RobotArmStateKeys.JOINT_MAX_ACCELERATION, body.get(protocol.RobotArmStateKeys.JOINT_MAX_ACCELERATION)) \
            .time(now)
        
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.Q_ACTUAL)):
            point.field(f"q_actual_{i}", v)
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.QD_ACTUAL)):
            point.field(f"qd_actual_{i}", v)
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.Q_TARGET)):
            point.field(f"q_target_{i}", v)
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.TCP_POSE)):
            point.field(f"tcp_pose_{i}", v)

        # Write the point to the bucket
        self.write_api.write(bucket=self.bucket, org=self.client.org, record=point)

        qd_actual = body.get(protocol.RobotArmStateKeys.QD_ACTUAL) or []
        max_speed = body.get(protocol.RobotArmStateKeys.JOINT_MAX_SPEED)

        if not qd_actual or max_speed is None:
            return

        self.speed_vars.set("max_speed", max_speed)

        timestamp = now.timestamp()

        for joint_index, joint_speed in enumerate(qd_actual):
            result = self.speed_monitors[joint_index].update(
                signal="qd",
                value=abs(joint_speed),
                timestamp=timestamp,
            )

            verdicts = result.verdicts()

            if verdicts:
                self.store_speed_stl_robustness(joint_index, verdicts)
                self.log.info(f"velocity monitor for joint nr {joint_index}: {result}")


    


    def store_speed_stl_robustness(self, joint_index: int, verdicts):
        records = []

        for timestamp, robustness_interval in verdicts:
            lower_bound, upper_bound = robustness_interval

            lower_bound = -20.0 if lower_bound == float("-inf") else lower_bound
            upper_bound = 20.0 if upper_bound == float("inf") else upper_bound

            records.append({
                "measurement": "_stl_speed_monitor",
                "tags": {
                    "source": "monitoring_service",
                    "joint": str(joint_index),
                },
                "time": int(timestamp * 1e9),
                "fields": {
                    "robustness_lower_bound": lower_bound,
                    "robustness_upper_bound": upper_bound,
                },
            })

        if len(records) > 0:
            self.write_api.write(bucket=self.bucket, org=self.client.org, record=records)


    def on_state_msg_received(self, ch, method, properties, body: dict):
        "get data from rappitmq and call write_data to write it to influxdb server"
        # print(f"Received message with body: {body}")
        self.write_data(body)

    def write_error_data(self, body: dict):
        "Write simple error event to InfluxDB server"
        now = datetime.now(timezone.utc)

        point = Point("_simple_error_service") \
            .tag("source", "simple_error_service") \
            .field(protocol.SimpleErrorMsgKeys.STATUS, body.get(protocol.SimpleErrorMsgKeys.STATUS)) \
            .time(now)

        actual = body.get(protocol.SimpleErrorMsgKeys.ACTUAL_POSITION) or []
        simulated = body.get(protocol.SimpleErrorMsgKeys.SIMULATED_POISITION) or []
        diff = body.get(protocol.SimpleErrorMsgKeys.POSITION_DIFFERENCE) or []
        axes = ("x", "y", "z")

        for i, v in enumerate(actual):
            point.field(f"actual_{axes[i] if i < len(axes) else i}", v)
        for i, v in enumerate(simulated):
            point.field(f"simulated_{axes[i] if i < len(axes) else i}", v)
        for i, v in enumerate(diff):
            point.field(f"diff_{axes[i]}", v)
            
        self.log.info(point)

        self.write_api.write(bucket=self.bucket, org=self.client.org, record=point)

    def on_error_msg_received(self, ch, method, properties, body: dict):
        "Handle simple error messages and write them to InfluxDB"
        self.log.info(f"Received simple error event: {body}")
        self.write_error_data(body)


    def close(self):
        self.client.close()


if __name__ == "__main__":
    MonitoringService()
