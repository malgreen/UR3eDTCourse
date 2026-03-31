from os import path
import logging


def get_service_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(
                path.join(
                    path.dirname(path.dirname(__file__)),
                    "logs",
                    f"{name}.log",
                )
            ),
            logging.StreamHandler(),
        ],
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s : %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)
