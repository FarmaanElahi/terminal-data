import numpy as np

# Define the structured array dtype for a candle
CANDLE_DTYPE = np.dtype(
    [
        ("timestamp", "int64"),  # Unix timestamp in milliseconds or seconds
        ("open", "float64"),
        ("high", "float64"),
        ("low", "float64"),
        ("close", "float64"),
        ("volume", "float64"),
    ]
)
