from multiprocessing import Process

import services.continuous_error_service


def start_continuous_error_service() -> None:
    p = Process(target=services.continuous_error_service.ContinuousErrorService)
    p.start()
