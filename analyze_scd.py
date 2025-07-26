import struct

# Read more of the SCD file to find loop points
with open('ffiv_battle2.scd', 'rb') as f:
    data = f.read(1024)  # First 1KB

loop_start = 369313
loop_end = 3308958

# Search for these patterns in the first 1KB
found_start = []
found_end = []

for i in range(len(data) - 4):
    chunk = data[i:i+4]
    value = struct.unpack('<I', chunk)[0]
    if value == loop_start:
        found_start.append(i)
    elif value == loop_end:
        found_end.append(i)

print(f'Loop start {loop_start} (0x{loop_start:x}) found at offsets: {found_start}')
print(f'Loop end {loop_end} (0x{loop_end:x}) found at offsets: {found_end}')

# If we found them, show the context around those offsets
for offset in found_start + found_end:
    start = max(0, offset - 8)
    end = min(len(data), offset + 12)
    context = data[start:end]
    print(f'Context around offset {offset}: {context.hex()}')
    print(f'  Bytes {start}-{end-1}: {" ".join(f"{b:02x}" for b in context)}')

# Also show the header structure
print('\nSCD Header (first 64 bytes):')
header = data[:64]
for i in range(0, len(header), 16):
    line = header[i:i+16]
    hex_str = ' '.join(f'{b:02x}' for b in line)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in line)
    print(f'{i:04x}: {hex_str:<48} {ascii_str}')
