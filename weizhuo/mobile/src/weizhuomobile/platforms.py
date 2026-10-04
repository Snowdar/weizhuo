"""Recognize Android across CPython/Chaquopy platform names."""
import sys


def is_android():
    # Python/Chaquopy versions may report linux; Toga uses this same capability.
    return sys.platform == 'android' or hasattr(sys, 'getandroidapilevel')
