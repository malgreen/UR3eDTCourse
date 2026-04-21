import requests

from startup.utils.config import resource_file_path_w_setuptools
from startup.utils.docker_service_starter import kill_container, start

containerName = "influx-server"


def start_docker_influxdb():
    logFileName = "logs/influxdb.log"
    dockerComposeDirectoryPath = resource_file_path_w_setuptools("communication/influxdb")
    sleepTimeBetweenAttempts = 1
    maxAttempts = 10

    def test_connection_function():
        try:
            r = requests.get("http://localhost:8086/")
            if r.status_code == 200:
                print("InfluxDB ready:\n " + r.text)
                return True
        except requests.exceptions.ConnectionError:
            return False

    kill_container(containerName)
    start(logFileName,
             dockerComposeDirectoryPath,
             test_connection_function, sleepTimeBetweenAttempts, maxAttempts)


def stop_docker_influxdb():
    kill_container(containerName)


if __name__ == '__main__':
    start_docker_influxdb()
