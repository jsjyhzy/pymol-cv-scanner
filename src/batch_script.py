# -*- coding: utf-8 -*-
"""Generate a standalone batch CLI app (Python zipapp) from the template."""

import os
import pkgutil
import shutil
import tempfile
import zipapp


def _read_template():
    """Read template file content from package's templates directory."""
    # Use pkgutil to read file relative to this module
    template_bytes = pkgutil.get_data(__name__, 'templates/scan_zipapp_main.py')
    if template_bytes is None:
        # Fallback: use filesystem path
        this_dir = os.path.dirname(__file__)
        template_path = os.path.join(this_dir, 'templates', 'scan_zipapp_main.py')
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return template_bytes.decode('utf-8')


def _render_template(g1, g2, start, end, nwindows, force_const,
                     tolerance, max_iter, implicit_solvent):
    """Replace @@MARKER@@ tokens with literal Python values."""
    values = {
        'G1': repr(list(g1)),
        'G2': repr(list(g2)),
        'START': repr(float(start)),
        'END': repr(float(end)),
        'NWINDOWS': repr(int(nwindows)),
        'FORCE': repr(float(force_const)),
        'TOL': repr(float(tolerance)),
        'MAX_ITER': repr(int(max_iter)),
        'IMPLICIT': repr(bool(implicit_solvent)),
    }
    template = _read_template()
    for name, var in values.items():
        template = template.replace('@@' + name + '@@', var)
    return template


def create_batch_zipapp(output_path, prmtop_file, pdb_file, g1, g2,
                        start, end, nwindows, force_const,
                        tolerance, max_iter, implicit_solvent=False):
    """
    Pack a self-contained command-line application (.pyz) into output_path.

    The archive contains __main__.py (the rendered scan app) and the input
    files (data/input.prmtop, data/input.pdb), so it can be run anywhere with
    OpenMM installed:  python <output_path>
    """
    main_src = _render_template(g1, g2, start, end, nwindows, force_const,
                                tolerance, max_iter, implicit_solvent)

    staging = tempfile.mkdtemp(prefix='scan_zipapp_')
    try:
        with open(os.path.join(staging, '__main__.py'), 'w', encoding='utf-8') as f:
            f.write(main_src)

        data_dir = os.path.join(staging, 'data')
        os.makedirs(data_dir)
        shutil.copy(prmtop_file, os.path.join(data_dir, 'input.prmtop'))
        shutil.copy(pdb_file, os.path.join(data_dir, 'input.pdb'))

        def _filter(path):
            name = os.path.basename(path)
            return not name.startswith('.') and not name.endswith('.pyc')

        zipapp.create_archive(
            staging,
            output_path,
            interpreter='/usr/bin/env python3',
            compressed=True,
            filter=_filter,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return output_path