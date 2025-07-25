#!/usr/bin/env python3
"""
Script to create icon.ico from the minimal SVG icon for PyInstaller
"""

import os
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QSize, Qt, QBuffer
from PyQt5.QtWidgets import QApplication
import struct

def create_ico_from_svg():
    """Create icon.ico from assets/icon.svg with multiple sizes"""
    
    # Initialize Qt application (required for SVG rendering)
    app = QApplication([])
    
    # Load SVG
    svg_path = "assets/icon.svg"
    if not os.path.exists(svg_path):
        print(f"Error: {svg_path} not found!")
        return False
    
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        print("Error: Invalid SVG file!")
        return False
    
    # ICO file format requires these specific sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_data = b''
    
    # Create PNG data for each size
    png_data_list = []
    
    for size in sizes:
        # Create pixmap at this size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        # Render SVG to pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        
        # Convert to PNG bytes
        buffer = QBuffer()
        buffer.open(QBuffer.WriteOnly)
        pixmap.save(buffer, "PNG")
        png_data = buffer.data().data()  # Get raw bytes
        buffer.close()
        
        png_data_list.append(png_data)
        print(f"Created {size}x{size} icon ({len(png_data)} bytes)")
    
    # Create ICO file header
    ico_header = struct.pack('<HHH', 0, 1, len(sizes))  # Reserved, Type (1=ICO), Count
    
    # Create directory entries
    directory_entries = b''
    data_offset = 6 + (16 * len(sizes))  # Header + directory entries
    
    for i, (size, png_data) in enumerate(zip(sizes, png_data_list)):
        width = size if size < 256 else 0  # 0 means 256 in ICO format
        height = size if size < 256 else 0
        
        directory_entry = struct.pack('<BBBBHHLL',
            width,          # Width (0 = 256)
            height,         # Height (0 = 256) 
            0,              # Color count (0 for PNG)
            0,              # Reserved
            1,              # Color planes
            32,             # Bits per pixel
            len(png_data),  # Size of PNG data
            data_offset     # Offset to PNG data
        )
        
        directory_entries += directory_entry
        data_offset += len(png_data)
    
    # Combine all parts
    ico_data = ico_header + directory_entries + b''.join(png_data_list)
    
    # Save ICO file
    ico_path = "assets/icon.ico"
    with open(ico_path, 'wb') as f:
        f.write(ico_data)
    
    print(f"Successfully created {ico_path} ({len(ico_data)} bytes)")
    print(f"ICO file contains {len(sizes)} sizes: {', '.join(f'{s}x{s}' for s in sizes)}")
    return True

if __name__ == "__main__":
    if create_ico_from_svg():
        print("Minimal icon creation completed!")
    else:
        print("Icon creation failed!")
