"""Core logic for Music Pack creation for KH:ReFined"""
import os
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class TrackListParser:
    """Parse the TrackList.txt file to extract track names and file mappings"""
    
    @staticmethod
    def parse_track_list(track_list_path: str) -> List[Tuple[str, str]]:
        """
        Parse TrackList.txt and return list of (track_name, filename) tuples.
        
        Args:
            track_list_path: Path to TrackList.txt file
            
        Returns:
            List of (track_name, filename) tuples sorted by filename
        """
        tracks = []
        try:
            with open(track_list_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse format: "Track Name - musicXXX.win32.scd"
                    if ' - ' in line:
                        parts = line.rsplit(' - ', 1)
                        if len(parts) == 2:
                            track_name = parts[0].strip()
                            filename = parts[1].strip()
                            tracks.append((track_name, filename))
            
            # Sort by filename (numerical order)
            tracks.sort(key=lambda x: x[1])
            
        except Exception as e:
            logging.error(f"Error parsing TrackList.txt: {e}")
        
        return tracks


class MusicPackMetadata:
    """Container for music pack metadata"""
    
    def __init__(self, pack_name: str, author: str, description: str, slot: int):
        self.pack_name = pack_name
        self.author = author
        self.description = description
        self.slot = slot  # 1 or 2
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate metadata. Returns (is_valid, error_message)"""
        if not self.pack_name or not self.pack_name.strip():
            return False, "Pack name is required"
        
        if self.slot not in [0, 1, 2]:
            return False, "Slot must be 0, 1, or 2"
        
        return True, None


class MusicPackExporter:
    """Handles the export of music packs to ZIP format"""
    
    def __init__(self, template_base_path: str):
        """
        Initialize the exporter.
        
        Args:
            template_base_path: Path to the music_pack_creator folder containing templates
        """
        self.template_base_path = Path(template_base_path)
    
    def get_template_path(self, slot: int) -> Path:
        """Get the template path for the specified slot"""
        return self.template_base_path / f'KH2-MusicTemplateSLOT{slot}-main'
    
    def _calculate_width(self, text: str, base_width: int = 100) -> int:
        """Calculate width percentage for sys.yml text, minimum 80%"""
        # Estimate width based on character count
        # Longer text needs narrower width to fit
        char_count = len(text)
        
        if char_count <= 15:
            width = base_width
        elif char_count <= 20:
            width = 90
        elif char_count <= 25:
            width = 85
        else:
            width = 80
        
        # Never go below 80%
        return max(80, width)
    
    def export_pack(self, 
                    output_file: str,
                    mod_metadata: MusicPackMetadata,
                    game_metadata: MusicPackMetadata,
                    track_assignments: Dict[str, str],
                    progress_callback=None,
                    converter=None,
                    language_names: Dict[str, str] = None,
                    language_descriptions: Dict[str, str] = None) -> bool:
        """
        Export a music pack to a ZIP file.
        
        Args:
            output_file: Path where the ZIP file should be saved
            mod_metadata: MusicPackMetadata for mod.yml (OpenKH Mod Manager)
            game_metadata: MusicPackMetadata for sys.yml (in-game display)
            track_assignments: Dict mapping vanilla filename -> source file path
            progress_callback: Optional callback(current, total, message) for progress updates
            converter: Optional AudioConverter instance for non-SCD file conversion
            language_names: Optional dict of language codes to pack names (e.g., {'en': 'Name', 'it': 'Nome'})
            language_descriptions: Optional dict of language codes to descriptions
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate both metadata objects
            is_valid, error = mod_metadata.validate()
            if not is_valid:
                logging.error(f"Invalid mod metadata: {error}")
                return False
            
            is_valid, error = game_metadata.validate()
            if not is_valid:
                logging.error(f"Invalid game metadata: {error}")
                return False
            
            # Get template folder (use mod_metadata slot)
            template_folder = self.get_template_path(mod_metadata.slot)
            if not template_folder.exists():
                logging.error(f"Template folder not found: {template_folder}")
                return False
            
            if progress_callback:
                progress_callback(10, 100, "Copying template files...")
            
            # Create temporary directory for building the pack
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy template structure
                shutil.copytree(template_folder, temp_path / 'pack')
                pack_root = temp_path / 'pack'
                
                if progress_callback:
                    progress_callback(30, 100, "Copying music files...")
                
                # Create bgm folder if it doesn't exist
                bgm_folder = pack_root / 'bgm'
                bgm_folder.mkdir(exist_ok=True)
                
                # Clear existing SCD files from template
                for existing_file in bgm_folder.glob('*.scd'):
                    existing_file.unlink()
                
                # Copy assigned tracks (with conversion if needed)
                total_tracks = len(track_assignments)
                for idx, (filename, source_file) in enumerate(track_assignments.items()):
                    dest_file = bgm_folder / filename
                    
                    # Check if conversion is needed
                    if not source_file.lower().endswith('.scd'):
                        if progress_callback:
                            progress_callback(30 + int((idx / total_tracks) * 35), 100, 
                                            f"Converting: {os.path.basename(source_file)}")
                        
                        # Convert to SCD if converter is available
                        if converter:
                            try:
                                # Use the converter to convert to SCD
                                temp_output = str(bgm_folder / f"temp_{filename}")
                                success = converter.convert_to_scd(source_file, str(dest_file))
                                if not success:
                                    logging.error(f"Failed to convert {source_file} to SCD")
                                    # Copy original file as fallback (may not work in game)
                                    shutil.copy2(source_file, dest_file)
                            except Exception as e:
                                logging.error(f"Error converting {source_file}: {e}")
                                # Copy original file as fallback
                                shutil.copy2(source_file, dest_file)
                        else:
                            logging.warning(f"No converter available for {source_file}, copying as-is")
                            shutil.copy2(source_file, dest_file)
                    else:
                        # Direct copy for SCD files
                        if progress_callback:
                            progress_callback(30 + int((idx / total_tracks) * 35), 100, 
                                            f"Copying: {filename}")
                        shutil.copy2(source_file, dest_file)
                
                if progress_callback:
                    progress_callback(70, 100, "Updating metadata...")
                
                # Update mod.yml with mod_metadata
                self._update_mod_yml(pack_root / 'mod.yml', mod_metadata)
                
                # Update sys.yml with game_metadata (in-game display)
                self._update_sys_yml(pack_root / 'msg' / 'sys.yml', game_metadata, language_names, language_descriptions)
                
                if progress_callback:
                    progress_callback(85, 100, "Creating ZIP archive...")
                
                # Create ZIP file
                self._create_zip(pack_root, output_file)
                
                if progress_callback:
                    progress_callback(100, 100, "Complete!")
            
            return True
            
        except Exception as e:
            logging.error(f"Error exporting music pack: {e}", exc_info=True)
            return False
    
    def _update_mod_yml(self, mod_yml_path: Path, metadata: MusicPackMetadata):
        """Update mod.yml with pack metadata"""
        try:
            with open(mod_yml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace title, author, and description
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('title:'):
                    lines[i] = f'title: {metadata.pack_name} (Slot {metadata.slot}) [KH2]'
                elif line.startswith('originalAuthor:'):
                    lines[i] = f'originalAuthor: {metadata.author}'
                elif line.startswith('description:'):
                    lines[i] = f'description: {metadata.description}'
            
            with open(mod_yml_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
                
        except Exception as e:
            logging.warning(f"Error updating mod.yml: {e}")
    
    def _update_sys_yml(self, sys_yml_path: Path, metadata: MusicPackMetadata, 
                       language_names: Dict[str, str] = None,
                       language_descriptions: Dict[str, str] = None):
        """Update sys.yml with pack name and description for all languages"""
        try:
            with open(sys_yml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Determine which IDs to use based on slot
            if metadata.slot == 0:
                name_id = '0x5719'
                desc_id = '0x571A'
            elif metadata.slot == 1:
                name_id = '0x571B'
                desc_id = '0x571C'
            else:  # slot 2
                name_id = '0x571D'
                desc_id = '0x571E'
            
            # Use language-specific names if provided, otherwise use base pack name for all
            if language_names:
                # Calculate width per language
                lang_name_data = {}
                for lang_code, lang_name in language_names.items():
                    width = self._calculate_width(lang_name)
                    lang_name_data[lang_code] = (lang_name, width)
            else:
                # Fallback: use same name and width for all languages
                width = self._calculate_width(metadata.pack_name)
                lang_name_data = {
                    'en': (metadata.pack_name, width),
                    'it': (metadata.pack_name, width),
                    'gr': (metadata.pack_name, width),
                    'fr': (metadata.pack_name, width),
                    'sp': (metadata.pack_name, width)
                }
            
            # Use language-specific descriptions if provided
            if language_descriptions:
                lang_desc_data = language_descriptions
            else:
                # Fallback: use same description for all languages
                lang_desc_data = {
                    'en': metadata.description,
                    'it': metadata.description,
                    'gr': metadata.description,
                    'fr': metadata.description,
                    'sp': metadata.description
                }
            
            lines = content.split('\n')
            result_lines = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                # Check for name block
                if name_id in line:
                    result_lines.append(line)
                    i += 1
                    # Replace all language entries for name with width modifier
                    while i < len(lines) and not lines[i].strip().startswith('- id:'):
                        if ':' in lines[i] and any(lang in lines[i] for lang in ['en:', 'it:', 'gr:', 'fr:', 'sp:']):
                            lang_code = lines[i].split(':')[0].strip()
                            if lang_code in lang_name_data:
                                lang_name, lang_width = lang_name_data[lang_code]
                                result_lines.append(f'  {lang_code}: "{{:width {lang_width}}}{lang_name}"')
                            else:
                                result_lines.append(lines[i])
                        else:
                            result_lines.append(lines[i])
                        i += 1
                    continue
                
                # Check for description block
                if desc_id in line:
                    result_lines.append(line)
                    i += 1
                    # Replace all language entries for description and skip multi-line content
                    while i < len(lines) and not lines[i].strip().startswith('- id:'):
                        # Check if this is a language line (starts with lang code)
                        if ':' in lines[i] and any(lang in lines[i] for lang in ['en:', 'it:', 'gr:', 'fr:', 'sp:']):
                            lang_code = lines[i].split(':')[0].strip()
                            if lang_code in lang_desc_data:
                                result_lines.append(f'  {lang_code}: "{lang_desc_data[lang_code]}"')
                            else:
                                result_lines.append(f'  {lang_code}: "{metadata.description}"')
                            i += 1
                            # Skip any multi-line continuation (indented lines without language codes)
                            while i < len(lines):
                                next_line = lines[i].strip()
                                # If next line is empty, new language entry, or new ID block, stop skipping
                                if (not next_line or 
                                    next_line.startswith('- id:') or 
                                    any(lang in lines[i] for lang in ['en:', 'it:', 'gr:', 'fr:', 'sp:'])):
                                    break
                                i += 1
                        else:
                            # Keep blank lines and other formatting
                            if not lines[i].strip():
                                result_lines.append(lines[i])
                            i += 1
                    continue
                
                result_lines.append(line)
                i += 1
            
            with open(sys_yml_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(result_lines))
                
        except Exception as e:
            logging.warning(f"Error updating sys.yml: {e}")
    
    def _create_zip(self, source_dir: Path, output_file: str):
        """Create a ZIP archive from the pack directory"""
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)
