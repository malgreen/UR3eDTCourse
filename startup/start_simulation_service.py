from startup.utils.logging_config import get_logger
from multiprocessing import Process
import traceback
import logging
import services.simulation_service


def start_simulation_service() -> None:
    p = Process(target=services.simulation_service.SimulationService)
    p.start()

    
