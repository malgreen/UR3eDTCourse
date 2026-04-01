from multiprocessing import Process

import services.simulation_service


def start_simulation_service() -> None:
    p = Process(target=services.simulation_service.SimulationService)
    p.start()
