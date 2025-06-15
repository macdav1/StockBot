import logging
import os
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Main log file: daily_runner.log (rotates after 5MB, keeps 5 backups)
log_file = os.path.join("logs", "daily_runner.log")

logger = logging.getLogger("StockAppLogger")
logger.setLevel(logging.DEBUG)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)

# Console handler (so you still see everything on screen)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Separate error file
error_file = os.path.join("logs", "errors.log")
error_handler = RotatingFileHandler(error_file, maxBytes=5*1024*1024, backupCount=5)
error_handler.setFormatter(formatter)
error_handler.setLevel(logging.ERROR)

logger.addHandler(error_handler)
