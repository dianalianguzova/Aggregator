from Aggregator.Logger.Logger import get_logger
from Aggregator.ProcessPipeline import ProcessPipeline

def main():
    logger = get_logger("Worker")
    logger.info("Фоновый процесс сбора новостей запущен")

    try:
        pipeline = ProcessPipeline(logger)
        pipeline.run(interval_minutes=60)
    except KeyboardInterrupt:
        logger.info("Парсер остановлен")
    except Exception as e:
        logger.error(f"Ошибка работы парсера: {e}", exc_info=True)

if __name__ == "__main__":
    main()