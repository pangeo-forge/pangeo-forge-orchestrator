import logging
import sys

logger = logging.getLogger("orchestrator")

handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s - %(name)s - %(message)s"),
)
if logger.hasHandlers():
    logger.handlers.clear()
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
