from startup.utils.logging_config import get_logger
from multiprocessing import Process
import traceback
import logging
import services.simulation_service


def start_simulation_service() -> None:
    logger = get_logger("simulation_service")
    try:
        logger.info("Starting SimulationService...")
        # the start_consuming call in the constructor is blocking
        p = Process(target=services.simulation_service.SimulationService)
        p.start()
        p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down SimulationService...")
    except Exception:
        logger.error(traceback.format_exc())
    finally:
        logger.info("Simulation")
    
