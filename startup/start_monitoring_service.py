from multiprocessing import Process

import services.monitoring_service


def start_monitoring_service() -> None:
    p = Process(target=services.monitoring_service.MonitoringService)
    p.start()
