import asyncio
import os
import logging
from opentele.td import TDesktop
from opentele.api import API

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_conversion():
    tdata_path = "temp_downloads/dl_57540911-296e-4233-991f-0f06e7fa4dd9/extract/19496021141/tdata"
    output_path = "test_session"
    
    print(f"Checking tdata at {tdata_path}")
    if not os.path.exists(tdata_path):
        print("TData path not found!")
        return

    try:
        print("Loading TDesktop...")
        tdesk = TDesktop(tdata_path)
        
        if not tdesk.isLoaded():
            print("Failed to load TData (isLoaded=False)")
            return

        print("Converting to Telethon...")
        # Use default API params for Desktop
        client = await tdesk.ToTelethon(output_path, API.TelegramDesktop)
        
        print("Disconnecting...")
        await client.disconnect()
        
        session_file = f"{output_path}.session"
        if os.path.exists(session_file):
            print(f"Success! Session file created: {session_file}")
        else:
            print("Session file not found after conversion")

    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_conversion())
