"""Configuration management for SCDPlayer"""
import json
import os
from typing import Dict, List, Any


class Config:
    """Handle loading and saving application configuration"""
    
    def __init__(self, config_file: str = 'scdplayer_config.json'):
        self.config_file = config_file
        self.library_folders: List[str] = []
        self.scan_subdirs: bool = True
        
    def load_settings(self) -> None:
        """Load settings from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.library_folders = config.get('library_folders', [])
                    self.scan_subdirs = config.get('scan_subdirs', True)
        except Exception:
            pass  # Use defaults if config loading fails
    
    def save_settings(self) -> None:
        """Save settings to config file"""
        try:
            config = {
                'library_folders': self.library_folders,
                'scan_subdirs': self.scan_subdirs
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass  # Fail silently if we can't save settings
