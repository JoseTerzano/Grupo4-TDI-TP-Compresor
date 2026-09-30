"""Formato de contenedor .tdi: constantes, cabecera, validaciones y excepciones.

Cabecera fija de 20 bytes, little-endian (struct "<4sBBBQIB"):

    off  tam  campo
    0    4    magic            b"TDI1"
    4    1    versión          1
    5    1    id algoritmo     1 = FGK, 2 = Vitter (reservado)
    6    1    flags            0 (reservado)
    7    8    tamaño original  uint64
    15   4    CRC32 original   uint32 (binascii.crc32)
    19   1    bits válidos del último byte del payload (1..8; 0 si vacío)
    20   ...  payload          bitstream MSB-first
"""

from __future__ import annotations

import struct
from typing import NamedTuple

MAGIC = b"TDI1"
VERSION = 1
ALGO_FGK = 1
ALGO_VITTER = 2
ALGO_NAMES = {ALGO_FGK: "FGK (Huffman dinámico)", ALGO_VITTER: "Vitter (Λ)"}
SUPPORTED_ALGOS = {ALGO_FGK}

_HEADER = struct.Struct("<4sBBBQIB")
HEADER_SIZE = _HEADER.size
assert HEADER_SIZE == 20


# ---------------------------------------------------------------- excepciones
class TDIError(Exception):
    """Error base del formato/códec. `exit_code` se usa en los CLIs."""
    exit_code = 1


class InputFileError(TDIError):
    exit_code = 2


class InvalidMagicError(TDIError):
    exit_code = 3


class UnsupportedVersionError(TDIError):
    exit_code = 3


class UnsupportedAlgorithmError(TDIError):
    exit_code = 3


class TruncatedHeaderError(TDIError):
    exit_code = 3


class CorruptDataError(TDIError):
    exit_code = 4


class BitstreamExhaustedError(CorruptDataError):
    exit_code = 4


class ChecksumError(TDIError):
    exit_code = 5


# ------------------------------------------------------------------- cabecera
class Header(NamedTuple):
    version: int
    algo: int
    flags: int
    original_size: int
    crc32: int
    last_bits: int


def pack_header(algo: int, original_size: int, crc32: int, last_bits: int) -> bytes:
    return _HEADER.pack(MAGIC, VERSION, algo, 0, original_size,
                        crc32 & 0xFFFFFFFF, last_bits)


def parse_container(blob: bytes) -> tuple[Header, bytes]:
    """Valida cabecera y devuelve (Header, payload)."""
    if len(blob) < 4 and MAGIC.startswith(blob):
        raise TruncatedHeaderError(
            f"cabecera truncada: {len(blob)} B < {HEADER_SIZE} B")
    if blob[:4] != MAGIC:
        raise InvalidMagicError(
            f"magic inválido {blob[:4]!r}: no es un archivo .tdi")
    if len(blob) < HEADER_SIZE:
        raise TruncatedHeaderError(
            f"cabecera truncada: {len(blob)} B < {HEADER_SIZE} B")
    _, ver, algo, flags, size, crc, last = _HEADER.unpack_from(blob)
    if ver != VERSION:
        raise UnsupportedVersionError(f"versión {ver} no soportada (esperada {VERSION})")
    if algo not in SUPPORTED_ALGOS:
        name = ALGO_NAMES.get(algo, "desconocido")
        raise UnsupportedAlgorithmError(f"algoritmo id={algo} ({name}) no soportado")
    if flags != 0:
        raise UnsupportedVersionError(f"flags=0x{flags:02x} no soportados")
    payload = blob[HEADER_SIZE:]
    if not payload:
        if last != 0:
            raise CorruptDataError("payload vacío pero bits_último_byte != 0")
        if size != 0:
            raise BitstreamExhaustedError(
                f"payload vacío: faltan datos para reconstruir {size} B")
    elif not 1 <= last <= 8:
        raise CorruptDataError(f"bits_último_byte={last} fuera de rango 1..8")
    return Header(ver, algo, flags, size, crc, last), payload


def payload_bit_length(payload: bytes, last_bits: int) -> int:
    if not payload:
        return 0
    return (len(payload) - 1) * 8 + last_bits
