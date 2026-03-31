import os
import logging

def get_logger(name) -> logging.Logger:
    assert name is not None
    dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(dir, exist_ok=True)
    file = os.path.join(dir, f"{name}.log")
    config_logging(filename=file, level=logging.INFO)

    return logging.getLogger(name)
    

def config_logging(filename=None, level=logging.WARN):
    if filename is not None:
        # noinspection PyArgumentList
        logging.basicConfig(level=level,
                            handlers=[
                                logging.FileHandler(filename),
                                logging.StreamHandler()
                            ],
                            format='%(asctime)s.%(msecs)03d %(levelname)s %(name)s : %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S'
                            )
    else:
        # noinspection PyArgumentList
        logging.basicConfig(level=level,
                            format='%(asctime)s.%(msecs)03d %(levelname)s %(name)s : %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S'
                            )
