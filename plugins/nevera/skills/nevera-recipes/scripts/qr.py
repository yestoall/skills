#!/usr/bin/env python3
"""A QR code for the link Nevera opens, as an image and as text.

Byte mode, error correction level M and versions 1 to 10, up to 213 bytes: the
link is about 110. It follows ISO/IEC 18004, and its tests compare it with another
encoder.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import struct
import zlib
from typing import Dict, List, NamedTuple, Optional

Matrix = List[List[bool]]

LEVEL_M = 0b00
QUIET_ZONE = 4  # modules, what the standard asks for
HALF_BLOCKS = {
    (True, True): "█",
    (True, False): "▀",
    (False, True): "▄",
    (False, False): " ",
}
PIXELS_PER_MODULE = 10
FORMAT_GENERATOR = 0x537
FORMAT_XOR = 0x5412
VERSION_GENERATOR = 0x1F25
WHITE = bytes([255])
BLACK = bytes([0])



class Group(NamedTuple):
    blocks: int
    data_codewords: int


class Layout(NamedTuple):
    correction_per_block: int
    first: Group
    second: Group = Group(0, 0)


LAYOUTS: Dict[int, Layout] = {
    1: Layout(10, Group(1, 16)),
    2: Layout(16, Group(1, 28)),
    3: Layout(26, Group(1, 44)),
    4: Layout(18, Group(2, 32)),
    5: Layout(24, Group(2, 43)),
    6: Layout(16, Group(4, 27)),
    7: Layout(18, Group(4, 31)),
    8: Layout(22, Group(2, 38), Group(2, 39)),
    9: Layout(22, Group(3, 36), Group(2, 37)),
    10: Layout(26, Group(4, 43), Group(1, 44)),
}

ALIGNMENT: Dict[int, List[int]] = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}

MASKS = (
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (y // 2 + x // 3) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


class QrTooLong(ValueError):
    """More bytes than fit in the largest version here."""


def block_sizes(version: int) -> List[int]:
    _, first, second = LAYOUTS[version]
    return [first.data_codewords] * first.blocks + [
        second.data_codewords
    ] * second.blocks


def data_codewords(version: int) -> int:
    return sum(block_sizes(version))


def count_bits(version: int) -> int:
    return 8 if version < 10 else 16


def smallest_version(length: int) -> int:
    for version in LAYOUTS:
        if 4 + count_bits(version) + 8 * length <= 8 * data_codewords(version):
            return version
    raise QrTooLong(f"{length} bytes don't fit in a QR code here")


def encode_data(data: bytes, version: int) -> List[int]:
    """The data codewords: mode, length, the bytes, terminator and padding."""
    bits = (0b0100 << count_bits(version)) | len(data)
    width = 4 + count_bits(version)
    for byte in data:
        bits = (bits << 8) | byte
        width += 8
    capacity = 8 * data_codewords(version)
    terminator = min(4, capacity - width)
    bits <<= terminator
    width += terminator
    bits <<= -width % 8
    width += -width % 8
    words = list(bits.to_bytes(width // 8, "big"))
    padding = data_codewords(version) - len(words)
    return words + [(0xEC, 0x11)[i % 2] for i in range(padding)]


# Arithmetic in GF(256), with the polynomial of the standard
EXP = [0] * 512
LOG = [0] * 256
_value = 1
for _power in range(255):
    EXP[_power] = _value
    LOG[_value] = _power
    _value <<= 1
    if _value & 0x100:
        _value ^= 0x11D
for _power in range(255, 512):
    EXP[_power] = EXP[_power - 255]


def multiply(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def error_correction(data: List[int], length: int) -> List[int]:
    """Reed-Solomon: the remainder of dividing the data by the generator."""
    generator = [1]
    for power in range(length):
        next_generator = [0] * (len(generator) + 1)
        for i, coefficient in enumerate(generator):
            next_generator[i] ^= coefficient
            next_generator[i + 1] ^= multiply(coefficient, EXP[power])
        generator = next_generator
    remainder = list(data) + [0] * length
    for i in range(len(data)):
        factor = remainder[i]
        if factor:
            for j, coefficient in enumerate(generator):
                remainder[i + j] ^= multiply(coefficient, factor)
    return remainder[len(data) :]


def interleave(words: List[int], version: int) -> List[int]:
    """Splits the data into blocks, adds their error correction, and takes one
    codeword of each block in turn."""
    length = LAYOUTS[version].correction_per_block
    sizes = block_sizes(version)
    blocks, at = [], 0
    for size in sizes:
        blocks.append(words[at : at + size])
        at += size
    corrections = [error_correction(block, length) for block in blocks]
    result = []
    for i in range(max(sizes)):
        result += [block[i] for block in blocks if i < len(block)]
    for i in range(length):
        result += [correction[i] for correction in corrections]
    return result


def bch(value: int, generator: int, degree: int) -> int:
    """value, followed by the remainder of dividing it by the generator."""
    remainder = value << degree
    top = generator.bit_length() - 1
    while remainder.bit_length() > top:
        remainder ^= generator << (remainder.bit_length() - 1 - top)
    return (value << degree) | remainder


def format_bits(mask: int) -> int:
    return bch((LEVEL_M << 3) | mask, FORMAT_GENERATOR, 10) ^ FORMAT_XOR


def version_bits(version: int) -> int:
    return bch(version, VERSION_GENERATOR, 12)


class Grid:
    """The modules, and which of them are not for data."""

    def __init__(self, version: int) -> None:
        self.version = version
        self.size = 17 + 4 * version
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.reserved = [[False] * self.size for _ in range(self.size)]
        self.draw_function_patterns()

    def set(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self.reserved[y][x] = True

    def draw_finder(self, left: int, top: int) -> None:
        for y in range(-1, 8):
            for x in range(-1, 8):
                if 0 <= left + x < self.size and 0 <= top + y < self.size:
                    ring = max(abs(x - 3), abs(y - 3))
                    self.set(left + x, top + y, ring != 2 and ring != 4)

    def draw_function_patterns(self) -> None:
        last = self.size - 7
        for left, top in ((0, 0), (last, 0), (0, last)):
            self.draw_finder(left, top)
        for i in range(8, self.size - 8):
            self.set(i, 6, i % 2 == 0)
            self.set(6, i, i % 2 == 0)
        centres = ALIGNMENT[self.version]
        for cy in centres:
            for cx in centres:
                # Not over the finders. Over the timing lines, yes: they match
                if (cx, cy) in ((6, 6), (centres[-1], 6), (6, centres[-1])):
                    continue
                for y in range(-2, 3):
                    for x in range(-2, 3):
                        self.set(cx + x, cy + y, max(abs(x), abs(y)) != 1)
        self.set(8, self.size - 8, True)  # The dark module
        self.draw_format(0)
        self.draw_version()

    def draw_format(self, mask: int) -> None:
        bits = format_bits(mask)
        bit = [bool((bits >> i) & 1) for i in range(15)]
        for i in range(6):
            self.set(8, i, bit[i])
        self.set(8, 7, bit[6])
        self.set(8, 8, bit[7])
        self.set(7, 8, bit[8])
        for i in range(9, 15):
            self.set(14 - i, 8, bit[i])
        for i in range(8):
            self.set(self.size - 1 - i, 8, bit[i])
        for i in range(8, 15):
            self.set(8, self.size - 15 + i, bit[i])

    def draw_version(self) -> None:
        if self.version < 7:
            return
        bits = version_bits(self.version)
        for i in range(18):
            dark = bool((bits >> i) & 1)
            far, near = self.size - 11 + i % 3, i // 3
            self.set(far, near, dark)
            self.set(near, far, dark)

    def draw_data(self, codewords: List[int]) -> None:
        bits = [(word >> (7 - i)) & 1 for word in codewords for i in range(8)]
        at = 0
        right = self.size - 1
        upward = True
        while right > 0:
            if right == 6:
                right = 5  # The timing column has no data
            rows = range(self.size - 1, -1, -1) if upward else range(self.size)
            for y in rows:
                for x in (right, right - 1):
                    if not self.reserved[y][x] and at < len(bits):
                        self.modules[y][x] = bool(bits[at])
                        at += 1
            upward = not upward
            right -= 2

    def masked(self, mask: int) -> Matrix:
        """A copy with the mask on the data and its format information drawn."""
        rule = MASKS[mask]
        result = Grid(self.version)
        result.modules = [
            [
                module != (not self.reserved[y][x] and rule(x, y))
                for x, module in enumerate(row)
            ]
            for y, row in enumerate(self.modules)
        ]
        result.draw_format(mask)
        return result.modules


def runs_penalty(line: List[bool]) -> int:
    """Rule 1: five or more equal modules in a row."""
    penalty, length, previous = 0, 0, None
    for module in line:
        if module == previous:
            length += 1
        else:
            if length >= 5:
                penalty += length - 2
            previous, length = module, 1
    return penalty + (length - 2 if length >= 5 else 0)


def finder_like_penalty(line: List[bool]) -> int:
    """Rule 3: what looks like a finder, with four light modules to one side."""
    one_side = [True, False, True, True, True, False, True, False, False, False, False]
    other_side = one_side[::-1]
    return 40 * sum(
        line[i : i + 11] in (one_side, other_side) for i in range(len(line) - 10)
    )


def balance_penalty(dark: int, total: int) -> int:
    """Rule 4: 10 points for each 5% away from half dark, from the multiple of 5
    closest to half."""
    below = dark * 100 // total // 5 * 5
    return 2 * min(abs(below - 50), abs(below + 5 - 50))


def penalty(matrix: Matrix) -> int:
    size = len(matrix)
    columns = [[matrix[y][x] for y in range(size)] for x in range(size)]
    lines = matrix + columns
    total = sum(runs_penalty(line) for line in lines)
    total += sum(finder_like_penalty(line) for line in lines)
    for y in range(size - 1):  # Rule 2: squares of one colour
        for x in range(size - 1):
            if (
                matrix[y][x]
                == matrix[y][x + 1]
                == matrix[y + 1][x]
                == matrix[y + 1][x + 1]
            ):
                total += 3
    return total + balance_penalty(sum(map(sum, matrix)), size * size)


def qr_matrix(text: str, mask: Optional[int] = None) -> Matrix:
    """The modules of the QR code, row by row: True is dark. Without a mask, the
    one the standard's penalty rules prefer."""
    data = text.encode("utf-8")
    version = smallest_version(len(data))
    grid = Grid(version)
    grid.draw_data(interleave(encode_data(data, version), version))
    if mask is not None:
        return grid.masked(mask)
    return min((grid.masked(each) for each in range(len(MASKS))), key=penalty)


def text_art(matrix: Matrix, border: int = QUIET_ZONE) -> str:
    """The code in half blocks, two modules per character, to print in a terminal.
    Painted is light, so it only scans on a dark background. The quiet zone is
    painted too: no line ends in spaces that something could trim."""
    side = len(matrix)

    def light(y: int, x: int) -> bool:
        return not (0 <= y < side and 0 <= x < side and matrix[y][x])

    return "\n".join(
        "".join(
            HALF_BLOCKS[light(y, x), light(y + 1, x)]
            for x in range(-border, side + border)
        )
        for y in range(-border, side + border, 2)
    )


def png_chunk(kind: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body))
    )


def png_bytes(
    matrix: Matrix, scale: int = PIXELS_PER_MODULE, border: int = QUIET_ZONE
) -> bytes:
    """The image: black on white, in 8-bit greyscale, with its quiet zone."""
    side = (len(matrix) + 2 * border) * scale
    blank = WHITE * side
    rows = [blank] * (border * scale)
    edge = WHITE * (border * scale)
    for row in matrix:
        modules = b"".join((BLACK if dark else WHITE) * scale for dark in row)
        rows += [edge + modules + edge] * scale
    rows += [blank] * (border * scale)
    raw = b"".join(b"\x00" + row for row in rows)
    header = struct.pack(">IIBBBBB", side, side, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )
