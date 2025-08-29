from pathlib import Path
from datetime import datetime
from loguru import logger
import sys
import logging

# Ensure log directory exists next to this file
log_dir = (Path(__file__).parent / "logs")
log_dir.mkdir(exist_ok=True)

# Daily log file name like logs/log_2025-08-29.log
log_file = log_dir / f"log_{datetime.now().strftime('%Y-%m-%d')}.log"

# Reset default handlers and add sinks
logger.remove()
logger.add(
    log_file,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}.{function}:{line} - {message}",
    level="DEBUG",
    encoding="utf-8",
    backtrace=True,
    diagnose=True,
    rotation="00:00",        # rotate at midnight
    retention="14 days",     # keep 14 days of logs
)
# Optional: also log to stderr for local dev. Uncomment if desired.
# logger.add(sys.stderr,
#            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}.{function}:{line} - {message}",
#            level="DEBUG",
#            backtrace=True,
#            diagnose=True)

# Intercept standard logging and route to Loguru so libraries using logging work
class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = "INFO"
        frame, depth = logging.currentframe(), 2
        # Walk back to the original caller outside the logging module
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Configure root logging to use the intercept handler
logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

# Export the configured Loguru logger
__all__ = ["logger"]

# --- Usage ---
logger.info("Server started")
logger.error("Failed to embed chunk 5 from document X.pdf")
