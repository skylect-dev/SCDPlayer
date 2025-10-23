"""Configuration management for SCDToolkit"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any


class Config:
    """Handle loading and saving application configuration"""
    
    def __init__(self, config_file: str = 'scdtoolkit_config.json'):
        self.config_file = Path(config_file)
        self.legacy_config_file = Path('scdplayer_config.json')  # Fallback for renamed app
        self.library_folders: List[str] = []
        self.scan_subdirs: bool = True
        self.kh_rando_folder: str = ""
        
    def load_settings(self) -> None:
        """Load settings from config file (with fallback to legacy scdplayer_config.json)"""
        try:
            config_to_load = None
            
            # First try the new config file
            if self.config_file.exists():
                config_to_load = self.config_file
            # Fall back to legacy config file if new one doesn't exist
            elif self.legacy_config_file.exists():
                logging.info(f"Using legacy config file: {self.legacy_config_file}")
                config_to_load = self.legacy_config_file
                
            if config_to_load:
                with open(config_to_load, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.library_folders = config.get('library_folders', [])
                    self.scan_subdirs = config.get('scan_subdirs', True)
                    self.kh_rando_folder = config.get('kh_rando_folder', "")
                
                # If we loaded from legacy file, save to new file and optionally remove old one
                if config_to_load == self.legacy_config_file:
                    logging.info(f"Migrating settings to new config file: {self.config_file}")
                    self.save_settings()
                    
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
