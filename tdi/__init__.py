"""Paquete tdi: Huffman dinámico (FGK) + contenedor .tdi. Solo stdlib."""

from .codec import compress, decompress  # noqa: F401
from .format import TDIError  # noqa: F401

__version__ = "1.0.0"
