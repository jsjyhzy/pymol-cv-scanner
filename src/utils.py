# -*- coding: utf-8 -*-
"""Utility functions: file encoding, PyMOL selection handling, etc."""

import base64
import gzip

# PyMOL imports (only needed when running in PyMOL environment)
try:
    from pymol import cmd
except ImportError:
    cmd = None


def encode_file(file_path):
    """Read file, compress with gzip, and return base64 encoded string."""
    with open(file_path, 'rb') as f:
        data = f.read()
    compressed = gzip.compress(data, compresslevel=9)
    return base64.b64encode(compressed).decode('ascii')


def get_current_selection_indices():
    """
    Return 0‑based atom indices from the current PyMOL selection ('sele').
    If no selection or not in PyMOL, return empty list.
    """
    if cmd is None:
        return []
    try:
        model = cmd.get_model('sele')
        return [atom.index - 1 for atom in model.atom]
    except Exception:
        return []