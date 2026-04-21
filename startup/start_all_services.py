from startup.start_docker_influxdb import start_docker_influxdb
from startup.start_docker_rabbitmq import start_docker_rabbitmq
from startup.start_simple_error_service import start_simple_error_service
from startup.start_simulation_service import start_simulation_service
from startup.start_monitoring_service import start_monitoring_service
from startup.start_ur3e_mockup import start_robot_arm_mockup
from startup.utils.start_as_daemon import start_as_daemon

if __name__ == "__main__":
    start_docker_rabbitmq()
    start_docker_influxdb()
    start_as_daemon(start_robot_arm_mockup)
    start_simulation_service()
    start_simple_error_service()
    start_monitoring_service()
