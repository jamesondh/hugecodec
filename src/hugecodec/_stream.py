"""Byte-stream helper mirroring FreePascal's TStream semantics.

Little-endian throughout (Pascal on x86/ARM). String encoding is latin-1 so
that we can round-trip arbitrary bytes without loss — most tracker files use
ASCII names but we don't want to crash on stray high bytes.
"""

from __future__ import annotations

import struct


class ByteReader:
    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    # ----- primitives ------------------------------------------------------

    def read(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.data):
            raise EOFError(
                f"tried to read {n} bytes at offset {self.pos:#x}, "
                f"file is only {len(self.data)} bytes"
            )
        chunk = self.data[self.pos:end]
        self.pos = end
        return chunk

    def read_int32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_uint32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def read_byte(self) -> int:
        return self.read(1)[0]

    def read_bool(self) -> bool:
        return self.read(1)[0] != 0

    # ----- Pascal-flavored -------------------------------------------------

    def read_enum(self) -> int:
        """FreePascal $MINENUMSIZE 4 default: enums are 32-bit signed ints in
        packed records. We return the raw int; the caller narrows to whatever
        enum semantics apply."""
        return self.read_int32()

    def read_short_string(self) -> str:
        """Pascal ShortString[255]: 1 length byte + 255 data bytes fixed.
        Bytes past `length` are undefined garbage on the disk; we drop them.
        """
        raw = self.read(256)
        length = raw[0]
        return raw[1:1 + length].decode("latin-1", errors="replace")

    def read_ansi_string(self) -> str:
        """FreePascal TStream.ReadAnsiString: 4-byte length prefix + N bytes.
        Length -1 is a Pascal convention meaning 'nil'; treat as empty."""
        length = self.read_int32()
        if length <= 0:
            return ""
        return self.read(length).decode("latin-1", errors="replace")

    # ----- introspection ---------------------------------------------------

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def eof(self) -> bool:
        return self.pos >= len(self.data)

    def peek(self, n: int) -> bytes:
        return self.data[self.pos:self.pos + n]
