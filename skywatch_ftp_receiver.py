#!/usr/bin/env python3
"""
SkyWatch FTP Receiver - captures images and metadata from SkyWatch software
Runs a simple FTP server to receive images/data from remote SkyWatch instances
"""

import os
import sys
import json
import logging
import socket
from pathlib import Path
from datetime import datetime, timezone
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

# Configuration
RECEIVER_HOST = "0.0.0.0"  # Listen on all interfaces
RECEIVER_PORT = int(os.getenv("SKYWATCH_FTP_PORT", "2121"))
DATA_DIR = Path(os.getenv("SKYWATCH_DATA_DIR", "/srv/doro_lab_projects/skycam"))
IMAGES_DIR = DATA_DIR / "images"  # Gallery directory
ARCHIVE_DIR = DATA_DIR / "archive"
SKYWATCH_FTP_PASSWORD = os.getenv("SKYWATCH_FTP_PASSWORD", "skywatch")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(DATA_DIR / "skywatch_ftp.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SkyWatch-FTP")

class SkyWatchFTPHandler(FTPHandler):
    """Custom FTP handler to process SkyWatch uploads"""
    
    def handle_stray_data(self):
        """Suppress redundant logging"""
        pass
    
    def on_file_received(self, file):
        """Called after file is completely uploaded"""
        try:
            # Get the uploaded file path
            filepath = Path(file)
            filename = filepath.name
            
            logger.info(f"File upload complete: {filename}")
            
            # Process based on file type
            if filename.endswith(('.jpg', '.jpeg')):
                self._process_image_complete(filepath)
            elif filename.endswith('.json'):
                self._process_metadata(filename)
        except Exception as e:
            logger.error(f"Error in on_file_received: {e}", exc_info=True)
    
    def _process_image_complete(self, source_path):
        """Handle completely uploaded image file"""
        try:
            if not source_path.exists() or source_path.stat().st_size == 0:
                logger.warning(f"Skipping 0-byte or missing file: {source_path}")
                return
            
            filename = source_path.name
            file_size = source_path.stat().st_size
            
            # Archive with timestamp
            archive_subdir = ARCHIVE_DIR / datetime.now(timezone.utc).strftime("%Y/%m/%d")
            archive_subdir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(source_path, archive_subdir / source_path.name)
            
            # Also copy to images directory for gallery
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, IMAGES_DIR / source_path.name)
            
            # Update status file
            self._update_status("image_received", file_size, filename)
            
            logger.info(f"Image archived: {filename} ({file_size} bytes)")
        
        except Exception as e:
            logger.error(f"Error processing complete image {source_path}: {e}", exc_info=True)
    
    def _process_metadata(self, filename):
        """Handle uploaded metadata/settings file"""
        try:
            source_path = Path(self.fs.root) / filename
            
            if source_path.exists() and source_path.stat().st_size > 0:
                # Try to parse and merge with forecast
                data = json.loads(source_path.read_text())
                self._merge_skywatch_data(data)
                
                logger.info(f"Metadata processed: {filename}")
        
        except Exception as e:
            logger.error(f"Error processing metadata {filename}: {e}", exc_info=True)
    
    def _merge_skywatch_data(self, skywatch_data):
        """Merge SkyWatch sensor data into forecast"""
        try:
            forecast_path = DATA_DIR / "forecast.json"
            
            if forecast_path.exists():
                forecast = json.loads(forecast_path.read_text())
            else:
                forecast = {"current": {}, "data_sources": {}}
            
            # Extract SkyWatch temperature and humidity if available
            if "outdoor_temp" in skywatch_data:
                forecast["current"]["temperature_c"] = float(skywatch_data["outdoor_temp"])
            
            if "humidity" in skywatch_data:
                forecast["current"]["humidity_pct"] = float(skywatch_data["humidity"])
            
            # Mark SkyWatch as active data source
            if "data_sources" not in forecast:
                forecast["data_sources"] = {}
            
            forecast["data_sources"]["skywatch"] = {
                "available": True,
                "source": "SkyWatch Camera",
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            
            # Update timestamp
            forecast["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            forecast_path.write_text(json.dumps(forecast, indent=2))
            logger.info("Forecast updated with SkyWatch data")
        
        except Exception as e:
            logger.error(f"Error merging SkyWatch data: {e}", exc_info=True)
    
    def _update_status(self, event_type, size=0, filename=""):
        """Update connection status file"""
        try:
            status_file = DATA_DIR / "skywatch_status.json"
            
            status = {
                "last_event": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_filename": filename,
                "last_size_bytes": size,
                "connection": "active",
                "receiver_address": f"{self.socket.getpeername()[0]}:{self.socket.getpeername()[1]}"
            }
            
            status_file.write_text(json.dumps(status, indent=2))
        
        except Exception as e:
            logger.debug(f"Could not update status: {e}")

class SkyWatchAuthorizer(DummyAuthorizer):
    """Allow SkyWatch user to authenticate with any password."""

    def validate_authentication(self, username, password, handler):
        if username == "skywatch":
            return
        return super().validate_authentication(username, password, handler)

def run_ftp_server():
    """Start FTP server to receive SkyWatch uploads"""
    
    # Create necessary directories
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"SkyWatch FTP Receiver starting...")
    logger.info(f"  Listen: {RECEIVER_HOST}:{RECEIVER_PORT}")
    logger.info(f"  Data dir: {DATA_DIR}")
    logger.info(f"  Gallery dir: {IMAGES_DIR}")  # Updated for clarity
    
    # Setup FTP authorizer (allow anonymous and flexible SkyWatch login)
    authorizer = SkyWatchAuthorizer()
    authorizer.add_anonymous(str(DATA_DIR), perm="elradfmw")
    authorizer.add_user(
        "skywatch",
        SKYWATCH_FTP_PASSWORD,
        str(DATA_DIR),
        perm="elradfmw"  # Read/write permissions
    )
    
    # Setup FTP handler
    SkyWatchFTPHandler.authorizer = authorizer
    handler = SkyWatchFTPHandler
    handler.permit_foreign_addresses = True
    handler.passive_ports = range(60000, 60100)
    
    # Create and run server
    server = FTPServer((RECEIVER_HOST, RECEIVER_PORT), handler)
    
    logger.info("FTP server ready. Waiting for SkyWatch connections...")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down FTP server...")
        server.close_all()
        sys.exit(0)

if __name__ == "__main__":
    try:
        run_ftp_server()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
