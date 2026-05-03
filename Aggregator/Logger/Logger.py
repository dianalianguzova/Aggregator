import logging
import os
from logging.handlers import RotatingFileHandler

class Logger:
    _initialized = False
    _common_logfile = "logger/logs/app.log"  # общий файл для всех

    @classmethod
    def setup(cls):
        if cls._initialized:
            return

        os.makedirs('logger/logs', exist_ok=True)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        if not root_logger.handlers:
            console = logging.StreamHandler() #вывод в консоль
            console.setLevel(logging.INFO)
            console.setFormatter(formatter)
            root_logger.addHandler(console)

            file = RotatingFileHandler( #ротирующийся файл
                cls._common_logfile,
                maxBytes=10 * 1024 * 1024, #10мб
                backupCount=3,
                encoding='utf-8'
            )
            file.setLevel(logging.DEBUG)
            file.setFormatter(formatter)
            root_logger.addHandler(file)
        cls._initialized = True


def get_logger(name: str):#получение именованного логгера
    Logger.setup()
    return logging.getLogger(name)


#def debug(self, message: str):
    #self._logger.debug(message)

#def info(self, message: str):
    #self._logger.info(message)

#def error(self, message: str):
    #self._logger.error(message)

#def warning(self, message: str):
    #self._logger.warning(message)
