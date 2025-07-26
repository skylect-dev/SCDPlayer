# Loop Point Implementation Plan

## Current Status
🚨 **CRITICAL DISCOVERY**: OGG Vorbis SCD files store loop points in OGG comments, NOT SCD header!  
❌ **NOT WORKING**: Current implementation writes to SCD header (ignored by vgmstream for OGG)  
🔧 **NEEDS REWORK**: Must modify OGG comment tags within the compressed stream  
📚 **ANALYSIS COMPLETE**: vgmstream source code review reveals the real format structure  

## Primary Objectives

### 1. **SCD Loop Point Preservation** (CRITICAL REWORK NEEDED)
- ❌ ~~Save loop points directly to native SCD header locations~~ (Wrong for OGG!)
- 🔧 **NEW APPROACH**: For OGG Vorbis SCD files, modify OGG comment tags
- 🔧 **CODEC-SPECIFIC**: Different codecs store loop points differently:
  - **PCM/ADPCM**: SCD header locations (`meta_offset + 0x10/0x14`) ✅
  - **OGG Vorbis**: OGG comment tags inside compressed stream 🔧  
  - **MPEG**: SCD header (byte offsets) ✅

### 2. **Complete Workflow Support**
- **SCD → WAV**: Loop points are lost (expected behavior, WAV doesn't natively support game loop points)
- **WAV → SCD**: Should work via MusicEncoder.exe batch process (needs verification)
- **SCD → SCD**: Loop point editing and saving (PRIMARY FOCUS)

### 3. **User Interface**
- ✅ Precision loop editor with sample-accurate controls
- ✅ Progress indicators during save operations
- ✅ Visual feedback for loop point changes

## Technical Implementation

### SCD Format Structure (from vgmstream)
```c
// Stream header at meta_offset:
stream_size     = read_32bit(meta_offset+0x00,sf);
channels        = read_32bit(meta_offset+0x04,sf);
sample_rate     = read_32bit(meta_offset+0x08,sf);
codec           = read_32bit(meta_offset+0x0c,sf);
loop_start      = read_32bit(meta_offset+0x10,sf);  // ← WE WRITE HERE
loop_end        = read_32bit(meta_offset+0x14,sf);  // ← WE WRITE HERE
```

### Current Implementation Status

#### ✅ **Working Components:**
1. **SCD Header Parsing**: Correctly finds stream metadata location
2. **Endianness Handling**: Supports both big-endian and little-endian files
3. **Native Format Writing**: Writes to exact vgmstream locations
4. **Backup/Restore**: Safe operation with automatic rollback on errors
5. **Progress Indicators**: User sees progress during save operations

#### � **CRITICAL FINDINGS:**
1. **Codec-Specific Loop Storage**: ✅ **DISCOVERED**
   - **OGG Vorbis (codec 6)**: Loop points stored in OGG comment tags, SCD header ignored
   - **PCM (codec 0/1)**: Loop points in SCD header as byte offsets  
   - **ADPCM (codec 3)**: Loop points in SCD header as byte offsets
   - **MPEG (codec 7)**: Loop points in SCD header as byte offsets

2. **Current Implementation Problem**: ❌ **IDENTIFIED**
   - Writing to SCD header works for PCM/ADPCM/MPEG
   - Writing to SCD header does NOT work for OGG Vorbis (most common format)
   - vgmstream comment: "loop values are in bytes, let init_vgmstream_ogg_vorbis find loop comments instead"

#### 🔧 **Next Steps (PRIORITY REWORK):**
1. **Detect codec type** in SCD files
2. **Implement OGG comment modification** for codec 6 files  
3. **Keep SCD header modification** for other codecs
4. **Test with both format types** to ensure compatibility

## Workflow Analysis

### Primary Use Case: SCD Loop Editing
```
1. User loads SCD file
2. vgmstream reads native loop points (if any)
3. User adjusts loop points in precision editor
4. User saves loop points
5. Loop points written to native SCD locations
6. File remains playable in games/other tools
```

### Secondary Use Cases:

#### WAV Export/Import (Limited)
```
SCD → WAV: Loop points lost (WAV format limitation)
WAV → SCD: Use MusicEncoder.exe batch process (preserves audio quality)
```

#### Community Workflow (Advanced)
```
SCD → WAV (with custom metadata): Export for editing
WAV → SCD (via batch): Import back to SCD format
```

## Testing Checklist

### ✅ **Completed Tests:**
- [x] SCD file header parsing
- [x] Loop point writing to native locations
- [x] Backup/restore functionality
- [x] Progress indicator display

### 🔧 **Tests Needed:**
- [ ] Verify saved loop points match user input exactly
- [ ] Test with various SCD file types (different games, encodings)
- [ ] Confirm compatibility with other SCD tools
- [ ] Test complete save/load cycle accuracy

### 📋 **Validation Steps:**
1. Load SCD file with known loop points
2. Verify vgmstream reads them correctly
3. Modify loop points in editor
4. Save to SCD format
5. Reload file and verify loop points match exactly
6. Test file in external tools (games, other players)

## Known Issues & Solutions

### Issue 1: Value Discrepancy
**Problem**: Saved values don't match applied values  
**Investigation Needed**: 
- Check if coordinate systems differ between UI and file format
- Verify sample rate consistency
- Ensure no unit conversion errors (samples vs. bytes vs. time)

### Issue 2: MusicEncoder.exe Workflow
**Problem**: Complex batch process for WAV↔SCD conversion  
**Status**: Working but needs verification for loop preservation  
**Alternative**: Focus on native SCD editing (primary use case)

## Success Criteria

### Minimum Viable Product (MVP):
1. ✅ Load SCD file and read existing loop points
2. ✅ Edit loop points with precision controls
3. ✅ Save loop points to native SCD format
4. 🔧 **Verify saved points match user input exactly**
5. 🔧 **Confirm external tool compatibility**

### Extended Goals:
- Support for all SCD variants (different games)
- Batch processing capabilities
- Advanced loop point validation
- Integration with community workflows

## Next Steps

### Immediate Priority:
1. **Debug value discrepancy** - investigate why saved ≠ applied values
2. **Verification testing** - load/save/reload cycle accuracy
3. **External tool testing** - confirm other tools can read our loop points

### Medium Priority:
1. Comprehensive SCD format testing
2. MusicEncoder.exe workflow verification
3. Community workflow integration

### Long Term:
1. Support for additional audio formats
2. Advanced loop point features
3. Batch processing capabilities

---

## Development Notes

### File Corruption Prevention ✅
- **Previous Issue**: MusicEncoder.exe was re-encoding audio, causing file size changes
- **Solution**: Direct header manipulation preserves original audio data perfectly
- **Result**: Files maintain exact same audio quality and playback characteristics

### vgmstream Integration ✅
- **Benefit**: Uses industry-standard format specification
- **Compatibility**: Ensures other tools can read our loop points
- **Reliability**: Leverages well-tested format parsing code

### User Experience ✅
- **Progress Indicators**: User sees save progress, no apparent hanging
- **Error Handling**: Automatic backup/restore on failures
- **Precision Controls**: Sample-accurate loop point editing
