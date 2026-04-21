"""Monitoring Service for handling InfluxDB operations"""

from datetime import datetime, timezone

from communication import protocol
from communication.rabbitmq import Rabbitmq
#from docker import client
from influxdb_client import InfluxDBClient, Point, WritePrecision # pip install influxdb-client
from influxdb_client.client.write_api import SYNCHRONOUS
from startup.utils import load_config_w_setuptools
from .utils import get_service_logger


class MonitoringService:
    def __init__(self) -> None:
        self.log = get_service_logger(__name__)
        # self.log = logging.basicConfig()
        config = load_config_w_setuptools("startup.conf")

        # === InfluxDB === #
        self.client = InfluxDBClient(url=config["influxdb.url"], token=config["influxdb.token"], org=config["influxdb.org"])
        self.bucket = config["influxdb.bucket"]
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

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
        self.log.info(f"{__name__} consuming...")
        self.rmq.start_consuming()

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
            point.field(f"q_actual_{i}", float(v))
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.QD_ACTUAL)):
            point.field(f"qd_actual_{i}", float(v))
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.Q_TARGET)):
            point.field(f"q_target_{i}", float(v))
        for i, v in enumerate(body.get(protocol.RobotArmStateKeys.TCP_POSE)):
            point.field(f"tcp_pose_{i}", float(v))

        # Write the point to the bucket
        self.write_api.write(bucket=self.bucket, org=self.client.org, record=point)

    def on_state_msg_received(self, ch, method, properties, body: dict):
        "get data from rappitmq and call write_data to write it to influxdb server"
        # print(f"Received message with body: {body}")
        self.write_data(body)


    def close(self):
        self.client.close()


if __name__ == "__main__":
    MonitoringService()