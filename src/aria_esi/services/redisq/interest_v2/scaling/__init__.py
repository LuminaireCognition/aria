"""
Scaling Functions for Interest Engine v2.

Scaling functions normalize raw values (ISK, distance, time) to
scores in [0, 1]. Built-in functions are always available.
Custom scaling requires features.custom_scaling: true.
"""

from .builtin import (
    InverseScaling,
    LinearScaling,
    LogScaling,
    SigmoidScaling,
    StepScaling,
    scale_value,
)

__all__ = [
    "InverseScaling",
    "LinearScaling",
    "LogScaling",
    "SigmoidScaling",
    "StepScaling",
    "scale_value",
]
