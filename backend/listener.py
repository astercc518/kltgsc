import asyncio
import logging
import sys
import os

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.logging import setup_logging
from app.services.listener_service import ListenerService

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    service = ListenerService()
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Stopping listener service...")
    except Exception as e:
        logger.error(f"Listener service crashed: {e}")

if __name__ == "__main__":
    logger.info("Starting TGSC Listener Worker")
    asyncio.run(main())
