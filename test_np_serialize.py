import numpy as np
import json
from pydantic import BaseModel
from typing import Any

class ServerMessage(BaseModel):
    m: str
    p: tuple[Any, ...] | None = None

CANDLE_DTYPE = np.dtype(
    [
        ("timestamp", "i8"),
        ("open", "f4"),
        ("high", "f4"),
        ("low", "f4"),
        ("close", "f4"),
        ("volume", "f4"),
    ]
)

data = np.zeros(1, dtype=CANDLE_DTYPE)
latest = data[::-1].tolist()
print("latest[0] types:", [type(x) for x in latest[0]])

msg = ServerMessage(m="test", p=("session", "symbol", latest[0]))
print("Pydantic dump:")
try:
    dump = msg.model_dump(exclude_none=True)
    print(dump)
    json.dumps(dump)
    print("JSON dumps SUCCESS")
except Exception as e:
    print("JSON dumps FAILED:", type(e), e)
