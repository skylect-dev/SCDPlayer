"""Helpers for reading/writing KH2 SCD (OGG) loop points.

KH2's SCD sound entry header stores loop start/end as byte offsets
(relative to the sound entry start), not as sample indices.

To align the tool with in-game looping, we map between sample indices and
byte offsets by parsing embedded Ogg pages and their granule positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class ScdSoundEntryHeader:
    offset: int
    length_bytes: int
    channels: int
    sample_rate: int
    codec: int
    loop_start_bytes: int
    loop_end_bytes: int


@dataclass(frozen=True)
class OggPage:
    offset: int  # absolute file offset
    granule_pos: int  # samples at end of page


@dataclass(frozen=True)
class OggPageSpan:
    offset: int
    start_sample: int
    end_sample: int


def _u32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little", signed=False)


def _read_first_sound_entry_offset(data: bytes) -> Optional[int]:
    if len(data) < 0x50:
        return None

    # Offsets header begins at 0x30. At 0x3C is the Sound Entry Offset Table Offset.
    sound_entry_table_off = _u32(data, 0x3C)
    if sound_entry_table_off <= 0 or sound_entry_table_off + 4 > len(data):
        return None

    sound_entry_off = _u32(data, sound_entry_table_off)
    if sound_entry_off <= 0 or sound_entry_off + 0x20 > len(data):
        return None

    return sound_entry_off


def read_sound_entry_header(path: str | Path) -> Optional[ScdSoundEntryHeader]:
    p = Path(path)
    data = p.read_bytes()
    entry_off = _read_first_sound_entry_offset(data)
    if entry_off is None:
        return None

    length_bytes = _u32(data, entry_off + 0x00)
    channels = _u32(data, entry_off + 0x04)
    sample_rate = _u32(data, entry_off + 0x08)
    codec = _u32(data, entry_off + 0x0C)
    loop_start_bytes = _u32(data, entry_off + 0x10)
    loop_end_bytes = _u32(data, entry_off + 0x14)

    return ScdSoundEntryHeader(
        offset=entry_off,
        length_bytes=length_bytes,
        channels=channels,
        sample_rate=sample_rate,
        codec=codec,
        loop_start_bytes=loop_start_bytes,
        loop_end_bytes=loop_end_bytes,
    )


def _find_ogg_start(data: bytes, start: int, end: int) -> Optional[int]:
    idx = data.find(b"OggS", start, end)
    return idx if idx >= 0 else None


def iter_ogg_pages(data: bytes, ogg_start: int, ogg_end: Optional[int] = None) -> Iterable[OggPage]:
    """Iterate pages from an embedded Ogg bitstream.

    This is a minimal Ogg parser: enough to map file offsets to granule positions.
    """
    pos = ogg_start
    limit = ogg_end if ogg_end is not None else len(data)

    while pos + 27 <= limit:
        if data[pos : pos + 4] != b"OggS":
            break

        # https://xiph.org/ogg/doc/framing.html
        page_segments = data[pos + 26]
        header_size = 27 + page_segments
        if pos + header_size > limit:
            break

        seg_table = data[pos + 27 : pos + 27 + page_segments]
        body_size = sum(seg_table)
        page_size = header_size + body_size
        if page_size <= 0 or pos + page_size > limit:
            break

        granule_pos = int.from_bytes(data[pos + 6 : pos + 14], "little", signed=False)
        yield OggPage(offset=pos, granule_pos=granule_pos)

        pos += page_size


def _build_ogg_index(data: bytes, entry_off: int, length_bytes: int) -> list[OggPage]:
    entry_end = min(len(data), entry_off + max(0, length_bytes))
    ogg_start = _find_ogg_start(data, entry_off, entry_end)
    if ogg_start is None:
        return []

    pages = list(iter_ogg_pages(data, ogg_start, ogg_end=entry_end))
    # Filter out pages with granule_pos==0 (headers) but keep ordering
    return pages


def _build_ogg_spans(pages: list[OggPage]) -> list[OggPageSpan]:
    spans: list[OggPageSpan] = []
    prev_end = 0
    for page in pages:
        end = int(page.granule_pos or 0)
        start = int(prev_end)
        if end < start:
            # Defensive: malformed or non-monotonic granules
            end = start
        spans.append(OggPageSpan(offset=int(page.offset), start_sample=start, end_sample=end))
        prev_end = end
    return spans


def loop_bytes_to_samples(path: str | Path, loop_bytes: int) -> Optional[int]:
    """Convert an SCD loop byte offset to a sample index.

    We choose the first Ogg page at/after the loop byte offset and return
    that page's granule position.
    """
    p = Path(path)
    data = p.read_bytes()
    entry_off = _read_first_sound_entry_offset(data)
    if entry_off is None:
        return None

    length_bytes = _u32(data, entry_off + 0x00)
    pages = _build_ogg_index(data, entry_off, length_bytes)
    if not pages:
        return None

    spans = _build_ogg_spans(pages)
    target_abs = entry_off + max(0, int(loop_bytes))

    # The loop offsets in KH2 SCD behave like byte boundaries into the Ogg stream.
    # To map to samples, use the start sample of the first page at/after the target.
    for idx, span in enumerate(spans):
        if span.offset >= target_abs:
            return int(span.start_sample)

    # If target is after the last page start, use total samples (end of last page).
    if spans:
        return int(spans[-1].end_sample)
    return None


def samples_to_loop_bytes(path: str | Path, target_samples: int) -> Optional[int]:
    """Convert a desired sample index into a loop byte offset (relative to sound entry)."""
    p = Path(path)
    data = p.read_bytes()
    entry_off = _read_first_sound_entry_offset(data)
    if entry_off is None:
        return None

    length_bytes = _u32(data, entry_off + 0x00)
    pages = _build_ogg_index(data, entry_off, length_bytes)
    if not pages:
        return None

    spans = _build_ogg_spans(pages)
    desired = max(0, int(target_samples))

    # Pick the page whose start_sample is closest to desired.
    best: Optional[OggPageSpan] = None
    best_diff: Optional[int] = None
    for span in spans:
        diff = abs(int(span.start_sample) - desired)
        if best is None or diff < (best_diff if best_diff is not None else 1 << 60):
            best = span
            best_diff = diff

    if best is None:
        return None

    loop_bytes = int(best.offset) - entry_off
    if loop_bytes < 0:
        return None

    # Clamp into entry length
    loop_bytes = max(0, min(loop_bytes, max(0, length_bytes)))
    return int(loop_bytes)


def patch_scd_loop_from_samples(path: str | Path, loop_start_samples: int, loop_end_samples: int) -> bool:
    """Patch SCD loop points (OGG) from sample indices.

    This writes header loop offsets in bytes using an Ogg page index.
    """
    p = Path(path)
    data = bytearray(p.read_bytes())
    entry_off = _read_first_sound_entry_offset(data)
    if entry_off is None:
        return False

    length_bytes = _u32(data, entry_off + 0x00)

    start_bytes = samples_to_loop_bytes(p, loop_start_samples)
    end_bytes = samples_to_loop_bytes(p, loop_end_samples)

    if start_bytes is None or end_bytes is None:
        return False

    # Ensure ordering and sane bounds
    start_bytes = max(0, min(start_bytes, max(0, length_bytes)))
    end_bytes = max(start_bytes + 1, min(end_bytes, max(0, length_bytes)))

    data[entry_off + 0x10 : entry_off + 0x14] = int(start_bytes).to_bytes(4, "little", signed=False)
    data[entry_off + 0x14 : entry_off + 0x18] = int(end_bytes).to_bytes(4, "little", signed=False)
    p.write_bytes(data)
    return True
