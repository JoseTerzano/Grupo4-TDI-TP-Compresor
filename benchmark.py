#!/usr/bin/env python3
"""Benchmark: Huffman dinámico propio vs Brotli q5 (externo) vs gzip -n -6 (baseline).

- Las tres soluciones se miden por subprocess con time.perf_counter_ns()
  (todas pagan el arranque de proceso).
- 1 warm-up descartado + N repeticiones (default 5); se reporta la mediana.
- SHA-256 del round-trip verificado en cada repetición.
- Weissman: W = (R/Rref)·(ln Tref / ln T), T en ms, α=1, ref = gzip-6.
  Global sobre pruebas 2-4: Rglobal = ΣSo/ΣSc, Tglobal = mediana (sobre
  repeticiones) del tiempo total de compresión del corpus.

Uso: python benchmark.py [--reps 5] [--corpus tests/corpus] [--out results]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tdi import adaptive_huffman as ah  # noqa: E402
from tdi.format import HEADER_SIZE  # noqa: E402

FILES = ["prueba_1_pequena.txt", "prueba_2_texto_natural.txt",
         "prueba_3_alta_repeticion.txt", "prueba_4_baja_repeticion.txt"]
RANKED = FILES[1:]                     # prueba 1 fuera del ranking temporal
GZIP_OVERHEAD = 18                     # 10 B cabecera (-n) + 8 B trailer CRC/ISIZE
MB = 1_000_000


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def entropy0(data: bytes) -> float:
    n = len(data)
    if not n:
        return 0.0
    return -sum(c / n * math.log2(c / n) for c in Counter(data).values())


# ----------------------------------------------------------------- soluciones
class Solution:
    name = ""
    ext = ""
    header_bytes: int | None = None

    def compress_cmd(self, src: str, dst: str) -> tuple[list[str], str | None]:
        raise NotImplementedError

    def decompress_cmd(self, src: str, dst: str) -> tuple[list[str], str | None]:
        raise NotImplementedError

    def version(self) -> str:
        return ""


def _run(cmd: list[str], stdout_path: str | None) -> int:
    """Ejecuta y devuelve ns transcurridos. Falla ruidosamente si rc != 0."""
    if stdout_path:
        with open(stdout_path, "wb") as f:
            t0 = time.perf_counter_ns()
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
            dt = time.perf_counter_ns() - t0
    else:
        t0 = time.perf_counter_ns()
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        dt = time.perf_counter_ns() - t0
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} -> rc={r.returncode}: "
                           f"{r.stderr.decode(errors='replace').strip()}")
    return dt


class Own(Solution):
    name = "Propia: Huffman dinámico FGK"
    ext = ".tdi"
    header_bytes = HEADER_SIZE

    def compress_cmd(self, src, dst):
        return [sys.executable, str(ROOT / "compressor.py"), src, dst, "--quiet"], None

    def decompress_cmd(self, src, dst):
        return [sys.executable, str(ROOT / "decompressor.py"), src, dst, "--quiet"], None

    def version(self):
        return f"Python {platform.python_version()} (implementación propia, solo stdlib)"


class BrotliCLI(Solution):
    name = "Externa: Brotli q5"
    ext = ".br"

    def __init__(self, exe: str):
        self.exe = exe

    def compress_cmd(self, src, dst):
        return [self.exe, "-q", "5", "-k", "-f", "-o", dst, src], None

    def decompress_cmd(self, src, dst):
        return [self.exe, "-d", "-k", "-f", "-o", dst, src], None

    def version(self):
        r = subprocess.run([self.exe, "--version"], capture_output=True, text=True)
        return (r.stdout or r.stderr).strip() + " (CLI oficial, ventana por defecto lgwin=22)"


class BrotliPy(Solution):
    """Fallback: paquete `brotli` de PyPI (mismo encoder de Google, quality=5)."""
    name = "Externa: Brotli q5 (PyPI fallback)"
    ext = ".br"
    _C = ("import sys,brotli;d=open(sys.argv[1],'rb').read();"
          "open(sys.argv[2],'wb').write(brotli.compress(d,quality=5))")
    _D = ("import sys,brotli;d=open(sys.argv[1],'rb').read();"
          "open(sys.argv[2],'wb').write(brotli.decompress(d))")

    def compress_cmd(self, src, dst):
        return [sys.executable, "-c", self._C, src, dst], None

    def decompress_cmd(self, src, dst):
        return [sys.executable, "-c", self._D, src, dst], None

    def version(self):
        import brotli  # type: ignore
        return f"brotli PyPI {getattr(brotli, '__version__', '?')} (fallback)"


class Gzip(Solution):
    name = "Baseline: gzip -n -6"
    ext = ".gz"
    header_bytes = GZIP_OVERHEAD

    def __init__(self, exe: str):
        self.exe = exe

    def compress_cmd(self, src, dst):
        return [self.exe, "-n", "-6", "-c", src], dst

    def decompress_cmd(self, src, dst):
        return [self.exe, "-d", "-c", src], dst

    def version(self):
        r = subprocess.run([self.exe, "--version"], capture_output=True, text=True)
        return (r.stdout or r.stderr).splitlines()[0].strip()


def find_solutions() -> list[Solution]:
    sols: list[Solution] = [Own()]
    exe = shutil.which("brotli")
    if exe:
        sols.append(BrotliCLI(exe))
    else:
        try:
            import brotli  # noqa: F401
            print("AVISO: CLI 'brotli' no encontrado; se usa el paquete PyPI (fallback).")
            sols.append(BrotliPy())
        except ImportError:
            sys.exit("ERROR: falta Brotli. Instalar el CLI:\n"
                     "  Debian/Ubuntu: sudo apt install brotli\n"
                     "  macOS:         brew install brotli\n"
                     "  Windows:       choco install brotli  (o MSYS2: pacman -S mingw-w64-x86_64-brotli)\n"
                     "o como fallback: pip install brotli")
    gz = shutil.which("gzip")
    if not gz:
        sys.exit("ERROR: falta gzip (Windows: viene con Git for Windows / MSYS2; "
                 "Linux/macOS: preinstalado).")
    sols.append(Gzip(gz))
    return sols


# ------------------------------------------------------------------- entorno
def cpu_name() -> str:
    try:
        if sys.platform == "win32":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        if sys.platform == "darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True).stdout.strip()
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "desconocido"


def check_corpus(corpus: Path) -> None:
    readme = (corpus / "README_pruebas.txt").read_text(encoding="utf-8", errors="replace")
    expected = dict(re.findall(r"(prueba_\S+\.txt)\s+bytes:\s*\d+\s+sha256:\s*([0-9a-f]{64})",
                               readme))
    for f in FILES:
        got = sha256((corpus / f).read_bytes())
        if expected.get(f) != got:
            sys.exit(f"ERROR: {f} no coincide con README_pruebas.txt "
                     f"(esperado {expected.get(f)}, obtenido {got}). "
                     "¿git convirtió CRLF? Ver .gitattributes.")
    print(f"Corpus verificado: {len(FILES)} archivos coinciden con README_pruebas.txt")


# ---------------------------------------------------------------- medición
def weissman(r: float, rref: float, t_ms: float, tref_ms: float) -> float | None:
    if t_ms <= 1 or tref_ms <= 1:
        return None                                 # ln(T) <= 0: no definido
    return (r / rref) * (math.log(tref_ms) / math.log(t_ms))


def bench_one(sol: Solution, src: Path, work: Path, reps: int) -> dict:
    comp = work / (src.stem + sol.ext)
    rec = work / (src.stem + ".rec")
    original = src.read_bytes()
    tcs, tds, sha_ok = [], [], True
    for i in range(reps + 1):                      # i = 0: warm-up descartado
        for p in (comp, rec):
            if p.exists():
                p.unlink()
        cmd, out = sol.compress_cmd(str(src), str(comp))
        tc = _run(cmd, out)
        cmd, out = sol.decompress_cmd(str(comp), str(rec))
        td = _run(cmd, out)
        sha_ok &= sha256(rec.read_bytes()) == sha256(original)
        if i:
            tcs.append(tc)
            tds.append(td)
    return {"sc": comp.stat().st_size, "tc_ns": tcs, "td_ns": tds, "sha_ok": sha_ok}


def core_times(data: bytes, reps: int) -> tuple[float, float]:
    """Mediana (ms) del núcleo propio en proceso, sin arranque ni E/S."""
    tcs, tds = [], []
    for i in range(reps + 1):
        t0 = time.perf_counter_ns()
        enc = ah.encode(data)
        t1 = time.perf_counter_ns()
        out = ah.decode(enc.payload, len(data), enc.bit_length)
        t2 = time.perf_counter_ns()
        assert out == data
        if i:
            tcs.append(t1 - t0)
            tds.append(t2 - t1)
    return statistics.median(tcs) / 1e6, statistics.median(tds) / 1e6


def fmt(x, nd=2):
    if x is None:
        return "no definido"
    if isinstance(x, bool):
        return "OK" if x else "FAIL"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--corpus", default=str(ROOT / "tests" / "corpus"))
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()
    corpus, outdir = Path(args.corpus), Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    check_corpus(corpus)
    sols = find_solutions()
    rows, raw = [], {}
    with tempfile.TemporaryDirectory(prefix="tdi_bench_") as tmp:
        work = Path(tmp)
        for f in FILES:
            src = corpus / f
            data = src.read_bytes()
            so = len(data)
            h0 = entropy0(data)
            bound = 8 / h0 if h0 else None
            per = {}
            for sol in sols:
                print(f"  {f:32s} {sol.name:36s} ...", end="", flush=True)
                per[sol.name] = bench_one(sol, src, work, args.reps)
                print(" ok" if per[sol.name]["sha_ok"] else " SHA FAIL")
            raw[f] = per
            ref = per[sols[-1].name]
            ref_r = so / ref["sc"]
            ref_t = statistics.median(ref["tc_ns"]) / 1e6
            core_c, core_d = core_times(data, args.reps)
            for sol in sols:
                m = per[sol.name]
                sc = m["sc"]
                tc = statistics.median(m["tc_ns"]) / 1e6
                td = statistics.median(m["td_ns"]) / 1e6
                r = so / sc
                rows.append({
                    "Archivo": f, "Solución": sol.name, "So": so, "Sc": sc,
                    "Ratio": r, "Ahorro%": (1 - sc / so) * 100,
                    "Relativo%": sc / so * 100,
                    "Tc_ms": tc, "Td_ms": td,
                    "Vc_MBs": so / MB / (tc / 1e3), "Vd_MBs": so / MB / (td / 1e3),
                    "Overhead%": (sol.header_bytes / sc * 100) if sol.header_bytes else None,
                    "Weissman": weissman(r, ref_r, tc, ref_t),
                    "SHA_OK": m["sha_ok"],
                    "Cota_orden0": bound, "H0_bits_byte": h0,
                    "Distintos": len(set(data)),
                    "Nucleo_Tc_ms": core_c if isinstance(sol, Own) else None,
                    "Nucleo_Td_ms": core_d if isinstance(sol, Own) else None,
                })

    # ---- Weissman global (pruebas 2-4)
    glob = []
    ref_name = sols[-1].name
    for sol in sols:
        so_sum = sum(len((corpus / f).read_bytes()) for f in RANKED)
        sc_sum = sum(raw[f][sol.name]["sc"] for f in RANKED)
        totals = [sum(raw[f][sol.name]["tc_ns"][i] for f in RANKED)
                  for i in range(args.reps)]
        glob.append({"Solución": sol.name, "SumSo": so_sum, "SumSc": sc_sum,
                     "Rglobal": so_sum / sc_sum,
                     "Tglobal_ms": statistics.median(totals) / 1e6})
    gref = next(g for g in glob if g["Solución"] == ref_name)
    for g in glob:
        g["Wglobal"] = weissman(g["Rglobal"], gref["Rglobal"],
                                g["Tglobal_ms"], gref["Tglobal_ms"])

    env = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": cpu_name(), "nucleos_logicos": os.cpu_count(),
        "so": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": f"{platform.python_implementation()} {platform.python_version()}",
        "repeticiones": args.reps, "warmup": 1, "estadistico": "mediana",
        "tiempo": "subprocess, perf_counter_ns (incluye arranque de proceso)",
        "versiones": {s.name: s.version() for s in sols},
    }

    # ---- exportar
    cols = ["Archivo", "Solución", "So", "Sc", "Ratio", "Ahorro%", "Relativo%",
            "Tc_ms", "Td_ms", "Vc_MBs", "Vd_MBs", "Overhead%", "Weissman",
            "SHA_OK", "Cota_orden0", "H0_bits_byte", "Distintos",
            "Nucleo_Tc_ms", "Nucleo_Td_ms"]
    with open(outdir / "results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else
                            round(r[k], 6) if isinstance(r[k], float) else r[k])
                        for k in cols})
    with open(outdir / "results.json", "w", encoding="utf-8") as fh:
        json.dump({"entorno": env, "filas": rows, "weissman_global": glob,
                   "crudo_ns": raw}, fh, ensure_ascii=False, indent=2)
    with open(outdir / "entorno.txt", "w", encoding="utf-8") as fh:
        for k, v in env.items():
            if isinstance(v, dict):
                fh.write(f"{k}:\n")
                for kk, vv in v.items():
                    fh.write(f"  {kk}: {vv}\n")
            else:
                fh.write(f"{k}: {v}\n")

    md = ["# Resultados del benchmark", "",
          f"Entorno: {env['cpu']} · {env['so']} · {env['python']}. "
          f"Mediana de {args.reps} repeticiones (1 warm-up descartado). "
          "Tiempos por subprocess (incluyen arranque de proceso).", "",
          "| Archivo | Solución | So | Sc | Ratio | Ahorro% | Tc_ms | Td_ms | Vc (MB/s) "
          "| Vd (MB/s) | Overhead% | Weissman | SHA_OK | Cota orden-0 |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|"]
    for r in rows:
        md.append("| " + " | ".join([
            r["Archivo"].replace(".txt", ""), r["Solución"], str(r["So"]), str(r["Sc"]),
            fmt(r["Ratio"], 3), fmt(r["Ahorro%"]), fmt(r["Tc_ms"]), fmt(r["Td_ms"]),
            fmt(r["Vc_MBs"], 3), fmt(r["Vd_MBs"], 3),
            fmt(r["Overhead%"], 3) if r["Overhead%"] is not None else "n/d",
            fmt(r["Weissman"], 3), fmt(r["SHA_OK"]), fmt(r["Cota_orden0"], 3)]) + " |")
    md += ["", "## Weissman global (pruebas 2–4, ref = gzip -n -6, T en ms)", "",
           "| Solución | ΣSo | ΣSc | Rglobal | Tglobal_ms | Wglobal |",
           "|---|---:|---:|---:|---:|---:|"]
    for g in glob:
        md.append(f"| {g['Solución']} | {g['SumSo']} | {g['SumSc']} | "
                  f"{g['Rglobal']:.3f} | {g['Tglobal_ms']:.2f} | {fmt(g['Wglobal'], 3)} |")
    md += ["", "## Núcleo propio en proceso (sin arranque de Python ni E/S)", "",
           "| Archivo | Tc núcleo (ms) | Td núcleo (ms) | Vc (MB/s) | Vd (MB/s) |",
           "|---|---:|---:|---:|---:|"]
    for r in rows:
        if r["Nucleo_Tc_ms"] is not None:
            md.append(f"| {r['Archivo'].replace('.txt', '')} | {r['Nucleo_Tc_ms']:.2f} | "
                      f"{r['Nucleo_Td_ms']:.2f} | {r['So'] / MB / (r['Nucleo_Tc_ms'] / 1e3):.3f} | "
                      f"{r['So'] / MB / (r['Nucleo_Td_ms'] / 1e3):.3f} |")
    md += ["", "Notas:",
           "- Prueba 1 se excluye del ranking temporal (lo indica la cátedra); su Weissman es solo ilustrativo.",
           "- Weissman = (R/Rref)·(ln Tref/ln T), T = Tc en ms, α = 1; \"no definido\" si T ≤ 1 ms.",
           "- Overhead: .tdi = 20 B de cabecera fija; gzip = 18 B (cabecera 10 B + trailer 8 B); "
           "Brotli no tiene cabecera de contenedor (n/d).",
           "- Cota orden-0 = 8/H₀ (entropía empírica de bytes): máximo ratio alcanzable por "
           "cualquier código de orden 0 sin contar cabecera."]
    (outdir / "tabla.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    all_ok = all(r["SHA_OK"] for r in rows)
    print("\n".join(md))
    print(f"\nSHA round-trip: {'TODOS OK' if all_ok else 'HAY FALLOS'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
