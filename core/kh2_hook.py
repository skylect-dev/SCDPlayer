"""
KH2 SCD Hook - Memory interface for Kingdom Hearts II Final Mix PC.

Connects to the game process and provides SCD hotswap capability via Topaz's SCDHook mod.
Uses dynamic memory scanning to locate PANACEA_ALLOC buffers - compatible with vanilla and Re:Fined.
"""

import logging
import os
import ctypes
import ctypes.wintypes
from typing import Optional, Tuple
import struct


# Windows API constants
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

# Memory region constants
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_IMAGE = 0x1000000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

# PANACEA_ALLOC key names to search for
KEY_MUSIC_APPLY = b"MUSIC_APPLY"
KEY_FIELD_PATH = b"FIELD_PATH"
KEY_BATTLE_PATH = b"BATTLE_PATH"
POINTER_OFFSET = 0x20  # Offset from key string to pointer (from Topaz's notes)


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', ctypes.wintypes.DWORD),
        ('cntUsage', ctypes.wintypes.DWORD),
        ('th32ProcessID', ctypes.wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
        ('th32ModuleID', ctypes.wintypes.DWORD),
        ('cntThreads', ctypes.wintypes.DWORD),
        ('th32ParentProcessID', ctypes.wintypes.DWORD),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', ctypes.wintypes.DWORD),
        ('szExeFile', ctypes.c_char * 260)
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', ctypes.wintypes.DWORD),
        ('th32ModuleID', ctypes.wintypes.DWORD),
        ('th32ProcessID', ctypes.wintypes.DWORD),
        ('GlblcntUsage', ctypes.wintypes.DWORD),
        ('ProccntUsage', ctypes.wintypes.DWORD),
        ('modBaseAddr', ctypes.POINTER(ctypes.c_byte)),
        ('modBaseSize', ctypes.wintypes.DWORD),
        ('hModule', ctypes.wintypes.HMODULE),
        ('szModule', ctypes.c_char * 256),
        ('szExePath', ctypes.c_char * 260)
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', ctypes.c_void_p),
        ('AllocationBase', ctypes.c_void_p),
        ('AllocationProtect', ctypes.wintypes.DWORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', ctypes.wintypes.DWORD),
        ('Protect', ctypes.wintypes.DWORD),
        ('Type', ctypes.wintypes.DWORD)
    ]


class KH2Hook:
    """Handle connection to KH2FM process and memory operations for SCD hotswap."""
    
    def __init__(self):
        self.process_handle = None
        self.process_id = None
        self.base_address = None
        self.music_apply_addr = None
        self.field_path_addr = None
        self.battle_path_addr = None
        
    def connect(self) -> bool:
        """
        Connect to the KH2FM process and locate hook addresses.
        Returns True if successful, False otherwise.
        """
        try:
            # Find the KH2FM process
            self.process_id = self._find_process("KINGDOM HEARTS II FINAL MIX.exe")
            if not self.process_id:
                logging.debug("KH2FM process not found")
                return False
            
            # Open process handle
            self.process_handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
                False,
                self.process_id
            )
            
            if not self.process_handle:
                logging.error("Failed to open KH2FM process handle")
                return False
            
            # Get base address (for reference only)
            self.base_address = self._get_module_base_address(self.process_id, "KINGDOM HEARTS II FINAL MIX.exe")
            if not self.base_address:
                logging.error("Failed to get KH2FM base address")
                self.disconnect()
                return False
            
            # Scan memory for PANACEA_ALLOC keys and resolve pointers
            logging.info(f"KH2 Hook: Scanning memory for PANACEA_ALLOC keys...")
            
            if not self._scan_for_panacea_keys():
                logging.error("Failed to locate PANACEA_ALLOC keys in memory")
                self.disconnect()
                return False
            
            logging.info(f"KH2 Hook connected - PID: {self.process_id}")
            logging.info(f"  MUSIC_APPLY: 0x{self.music_apply_addr:X}")
            logging.info(f"  FIELD_PATH:  0x{self.field_path_addr:X}")
            logging.info(f"  BATTLE_PATH: 0x{self.battle_path_addr:X}")
                
            return True
            
        except Exception as e:
            logging.exception(f"KH2 Hook connection error: {e}")
            self.disconnect()
            return False
    
    def disconnect(self):
        """Close the process handle and clear state."""
        if self.process_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.process_handle)
            except Exception:
                pass
            self.process_handle = None
        
        self.process_id = None
        self.base_address = None
        self.music_apply_addr = None
        self.field_path_addr = None
        self.battle_path_addr = None
    
    def is_connected(self) -> bool:
        """Check if we're currently connected to the process."""
        if not self.process_handle:
            return False
        
        # Verify process still exists
        exit_code = ctypes.wintypes.DWORD()
        result = ctypes.windll.kernel32.GetExitCodeProcess(self.process_handle, ctypes.byref(exit_code))
        if not result or exit_code.value != 259:  # 259 = STILL_ACTIVE
            self.disconnect()
            return False
        
        return True
    
    def _find_process(self, process_name: str) -> Optional[int]:
        """Find process ID by executable name."""
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return None
        
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            
            if ctypes.windll.kernel32.Process32First(snapshot, ctypes.byref(entry)):
                while True:
                    if entry.szExeFile.decode('utf-8', errors='ignore') == process_name:
                        return entry.th32ProcessID
                    
                    if not ctypes.windll.kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                        break
            
            return None
        finally:
            ctypes.windll.kernel32.CloseHandle(snapshot)
    
    def _get_module_base_address(self, process_id: int, module_name: str) -> Optional[int]:
        """Get the base address of a module in the target process."""
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32,
            process_id
        )
        if snapshot == -1:
            return None
        
        try:
            entry = MODULEENTRY32()
            entry.dwSize = ctypes.sizeof(MODULEENTRY32)
            
            if ctypes.windll.kernel32.Module32First(snapshot, ctypes.byref(entry)):
                while True:
                    if entry.szModule.decode('utf-8', errors='ignore') == module_name:
                        return ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                    
                    if not ctypes.windll.kernel32.Module32Next(snapshot, ctypes.byref(entry)):
                        break
            
            return None
        finally:
            ctypes.windll.kernel32.CloseHandle(snapshot)
    
    def _scan_for_panacea_keys(self) -> bool:
        """
        Scan process memory for PANACEA_ALLOC key strings and resolve buffer pointers.
        Uses efficient region-based scanning similar to Cheat Engine.
        """
        if not self.is_connected():
            return False
        
        try:
            # Search for all three keys
            music_key_addr = self._find_string_in_memory(KEY_MUSIC_APPLY)
            field_key_addr = self._find_string_in_memory(KEY_FIELD_PATH)
            battle_key_addr = self._find_string_in_memory(KEY_BATTLE_PATH)
            
            if not music_key_addr or not field_key_addr or not battle_key_addr:
                logging.error("Failed to find PANACEA_ALLOC keys")
                return False
            
            # Read pointers at key_address + 0x20
            music_ptr = self._read_pointer(music_key_addr + POINTER_OFFSET)
            field_ptr = self._read_pointer(field_key_addr + POINTER_OFFSET)
            battle_ptr = self._read_pointer(battle_key_addr + POINTER_OFFSET)
            
            if not music_ptr or not field_ptr or not battle_ptr:
                logging.error("Failed to read PANACEA_ALLOC pointers")
                return False
            
            # Verify pointers are valid (non-null, within process space)
            if music_ptr < 0x10000 or field_ptr < 0x10000 or battle_ptr < 0x10000:
                logging.error("Invalid PANACEA_ALLOC pointers")
                return False
            
            self.music_apply_addr = music_ptr
            self.field_path_addr = field_ptr
            self.battle_path_addr = battle_ptr
            
            return True
            
        except Exception as e:
            logging.exception(f"Error scanning for PANACEA keys: {e}")
            return False
    
    def _find_string_in_memory(self, search_bytes: bytes) -> Optional[int]:
        """
        Fast memory scan for byte pattern. Searches readable/writable regions only.
        Returns the first matching address or None.
        """
        if not self.is_connected():
            return None
        
        # Start above the null page. Note: VirtualQueryEx may report BaseAddress=0
        # (ctypes exposes this as None), so we advance using our running address.
        address = 0x10000
        max_address = 0x7FFFFFFF0000  # User-space limit on x64
        
        while address < max_address:
            mbi = MEMORY_BASIC_INFORMATION()
            result = ctypes.windll.kernel32.VirtualQueryEx(
                self.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )
            
            if not result:
                break

            # RegionSize must be > 0 to make progress.
            if not mbi.RegionSize:
                break

            base_addr = int(mbi.BaseAddress) if mbi.BaseAddress else address
            
            # Check if region is committed and readable
            is_committed = (mbi.State == MEM_COMMIT)
            is_readable = (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_WRITECOPY)) != 0
            no_guard = (mbi.Protect & PAGE_GUARD) == 0
            
            if is_committed and is_readable and no_guard and mbi.RegionSize > 0:
                # Read region and search
                found = self._search_region(base_addr, mbi.RegionSize, search_bytes)
                if found:
                    return found
            
            # Move to next region
            address = base_addr + mbi.RegionSize
        
        return None
    
    def _search_region(self, base_address: int, size: int, search_bytes: bytes) -> Optional[int]:
        """Search a single memory region for the byte pattern."""
        try:
            # Limit chunk size for performance
            chunk_size = min(size, 1024 * 1024)  # 1MB chunks
            buffer = ctypes.create_string_buffer(chunk_size)
            bytes_read = ctypes.c_size_t()
            
            offset = 0
            while offset < size:
                read_size = min(chunk_size, size - offset)
                current_addr = base_address + offset
                
                result = ctypes.windll.kernel32.ReadProcessMemory(
                    self.process_handle,
                    ctypes.c_void_p(current_addr),
                    buffer,
                    read_size,
                    ctypes.byref(bytes_read)
                )
                
                if result and bytes_read.value > 0:
                    # Search for pattern in this chunk
                    data = buffer.raw[:bytes_read.value]
                    idx = data.find(search_bytes)
                    if idx >= 0:
                        return current_addr + idx
                
                offset += read_size
            
            return None
            
        except Exception:
            return None
    
    def _read_pointer(self, address: int) -> Optional[int]:
        """Read an 8-byte pointer from memory (x64)."""
        if not self.is_connected():
            return None
        
        try:
            pointer_value = ctypes.c_uint64()
            bytes_read = ctypes.c_size_t()
            
            result = ctypes.windll.kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(pointer_value),
                8,
                ctypes.byref(bytes_read)
            )
            
            if result and bytes_read.value == 8:
                return pointer_value.value
            
            return None
            
        except Exception:
            return None
    
    def read_byte(self, address: int) -> Optional[int]:
        """Read a single byte from the specified address."""
        if not self.is_connected():
            return None
        
        try:
            value = ctypes.c_byte()
            bytes_read = ctypes.c_size_t()
            
            result = ctypes.windll.kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(value),
                1,
                ctypes.byref(bytes_read)
            )
            
            if result and bytes_read.value == 1:
                return value.value & 0xFF
            
            return None
            
        except Exception as e:
            logging.debug(f"Read byte error at 0x{address:X}: {e}")
            return None
    
    def read_string(self, address: int, max_length: int = 256) -> Optional[str]:
        """Read a null-terminated string from the specified address."""
        if not self.is_connected():
            return None
        
        try:
            buffer = ctypes.create_string_buffer(max_length)
            bytes_read = ctypes.c_size_t()
            
            result = ctypes.windll.kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(address),
                buffer,
                max_length,
                ctypes.byref(bytes_read)
            )
            
            if result and bytes_read.value > 0:
                # Find null terminator
                data = buffer.raw[:bytes_read.value]
                null_idx = data.find(b'\x00')
                if null_idx >= 0:
                    data = data[:null_idx]
                
                return data.decode('utf-8', errors='ignore')
            
            return None
            
        except Exception as e:
            logging.debug(f"Read string error at 0x{address:X}: {e}")
            return None
    
    def write_byte(self, address: int, value: int) -> bool:
        """Write a single byte to the specified address."""
        if not self.is_connected():
            return False
        
        try:
            byte_value = ctypes.c_byte(value & 0xFF)
            bytes_written = ctypes.c_size_t()
            
            result = ctypes.windll.kernel32.WriteProcessMemory(
                self.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(byte_value),
                1,
                ctypes.byref(bytes_written)
            )
            
            if result and bytes_written.value == 1:
                return True
            
            logging.debug(f"Write byte failed at 0x{address:X}")
            return False
            
        except Exception as e:
            logging.error(f"Write byte error at 0x{address:X}: {e}")
            return False
    
    def write_string(self, address: int, text: str, max_length: int = 256) -> bool:
        """
        Write a null-terminated string to the specified address.
        String will be truncated if longer than max_length-1 (to leave room for null).
        """
        if not self.is_connected():
            return False
        
        try:
            # Encode to bytes and ensure null termination
            text_bytes = text.encode('utf-8', errors='ignore')
            if len(text_bytes) >= max_length:
                text_bytes = text_bytes[:max_length-1]
            
            # Create buffer with null padding
            buffer = ctypes.create_string_buffer(max_length)
            buffer.value = text_bytes
            
            bytes_written = ctypes.c_size_t()
            
            result = ctypes.windll.kernel32.WriteProcessMemory(
                self.process_handle,
                ctypes.c_void_p(address),
                buffer,
                max_length,
                ctypes.byref(bytes_written)
            )
            
            if result and bytes_written.value == max_length:
                return True
            
            logging.debug(f"Write string failed at 0x{address:X}")
            return False
            
        except Exception as e:
            logging.error(f"Write string error at 0x{address:X}: {e}")
            return False
    
    def send_scd(self, field_path: Optional[str] = None, battle_path: Optional[str] = None) -> bool:
        """
        Send SCD file path(s) to KH2 for hotswap.
        Blank path = no change for that slot.
        """
        if not self.is_connected():
            return False
        
        if not field_path and not battle_path:
            return False
        
        try:
            # Write paths (empty string = no change)
            self.write_string(self.field_path_addr, field_path or "")
            self.write_string(self.battle_path_addr, battle_path or "")
            
            # Trigger hotswap
            self.write_byte(self.music_apply_addr, 1)
            return True
            
        except Exception as e:
            logging.error(f"KH2 Hook send error: {e}")
            return False
    
    def get_current_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current field and battle paths from memory. Returns (field, battle)."""
        if not self.is_connected():
            return (None, None)
        
        field = self.read_string(self.field_path_addr)
        battle = self.read_string(self.battle_path_addr)
        return (field or None, battle or None)


# Global singleton instance
_hook_instance = None

def get_hook() -> KH2Hook:
    """Get the global KH2Hook instance."""
    global _hook_instance
    if _hook_instance is None:
        _hook_instance = KH2Hook()
    return _hook_instance
