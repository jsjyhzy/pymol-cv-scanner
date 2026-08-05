# -*- coding: utf-8 -*-
"""Generate standalone Python script from template file."""

import os
import pkgutil

from .utils import encode_file

def _read_template():
    """Read template file content from package's templates directory."""
    # Use pkgutil to read file relative to this module
    template_bytes = pkgutil.get_data(__name__, 'templates/scan_script_template.py')
    if template_bytes is None:
        # Fallback: use filesystem path
        this_dir = os.path.dirname(__file__)
        template_path = os.path.join(this_dir, 'templates', 'scan_script_template.py')
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return template_bytes.decode('utf-8')


def create_script_content(prmtop_file, pdb_file, g1, g2,
                          start, end, nwindows, force_const,
                          tolerance, max_iter):
    """Return the rendered script string."""
    prmtop_b64 = encode_file(prmtop_file)
    pdb_b64 = encode_file(pdb_file)

    template = _read_template()
    return template.format(
        prmtop_b64=prmtop_b64,
        pdb_b64=pdb_b64,
        g1=g1,
        g2=g2,
        start=start,
        end=end,
        nwindows=nwindows,
        force_const=force_const,
        tolerance=tolerance,
        max_iter=max_iter
    )