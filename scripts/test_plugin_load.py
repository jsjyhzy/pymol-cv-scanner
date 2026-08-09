# -*- coding: utf-8 -*-
"""Validate a PyMOL plugin archive (tar.gz) and optionally load it in PyMOL.

Usage (plain Python, structural check only):
    python3 scripts/test_plugin_load.py dist/distance_scan_plugin-1.0.0.tar.gz

Usage (real PyMOL load test, run inside PyMOL):
    pymol -cq scripts/test_plugin_load.py -- dist/distance_scan_plugin-1.0.0.tar.gz

Exits non-zero on failure. PyMOL-specific tests only run when the `pymol`
module is importable (e.g. under `pymol -cq`).
"""

import argparse
import os
import shutil
import sys
import tarfile
import tempfile

EXPECTED_PACKAGE = 'distance_scan_plugin'
REQUIRED_DATA_FILES = ('templates/scan_zipapp_main.py',)


def build_tree(namelist):
    """Mirror PyMOL's extract_zipfile directory analysis (nested dict)."""
    tree = {}
    for name in namelist:
        node = tree
        for part in name.split('/'):
            if part != '':
                node = node.setdefault(part, {})
    return tree


def structural_validation(archive_path):
    """Return the package dir path inside the archive, or raise AssertionError."""
    try:
        tf = tarfile.open(archive_path, 'r:gz')
    except tarfile.ReadError as e:
        raise AssertionError('not a valid gzipped tar archive: %s' % e)

    namelist = tf.getnames()
    if len(namelist) == 0:
        raise AssertionError('archive empty')

    cwd = os.getcwd()
    for name in namelist:
        norm = os.path.normpath(name)
        if os.path.isabs(norm) or not os.path.abspath(norm).startswith(cwd):
            raise AssertionError('archive contains absolute path entries: %r' % name)

    tree = build_tree(namelist)
    packages = [name for name in tree if '__init__.py' in tree[name]]
    if len(packages) != 1:
        raise AssertionError('archive must contain a single package, found %r'
                             % packages)
    package = packages[0]
    if package != EXPECTED_PACKAGE:
        raise AssertionError('expected package %r, found %r'
                             % (EXPECTED_PACKAGE, package))
    if '.' in package:
        raise AssertionError('package name must not contain dots')

    for data_file in REQUIRED_DATA_FILES:
        member = package + '/' + data_file
        if member not in namelist:
            raise AssertionError('missing required data file: %s' % member)

    tf.close()
    return package


def syntax_check_all_py(archive_path):
    """Compile every .py file in the archive without executing it."""
    import ast
    tf = tarfile.open(archive_path, 'r:gz')
    try:
        for member in tf.getmembers():
            if not member.isfile() or not member.name.endswith('.py'):
                continue
            if 'templates/' in member.name:
                # Templates contain @@MARKER@@ placeholders and are not valid
                # Python until rendered by the plugin.
                continue
            f = tf.extractfile(member)
            source = f.read()
            f.close()
            ast.parse(source, filename=member.name)
    finally:
        tf.close()


def pymol_load_test(archive_path, package):
    """Extract archive and load the plugin through PyMOL's plugin engine."""
    import pymol.plugins as plugins

    tmpdir = tempfile.mkdtemp(prefix='pymol_plugin_test_')
    try:
        tf = tarfile.open(archive_path, 'r:gz')
        try:
            tf.extractall(tmpdir)
        finally:
            tf.close()

        mod_name = 'pymol.plugins.startup.%s' % package
        plugins.set_startup_path([tmpdir] + plugins.get_startup_path(True), False)
        plugins.initialize(-2)

        info = plugins.plugins.get(package)
        if info is None:
            raise AssertionError('plugin %r not registered' % package)
        if info.mod_name != mod_name:
            raise AssertionError('unexpected module name %r' % info.mod_name)

        info.load(pmgapp=-1)
        if not info.loaded:
            raise AssertionError('plugin failed to load')
        print('  plugin loaded as %s' % info.mod_name)

        mod = info.module
        entry = None
        if hasattr(mod, '__init_plugin__'):
            entry = mod.__init_plugin__
        elif hasattr(mod, '__init__'):
            import types
            if isinstance(mod.__init__, types.FunctionType):
                entry = mod.__init__
        if entry is None:
            raise AssertionError('plugin has no __init__/__init_plugin__ entry')
        entry(None)  # headless: no PMGApp, addmenuitem is a safe no-op
        print('  entry point %s called without error' % entry.__name__)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv):
    parser = argparse.ArgumentParser(description='Validate a PyMOL plugin archive.')
    parser.add_argument('archive', help='path to the .tar.gz plugin archive')
    args = parser.parse_args(argv)

    archive_path = os.path.abspath(args.archive)
    if not os.path.isfile(archive_path):
        print('FAIL: archive not found: %s' % archive_path)
        return 1

    print('Archive: %s' % os.path.basename(archive_path))

    try:
        package = structural_validation(archive_path)
        print('  structure OK: single package %r with __init__.py' % package)
        syntax_check_all_py(archive_path)
        print('  syntax OK: all Python files compile')
    except AssertionError as e:
        print('FAIL: %s' % e)
        return 1

    try:
        import pymol  # noqa: F401
    except ImportError:
        print('PyMOL not importable; skipped load test (use `make test-pymol`).')
        print('PASS')
        return 0

    try:
        pymol_load_test(archive_path, package)
        print('PASS')
        return 0
    except AssertionError as e:
        print('FAIL: %s' % e)
        return 1
    except Exception as e:
        print('FAIL: unexpected error during load test: %s' % e)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
