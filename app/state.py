# estado mutable (snapshot_base/cookies)

from dataclasses import dataclass

@dataclass
class RuntimeState:
    """
    Estado mutable de la sesión:
    - snapshot_base: URL base tipo http://host/out.jpg?q=30&id=XXXX (sin &r=)
    - snapshot_cookie: cookies de sesión (si el servidor las usa)
    """
    snapshot_base: str
    snapshot_cookie: str
