"""Help dialog for SCDPlayer"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, 
                            QSplitter, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt
from version import __version__
from ui.dialogs import apply_title_bar_theming


class HelpDialog(QDialog):
    """Help dialog with table of contents and usage guide"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"SCDPlayer v{__version__} - Help Guide")
        self.setModal(True)
        self.resize(1000, 700)
        
        self.setup_ui()
        apply_title_bar_theming(self)
        
    def setup_ui(self):
        """Setup the help dialog UI with sidebar TOC"""
        layout = QVBoxLayout()
        
        # Create splitter for TOC and content
        splitter = QSplitter(Qt.Horizontal)
        
        # Table of Contents sidebar
        self.toc_list = QListWidget()
        self.toc_list.setMaximumWidth(250)
        self.toc_list.setMinimumWidth(200)
        self.setup_table_of_contents()
        self.toc_list.itemClicked.connect(self.navigate_to_section)
        splitter.addWidget(self.toc_list)
        
        # Help content area
        self.help_text = QTextEdit()
        self.help_text.setReadOnly(True)
        self.help_text.setHtml(self.get_help_content())
        splitter.addWidget(self.help_text)
        
        # Set splitter sizes (TOC smaller, content larger)
        splitter.setSizes([250, 750])
        layout.addWidget(splitter)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def setup_table_of_contents(self):
        """Setup the table of contents list"""
        sections = [
            ("Getting Started", "getting-started"),
            ("Setting Up Library", "library-setup"),
            ("Playing Audio", "playing-audio"),
            ("Loop Editor", "loop-editor"),
            ("Audio Analysis", "audio-analysis"),
            ("Volume Controls", "volume-controls"),
            ("KH Randomizer Setup", "kh-rando-setup"),
            ("File Status Colors", "file-status"),
            ("Export Options", "export-options"),
            ("File Conversion", "file-conversion"),
            ("Library Management", "library-management"),
            ("Keyboard Shortcuts", "keyboard-shortcuts"),
            ("File Organization", "file-organization"),
            ("Export Dialog Guide", "export-dialog"),
            ("Troubleshooting", "troubleshooting"),
        ]
        
        for title, anchor in sections:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, anchor)
            self.toc_list.addItem(item)
    
    def navigate_to_section(self, item):
        """Navigate to the selected section"""
        anchor = item.data(Qt.UserRole)
        if anchor:
            # Use scrollToAnchor which is designed for this purpose
            self.help_text.scrollToAnchor(anchor)
    
    def get_help_content(self):
        """Get the help content HTML"""
        return f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #ffffff; 
                    background-color: #2b2b2b;
                    margin: 0;
                    padding: 20px;
                }}
                h1 {{ 
                    color: #4CAF50; 
                    border-bottom: 2px solid #4CAF50; 
                    margin-top: 0;
                }}
                h2 {{ 
                    color: #2196F3; 
                    margin-top: 40px; 
                    margin-bottom: 15px;
                }}
                h3 {{ 
                    color: #FF9800; 
                    margin-top: 25px; 
                    margin-bottom: 10px;
                }}
                .section {{ 
                    background-color: #333333; 
                    padding: 15px; 
                    margin: 15px 0; 
                    border-left: 4px solid #2196F3; 
                    border-radius: 4px;
                }}
                .shortcut {{ 
                    background-color: #444444; 
                    padding: 2px 6px; 
                    border-radius: 3px; 
                    font-family: 'Consolas', monospace;
                    font-weight: bold;
                }}
                .warning {{ 
                    background-color: #3e2723; 
                    border-left: 4px solid #FF5722; 
                    padding: 15px; 
                    margin: 15px 0;
                    border-radius: 4px;
                }}
                .status-green {{ color: #90ee90; font-weight: bold; }}
                .status-orange {{ color: #ffa500; font-weight: bold; }}
                .status-white {{ color: #ffffff; font-weight: bold; }}
                ul {{ margin-left: 20px; }}
                li {{ margin: 8px 0; }}
                .version {{ text-align: center; color: #888888; margin-top: 40px; }}
            </style>
        </head>
        <body>
            <h1 id="top">SCDPlayer v{__version__} User Guide</h1>
            <p><strong>Professional audio player for SCD files with Kingdom Hearts Randomizer integration.</strong></p>
            
            <h2 id="getting-started">Getting Started</h2>
            <div class="section">
                <p>SCDPlayer is designed for managing and playing SCD audio files, particularly for use with the Kingdom Hearts Randomizer. The application supports multiple audio formats and provides seamless conversion capabilities.</p>
            </div>
            
            <h2 id="library-setup">Setting Up Your Library</h2>
            <div class="section">
                <h3>Adding Folders</h3>
                <ul>
                    <li><strong>Add Folder:</strong> Click "Add Folder" to scan directories for audio files</li>
                    <li><strong>Scan Subdirectories:</strong> Enable checkbox to include subfolders in scans</li>
                    <li><strong>Supported Formats:</strong> SCD, WAV, MP3, OGG, FLAC</li>
                    <li><strong>Auto-Scan:</strong> Library refreshes automatically when folders change</li>
                    <li><strong>Remove Folders:</strong> Select folders in the list and click "Remove Folder"</li>
                </ul>
            </div>
            
            <h2 id="playing-audio">Playing Audio</h2>
            <div class="section">
                <h3>Basic Playback</h3>
                <ul>
                    <li><strong>Load File:</strong> Use "Load File" button or double-click library items</li>
                    <li><strong>Play/Pause:</strong> Combined play/pause button (shows play when stopped, pause when playing)</li>
                    <li><strong>Previous/Next:</strong> Navigate between tracks in library</li>
                    <li><strong>Auto-Advance:</strong> Automatically plays next track in library when current ends</li>
                    <li><strong>Seek Bar:</strong> Click or drag to jump to specific positions</li>
                    <li><strong>Time Display:</strong> Shows current position and total duration</li>
                    <li><strong>Metadata Display:</strong> Shows file information, format details, and audio tags</li>
                </ul>
            </div>
            
            <h2 id="loop-editor">Loop Editor</h2>
            <div class="section">
                <h3>Professional Audio Loop Point Editor</h3>
                <p>Access via the "Edit Loop Points" button when a file is loaded. The Loop Editor provides professional-grade audio editing capabilities.</p>
                
                <h3>Core Features</h3>
                <ul>
                    <li><strong>Waveform Visualization:</strong> High-resolution waveform display with zoom controls</li>
                    <li><strong>Sample-Accurate Editing:</strong> Set loop points with sample precision</li>
                    <li><strong>Visual Loop Points:</strong> Drag-and-drop loop markers with real-time preview</li>
                    <li><strong>Timeline Navigation:</strong> Time and sample-based markers for precise positioning</li>
                    <li><strong>Zoom Controls:</strong> Mouse wheel zoom, focus on cursor, full track view</li>
                    <li><strong>Real-time Playback:</strong> Preview loops and volume changes instantly</li>
                </ul>
                
                <h3>Loop Point Controls</h3>
                <ul>
                    <li><strong>Set Loop Points:</strong> Click and drag the start and end loop markers on the waveform</li>
                    <li><strong>Precise Input:</strong> Enter exact sample values in the input fields</li>
                    <li><strong>Test Loops:</strong> Use the play button to preview loops with seamless looping</li>
                    <li><strong>Auto-Save:</strong> Loop points are automatically saved to audio files</li>
                    <li><strong>SCD Compatibility:</strong> Proper loop metadata for Kingdom Hearts randomizer</li>
                </ul>
                
                <h3>Navigation & Controls</h3>
                <ul>
                    <li><strong>Mouse Wheel:</strong> Zoom in/out on waveform</li>
                    <li><strong>F Key:</strong> Toggle follow cursor mode (cursor tracking)</li>
                    <li><strong>Click Waveform:</strong> Jump to position and start playback</li>
                    <li><strong>Scrollbar:</strong> Navigate through long audio files</li>
                    <li><strong>Zoom Controls:</strong> Focus on cursor position or view full track</li>
                </ul>
            </div>
            
            <h2 id="audio-analysis">Audio Analysis</h2>
            <div class="section">
                <h3>Professional Audio Level Analysis</h3>
                <p>The Loop Editor includes comprehensive audio analysis tools for professional audio management.</p>
                
                <h3>Analysis Metrics</h3>
                <ul>
                    <li><strong>Peak Level:</strong> Maximum amplitude in dB (prevent clipping at 0dB)</li>
                    <li><strong>RMS Level:</strong> Perceived loudness measurement in dB</li>
                    <li><strong>LUFS:</strong> Broadcast standard loudness measurement</li>
                    <li><strong>Dynamic Range:</strong> Difference between loudest and softest parts</li>
                    <li><strong>Crest Factor:</strong> Peak-to-RMS ratio indicating audio dynamics</li>
                    <li><strong>Clipping Detection:</strong> Identifies audio distortion and overloads</li>
                    <li><strong>File Information:</strong> Sample rate, bit depth, duration, and total samples</li>
                </ul>
                
                <h3>Smart Recommendations</h3>
                <ul>
                    <li><strong>Automatic Analysis:</strong> Audio is analyzed when files are loaded</li>
                    <li><strong>Intelligent Suggestions:</strong> Context-aware recommendations for audio improvement</li>
                    <li><strong>Gaming Focus:</strong> Recommendations tailored for game audio requirements</li>
                </ul>
            </div>
            
            <h2 id="volume-controls">Volume Controls & Normalization</h2>
            <div class="section">
                <h3>Advanced Volume Adjustment Suite</h3>
                <p>Professional-grade volume normalization tools integrated into the Loop Editor.</p>
                
                <h3>Normalization Methods</h3>
                <ul>
                    <li><strong>Auto Volume:</strong> Intelligent algorithm that adapts to audio characteristics
                        <ul>
                            <li>High dynamic range (>20dB): Conservative peak normalization (-3dB)</li>
                            <li>Low dynamic range (<6dB): RMS normalization (-12dB) for compressed audio</li>
                            <li>Medium dynamic range: Balanced peak normalization (-1dB)</li>
                        </ul>
                    </li>
                    <li><strong>Normalize Peak:</strong> Standard peak normalization to -1dB for maximum loudness</li>
                    <li><strong>Normalize RMS:</strong> Perceived loudness normalization to -12dB</li>
                    <li><strong>Custom Volume:</strong> User-defined target levels with gaming presets</li>
                </ul>
                
                <h3>Gaming-Optimized Presets</h3>
                <ul>
                    <li><strong>Game (-3dB):</strong> Conservative level good for in-game audio</li>
                    <li><strong>Typical (-0.2dB):</strong> Standard game audio peak level</li>
                    <li><strong>Max (-0.1dB):</strong> Maximum level with minimal headroom</li>
                </ul>
                
                <h3>Volume Adjustment Features</h3>
                <ul>
                    <li><strong>Real-time Preview:</strong> Volume changes applied to playback instantly</li>
                    <li><strong>Clipping Prevention:</strong> Automatic gain reduction to prevent distortion</li>
                    <li><strong>Status Indicator:</strong> Window title shows when volume has been modified</li>
                    <li><strong>Reset Function:</strong> Restore original volume levels with one click</li>
                    <li><strong>Safe Editing:</strong> Uses temporary files to prevent data loss</li>
                    <li><strong>Auto-Save:</strong> Volume adjustments saved with loop points</li>
                </ul>
            </div>
            
            <h2 id="kh-rando-setup">Kingdom Hearts Randomizer Integration</h2>
            <div class="section">
                <h3>Setting Up KH Rando</h3>
                <ul>
                    <li><strong>Select Folder:</strong> Click "Select KH Rando Folder" to choose your randomizer music directory</li>
                    <li><strong>Valid Structure:</strong> Must contain at least 4 of these subfolders (case-insensitive): atlantica, battle, boss, cutscene, field, title, wild</li>
                    <li><strong>Folder Case:</strong> Accepts mixed case folder names (e.g., "Atlantica", "BATTLE", "Boss")</li>
                    <li><strong>Auto-Detection:</strong> Application attempts to find common KH Rando locations automatically</li>
                    <li><strong>Status Indicators:</strong> Files show color coding based on KH Rando status</li>
                    <li><strong>Progress Tracking:</strong> Shows conversion progress when exporting multiple files</li>
                </ul>
            </div>
            
            <h2 id="file-status">File Status Colors</h2>
            <div class="section">
                <ul>
                    <li><span class="status-green">Green Text:</span> File exists in KH Rando folder</li>
                    <li><span class="status-orange">Orange Text:</span> Duplicate file (same name, different format)</li>
                    <li><span class="status-white">White Text:</span> Not in KH Rando folder</li>
                </ul>
            </div>
            
            <h2 id="export-options">Export Options</h2>
            <div class="section">
                <h3>Export Methods</h3>
                <ul>
                    <li><strong>Export Selected:</strong> Export chosen files with individual category assignment</li>
                    <li><strong>Export Missing:</strong> Bulk export all files not currently in KH Rando</li>
                    <li><strong>Auto-Convert:</strong> Non-SCD files automatically converted during export</li>
                    <li><strong>Category Assignment:</strong> Assign files to atlantica, battle, boss, cutscene, field, title, or wild</li>
                    <li><strong>Progress Tracking:</strong> Visual progress bar shows conversion and export status</li>
                    <li><strong>Background Processing:</strong> Exports run in background without freezing UI</li>
                </ul>
            </div>
            
            <h2 id="file-conversion">File Conversion</h2>
            <div class="section">
                <h3>Supported Conversions</h3>
                <ul>
                    <li><strong>To WAV:</strong> Convert SCD, MP3, OGG, FLAC files to WAV format</li>
                    <li><strong>To SCD:</strong> Convert WAV files to pseudo-SCD format for KH compatibility</li>
                    <li><strong>Batch Conversion:</strong> Convert multiple selected files with progress tracking</li>
                    <li><strong>Automatic:</strong> Conversions happen automatically during KH Rando export</li>
                    <li><strong>Temporary Files:</strong> Conversion files cleaned up automatically</li>
                    <li><strong>Background Processing:</strong> Conversions run in background threads</li>
                </ul>
            </div>
            
            <h2 id="library-management">Library Management</h2>
            <div class="section">
                <h3>Advanced Features</h3>
                <ul>
                    <li><strong>Delete Selected:</strong> Move files to Recycle Bin (DEL key shortcut)</li>
                    <li><strong>Open File Location:</strong> Open the folder containing selected or currently playing file (Ctrl+L)</li>
                    <li><strong>Convert Selected:</strong> Convert multiple files to WAV or SCD format with progress tracking</li>
                    <li><strong>Cross-Format Detection:</strong> Detects song.mp3 and song.scd as duplicates</li>
                    <li><strong>Root Folder Scanning:</strong> Finds misplaced files in main KH Rando directory</li>
                    <li><strong>Rescan:</strong> Manually refresh library after moving files</li>
                    <li><strong>Multi-Selection:</strong> Select multiple files for batch operations</li>
                </ul>
            </div>
            
            <h2 id="keyboard-shortcuts">Keyboard Shortcuts</h2>
            <div class="section">
                <h3>Main Window</h3>
                <ul>
                    <li><span class="shortcut">DEL</span> - Move selected files to Recycle Bin</li>
                    <li><span class="shortcut">Ctrl+L</span> - Open file location in File Explorer (selected or currently playing file)</li>
                    <li><span class="shortcut">F1</span> - Show this help guide</li>
                    <li><span class="shortcut">Double-Click</span> - Load and play file from library</li>
                    <li><span class="shortcut">Space</span> - Play/pause current track (when controls are focused)</li>
                </ul>
                
                <h3>Loop Editor</h3>
                <ul>
                    <li><span class="shortcut">F</span> - Toggle follow cursor mode (cursor tracking during playback)</li>
                    <li><span class="shortcut">Mouse Wheel</span> - Zoom in/out on waveform at cursor position</li>
                    <li><span class="shortcut">Click Waveform</span> - Jump to position and start playback</li>
                    <li><span class="shortcut">Drag Markers</span> - Move loop start (green) and end (red) points</li>
                    <li><span class="shortcut">Space</span> - Play/pause audio with current loop settings</li>
                </ul>
            </div>
            
            <h2 id="file-organization">File Organization Best Practices</h2>
            <div class="section">
                <ul>
                    <li><strong>Organize by Game:</strong> Create folders for each game (KH1, KH2, etc.)</li>
                    <li><strong>Descriptive Names:</strong> Use clear, descriptive filenames</li>
                    <li><strong>Separate Libraries:</strong> Keep original files separate from KH Rando exports</li>
                    <li><strong>Regular Backups:</strong> Back up your audio collection regularly</li>
                    <li><strong>Consistent Naming:</strong> Use consistent naming conventions across files</li>
                </ul>
            </div>
            
            <h2 id="export-dialog">Export Dialog Guide</h2>
            <div class="section">
                <h3>Using the Export Dialog</h3>
                <ul>
                    <li><strong>Quick Assignment:</strong> Use category buttons to assign all files to the same category</li>
                    <li><strong>Individual Selection:</strong> Use dropdown menus to set specific categories per file</li>
                    <li><strong>Status Indicators:</strong> Files already in KH Rando are marked to avoid duplicates</li>
                    <li><strong>Auto-Detection:</strong> Dialog attempts to find your KH Rando folder automatically</li>
                    <li><strong>Manual Selection:</strong> Browse to select KH Rando folder if auto-detection fails</li>
                </ul>
            </div>
            
            <div class="warning">
                <h3>Important Notes</h3>
                <ul>
                    <li><strong>SCD Conversion:</strong> Creates compatible pseudo-SCD files, not true SCD encoding</li>
                    <li><strong>File Deletion:</strong> Delete operations are permanent and cannot be undone</li>
                    <li><strong>KH Rando Compatibility:</strong> Always test exported files in your randomizer setup</li>
                    <li><strong>Backup First:</strong> Keep backups of important audio files before making changes</li>
                    <li><strong>Volume Adjustments:</strong> Volume changes modify audio data permanently when saved - use reset function if needed</li>
                    <li><strong>Loop Points:</strong> Loop metadata is saved directly to audio files and may not be compatible with all players</li>
                    <li><strong>Temporary Files:</strong> Loop Editor uses system temp directory for safe audio editing - ensure sufficient disk space</li>
                    <li><strong>File Locking:</strong> Close other audio applications before editing files to prevent access conflicts</li>
                </ul>
            </div>
            
            <h2 id="troubleshooting">Troubleshooting</h2>
            <div class="section">
                <h3>Common Issues</h3>
                <ul>
                    <li><strong>Files Won't Play:</strong> Check if file format is supported; try conversion</li>
                    <li><strong>Export Fails:</strong> Verify KH Rando folder structure and permissions</li>
                    <li><strong>Missing Files:</strong> Use "Rescan" to refresh library after moving files</li>
                    <li><strong>Slow Loading:</strong> Reduce library size or disable subdirectory scanning</li>
                    <li><strong>Conversion Errors:</strong> Ensure source files are not corrupted or in use</li>
                    <li><strong>KH Rando Not Detected:</strong> Manually browse to select the correct music folder</li>
                    <li><strong>Case Sensitivity Issues:</strong> KH Rando validation now accepts mixed case folder names</li>
                    <li><strong>File Location Won't Open:</strong> Check file exists and you have permission to access the folder</li>
                    <li><strong>Progress Bars Stuck:</strong> Close and restart application if background tasks freeze</li>
                </ul>
                
                <h3>Loop Editor Issues</h3>
                <ul>
                    <li><strong>Loop Editor Won't Open:</strong> Ensure a file is loaded and playable in the main window first</li>
                    <li><strong>Waveform Not Loading:</strong> Check that the audio file is not corrupted or in an unsupported format</li>
                    <li><strong>Volume Changes Not Saving:</strong> Ensure the audio file is not write-protected or in use by another application</li>
                    <li><strong>Audio Analysis Fails:</strong> Try reloading the file or converting to a supported format</li>
                    <li><strong>Playback Issues in Loop Editor:</strong> Close and reopen the Loop Editor to refresh audio handles</li>
                    <li><strong>Loop Points Not Saving:</strong> Check file permissions and ensure the file is not read-only</li>
                    <li><strong>Zoom Problems:</strong> Use the "Zoom to Full Track" button to reset view if display gets corrupted</li>
                    <li><strong>Performance Issues:</strong> For large files, use lower zoom levels to improve responsiveness</li>
                </ul>
                
                <h3>Volume Control Issues</h3>
                <ul>
                    <li><strong>Volume Adjustment Fails:</strong> Ensure audio file has sufficient bit depth and is not corrupted</li>
                    <li><strong>Clipping After Normalization:</strong> Use lower target levels or try different normalization methods</li>
                    <li><strong>Reset Volume Not Working:</strong> Close and reopen Loop Editor if original audio data is corrupted</li>
                    <li><strong>Volume Changes Not Audible:</strong> Check that volume adjustment was applied and saved properly</li>
                    <li><strong>Temporary File Errors:</strong> Ensure sufficient disk space and write permissions in system temp directory</li>
                </ul>
            </div>
            
            <div class="version">
                <strong>SCDPlayer v{__version__}</strong><br>
                Developed by skylect-dev<br>
                Powered by vgmstream & FFmpeg
            </div>
        </body>
        </html>
        """
