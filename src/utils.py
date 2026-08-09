# -*- coding: utf-8 -*-
"""Utility functions: PyMOL selection handling, etc."""

# PyMOL imports (only needed when running in PyMOL environment)
try:
    from pymol import cmd
except ImportError:
    cmd = None


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