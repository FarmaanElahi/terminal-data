import traceback

try:
    from terminal.auth.models import User  # noqa: F401
    from terminal.lists.models import List  # noqa: F401
    from terminal.symbols.models import Symbol  # noqa: F401
    from terminal.scan.models import Scan  # noqa: F401
except Exception:
    traceback.print_exc()
