# Detects system RAM and GPU VRAM on Windows.
# Uses PowerShell for RAM and nvidia-smi/dxdiag for VRAM.
# Returns dicts with 'source' keys for logging.

import os
import json
import tempfile
import subprocess
import time
from typing import Optional

# Suppress console window flashes on Windows for child processes
_CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def _run(cmd: list[str], timeout: int = 10) -> Optional[subprocess.CompletedProcess]:
    # Run a subprocess, returning None on FileNotFoundError or timeout
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def get_ram() -> dict:
    
    # Return total physical RAM in bytes.
    
    result = _run([
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_ComputerSystem "
        "| Select-Object -ExpandProperty TotalPhysicalMemory",
    ])

    if result is None or result.returncode != 0:
        return {"bytes": None, "gb": None, "source": None,
                "error": "PowerShell call failed"}

    try:
        raw = result.stdout.strip()
        total_bytes = int(raw)
        return {
            "bytes": total_bytes,
            "gb": round(total_bytes / (1024 ** 3), 2),
            "source": "powershell",
        }
    except ValueError:
        return {"bytes": None, "gb": None, "source": None,
                "error": f"Unexpected output: {result.stdout!r}"}



# VRAM detection by nvidia-smi 


def _vram_from_nvidia_smi() -> Optional[list[dict]]:
    # Query nvidia-smi for all GPUs.
    # Returns a list of GPU dicts, or None if nvidia-smi is unavailable.
    
    result = _run([
        "nvidia-smi",
        "--query-gpu=index,name,memory.total",
        "--format=csv,noheader,nounits",
    ], timeout=5)

    if result is None or result.returncode != 0:
        return None

    gpus = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            index, name, vram_mb = int(parts[0]), parts[1], int(parts[2])
            vram_bytes = vram_mb * 1024 * 1024
            gpus.append({
                "index": index,
                "name": name,
                "vram_bytes": vram_bytes,
                "vram_gb": round(vram_bytes / (1024 ** 3), 2),
                "source": "nvidia-smi",
            })
        except ValueError:
            continue

    return gpus if gpus else None


# VRAM detection by dxdiag

def _parse_dxdiag(path: str) -> list[dict]:
    # Parse dxdiag output, return GPU dicts
    # Trying UTF-16 and fallback to UTF-8
    text = None
    for enc in ("utf-16", "utf-8", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if text is None:
        return []

    gpus = []
    current: Optional[dict] = None
    in_display_section = False

    for line in text.splitlines():
        stripped = line.strip()

        # Detect start of a Display Devices section
        if "Display Devices" in stripped and stripped.startswith("-"):
            # Save previous GPU if we have one
            if current is not None:
                gpus.append(current)
            current = {}
            in_display_section = True
            continue

        # Detect start of any other major section — ends display block
        if stripped.startswith("-") and stripped.endswith("-") and in_display_section:
            if "Display Devices" not in stripped:
                if current is not None:
                    gpus.append(current)
                    current = None
                in_display_section = False
                continue

        if not in_display_section or current is None:
            continue

        # Parse the fields we care about
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "card name":
                current["name"] = value

            elif key == "dedicated memory":
                # Value like "12152 MB" or "N/A"
                try:
                    mb = int(value.split()[0])
                    vram_bytes = mb * 1024 * 1024
                    current["vram_bytes"] = vram_bytes
                    current["vram_gb"] = round(vram_bytes / (1024 ** 3), 2)
                except (ValueError, IndexError):
                    pass  # "N/A" or unexpected format — leave key absent

    # last section
    if current is not None:
        gpus.append(current)

    # Filter entries 
    result = []
    for i, gpu in enumerate(gpus):
        if "name" not in gpu:
            continue
        gpu.setdefault("vram_bytes", None)
        gpu.setdefault("vram_gb", None)
        gpu["index"] = i
        gpu["source"] = "dxdiag"
        result.append(gpu)

    return result


def _vram_from_dxdiag() -> Optional[list[dict]]:
    
    # Run dxdiag, write output to a temp file, parse it, clean up.
    # Returns a list of GPU dicts, or None on failure.
    
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="dxdiag_")
    os.close(tmp_fd)

    try:
        result = _run(["dxdiag", "/t", tmp_path], timeout=30)
        if result is None:
            return None

        # dxdiag writes asynchronously; wait until the file has content
        for _ in range(20):          # up to ~10 s
            if os.path.getsize(tmp_path) > 0:
                break
            time.sleep(0.5)

        gpus = _parse_dxdiag(tmp_path)
        return gpus if gpus else None

    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def get_vram() -> list[dict]:
    # Return list of GPU dicts with VRAM info
    # --- Attempt 1: nvidia-smi ---
    gpus = _vram_from_nvidia_smi()
    if gpus:
        return gpus

    # --- Attempt 2: dxdiag ---
    gpus = _vram_from_dxdiag()
    if gpus:
        return gpus

    # --- All methods failed ---
    return [{
        "index": 0,
        "name": "Unknown",
        "vram_bytes": None,
        "vram_gb": None,
        "source": None,
        "error": "All detection methods failed",
    }]


# Primary function for calls by parent

def detect_memory() -> dict:
    #Run all detects, return a summary dict.
    return {
        "ram": get_ram(),
        "gpus": get_vram(),
    }

# Direct-run Self-test

if __name__ == "__main__":
    import pprint
    print("Detecting memory, please wait...\n")
    info = detect_memory()
    pprint.pprint(info)