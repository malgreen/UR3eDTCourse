
from os import wait
from time import sleep
import services.simulation_service

def start_simulation_service() -> None:
    try:
        # the start_consuming call in the service is blocking
        service = services.simulation_service.SimulationService()
    except KeyboardInterrupt:
        print("Shutting down SimulationService...")
    except Exception as e:
        print(e)
    
if __name__ == "__main__":
    start_simulation_service()
