"""Compresión/descompresión de contenedor .tdi completo (cabecera + payload)."""

from __future__ import annotations

import binascii
from typing import NamedTuple

from . import adaptive_huffman as ah
from .format import (ALGO_FGK, ChecksumError, CorruptDataError, Header, pack_header,
                     parse_container, payload_bit_length)


class CompressResult(NamedTuple):
    blob: bytes
    enc: ah.EncodeResult


def compress(data: bytes, trace=None, check: bool = False) -> CompressResult:
    enc = ah.encode(data, trace=trace, check=check)
    header = pack_header(ALGO_FGK, len(data), binascii.crc32(data), enc.last_bits)
    return CompressResult(header + enc.payload, enc)


def decompress(blob: bytes, trace=None, check: bool = False) -> tuple[bytes, Header]:
    header, payload = parse_container(blob)
    nbits = payload_bit_length(payload, header.last_bits)
    if payload and (payload[-1] & ((1 << (8 - header.last_bits)) - 1)):
        raise CorruptDataError("bits de relleno del último byte no nulos")
    data = ah.decode(payload, header.original_size, nbits, trace=trace, check=check)
    crc = binascii.crc32(data)
    if crc != header.crc32:
        raise ChecksumError(
            f"CRC32 no coincide: cabecera {header.crc32:08x}, calculado {crc:08x}")
    return data, header
