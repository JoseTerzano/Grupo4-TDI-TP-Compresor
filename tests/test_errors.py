"""Detección de errores: excepciones propias y exit codes de los CLIs."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tdi import compress, decompress  # noqa: E402
from tdi.format import (HEADER_SIZE, BitstreamExhaustedError, ChecksumError,  # noqa: E402
                        CorruptDataError, InvalidMagicError, TDIError,
                        TruncatedHeaderError, UnsupportedAlgorithmError,
                        UnsupportedVersionError)

SAMPLE = (ROOT / "tests" / "corpus" / "prueba_2_texto_natural.txt").read_bytes()[:4000]
BLOB = compress(SAMPLE).blob


def mutate(blob: bytes, idx: int, value: int) -> bytes:
    b = bytearray(blob)
    b[idx] = value
    return bytes(b)


class TestFormatErrors(unittest.TestCase):
    def test_bad_magic(self):
        with self.assertRaises(InvalidMagicError):
            decompress(b"ZIP1" + BLOB[4:])
        with self.assertRaises(InvalidMagicError):
            decompress(b"hola")

    def test_bad_version(self):
        with self.assertRaises(UnsupportedVersionError):
            decompress(mutate(BLOB, 4, 9))

    def test_unsupported_algo(self):
        for algo in (0, 2, 200):
            with self.assertRaises(UnsupportedAlgorithmError):
                decompress(mutate(BLOB, 5, algo))

    def test_bad_flags(self):
        with self.assertRaises(UnsupportedVersionError):
            decompress(mutate(BLOB, 6, 1))

    def test_truncated_header(self):
        for n in (0, 2, 4, 10, HEADER_SIZE - 1):
            with self.assertRaises(TruncatedHeaderError, msg=n):
                decompress(BLOB[:n])

    def test_bad_last_bits(self):
        with self.assertRaises(CorruptDataError):
            decompress(mutate(BLOB, 19, 0))
        with self.assertRaises(CorruptDataError):
            decompress(mutate(BLOB, 19, 9))

    def test_truncated_payload(self):
        for cut in (HEADER_SIZE, HEADER_SIZE + 1, len(BLOB) // 2, len(BLOB) - 1):
            with self.assertRaises(CorruptDataError, msg=cut):
                decompress(BLOB[:cut])

    def test_payload_exhausted(self):
        # tamaño declarado mayor que lo codificado
        import struct
        b = bytearray(BLOB)
        struct.pack_into("<Q", b, 7, len(SAMPLE) + 50)
        with self.assertRaises(BitstreamExhaustedError):
            decompress(bytes(b))

    def test_trailing_data(self):
        with self.assertRaises(CorruptDataError):
            decompress(BLOB + b"\x00")

    def test_flipped_payload_bytes(self):
        """Cualquier byte del payload alterado se detecta (CRC o bitstream)."""
        positions = range(HEADER_SIZE, len(BLOB), max(1, (len(BLOB) - HEADER_SIZE) // 150))
        for i in positions:
            for mask in (0x01, 0x80, 0xFF):
                bad = mutate(BLOB, i, BLOB[i] ^ mask)
                with self.assertRaises(TDIError, msg=(i, mask)):
                    decompress(bad)

    def test_crc_mismatch(self):
        with self.assertRaises(ChecksumError):
            decompress(mutate(BLOB, 15, BLOB[15] ^ 0xFF))


class TestCLIErrors(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, *args], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8")

    def test_missing_file(self):
        for script in ("compressor.py", "decompressor.py"):
            r = self.run_cli(script, "no_existe_12345.txt", os.devnull)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("inexistente", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_corrupt_file_cli(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.tdi"
            bad.write_bytes(mutate(BLOB, 0, ord("X")))
            r = self.run_cli("decompressor.py", str(bad), str(Path(d) / "o.txt"))
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("Traceback", r.stderr)
            bad.write_bytes(BLOB[: len(BLOB) // 2])
            r = self.run_cli("decompressor.py", str(bad), str(Path(d) / "o.txt"))
            self.assertEqual(r.returncode, 4)
            self.assertNotIn("Traceback", r.stderr)

    def test_cli_roundtrip_verify(self):
        src = ROOT / "tests" / "corpus" / "prueba_1_pequena.txt"
        with tempfile.TemporaryDirectory() as d:
            tdi, rec = Path(d) / "a.tdi", Path(d) / "a.txt"
            self.assertEqual(self.run_cli("compressor.py", str(src), str(tdi)).returncode, 0)
            r = self.run_cli("decompressor.py", str(tdi), str(rec), "--verify", str(src))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("INTEGRIDAD", r.stdout)
            self.assertIn("OK", r.stdout)
            # verificar contra otro archivo -> FAIL, exit 6
            other = Path(d) / "otro.txt"
            other.write_bytes(b"distinto")
            r = self.run_cli("decompressor.py", str(tdi), str(rec), "--verify", str(other))
            self.assertEqual(r.returncode, 6)


if __name__ == "__main__":
    unittest.main()
