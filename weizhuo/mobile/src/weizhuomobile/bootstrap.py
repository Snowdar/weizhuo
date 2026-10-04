"""Prepare a supported C-library locale before constructing the native UI."""
import locale
import os


def prepare_locale():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        # Some iPhone language identifiers have no matching libc locale.
        os.environ["LC_ALL"] = "C"
        locale.setlocale(locale.LC_ALL, "C")
