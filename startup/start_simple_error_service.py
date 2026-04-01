from multiprocessing import Process

import services.simple_error_service


def start_simple_error_service() -> None:
    p = Process(target=services.simple_error_service.SimpleErrorService)
    p.start()
