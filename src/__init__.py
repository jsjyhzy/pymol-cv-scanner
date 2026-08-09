# -*- coding: utf-8 -*-
# Name: Distance Constrained Minimization
# Version: 1.0.0
# Description: Distance-constrained energy minimization scan between two atom groups using OpenMM.
# Author: huzheyang
"""PyMOL plugin entry point."""

from pymol.plugins import addmenuitem
from .gui import DistanceScanPlugin

_plugin_instance = None

def launch_plugin():
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = DistanceScanPlugin()
    _plugin_instance.show()
    _plugin_instance.raise_()
    _plugin_instance.activateWindow()

def __init__(self):
    addmenuitem("Distance Constrained Minimization", launch_plugin)