import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ensure log directory exists
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# --- Backend log file ---
log_file = log_dir / "backend.log"

# Rotating handler to keep logs manageable
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
file_handler.setLevel(logging.INFO)

# Log formatting
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
file_handler.setFormatter(formatter)

# Configure logger
logger = logging.getLogger("backend_logger")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)  # Only file, no console

# --- Usage ---
logger.info("Server started")
logger.error("Failed to embed chunk 5 from document X.pdf")
