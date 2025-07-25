"""Configuration management for SCDPlayer"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any


class Config:
    """Handle loading and saving application configuration"""
    
    def __init__(self, config_file: str = 'scdplayer_config.json'):
        self.config_file = Path(config_file)
        self.library_folders: List[str] = []
        self.scan_subdirs: bool = True
        self.kh_rando_folder: str = ""
        
    def load_settings(self) -> None:
        """Load settings from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.library_folders = config.get('library_folders', [])
                    self.scan_subdirs = config.get('scan_subdirs', True)
                    self.kh_rando_folder = config.get('kh_rando_folder', "")
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Failed to load config: {e}. Using defaults.")
    
    def save_settings(self) -> None:
        """Save settings to config file"""
        try:
            config = {
                'library_folders': self.library_folders,
                'scan_subdirs': self.scan_subdirs,
                'kh_rando_folder': self.kh_rando_folder
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logging.error(f"Failed to save config: {e}")
