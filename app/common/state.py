from __future__ import annotations
import os
import json
from pathlib import Path

def _runtime_dir() -> Path:
    raw = os.getenv("RUNTIME_DIR", "./runtime")
    p = Path(raw).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _state_path() -> Path:
    return _runtime_dir() / "armed_state.json"

def set_armed(armed: bool) -> None:
    try:
        _state_path().write_text(json.dumps({"armed": bool(armed)}), encoding="utf-8")
        print(f"[STATE] set_armed({armed}) -> {_state_path()}")
    except Exception as e:
        print(f"[STATE] ERROR set_armed: {e}")

def is_armed() -> bool:
    path = _state_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("armed", False))
    except Exception as e:
        print(f"[STATE] ERROR is_armed: {e}")
        return False

def ensure_initial_state() -> None:
    """
    Sobrescribe SIEMPRE el estado en cada arranque con ARMED_ON_BOOT.
    Garantiza iniciar armado si ARMED_ON_BOOT=true.
    """
    initial = os.getenv("ARMED_ON_BOOT", "false").lower() == "true"
    set_armed(initial)
    print(f"[STATE] ensure_initial_state -> armed={initial} (RUNTIME={_runtime_dir()})")
