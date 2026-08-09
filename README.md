# ⚠️ AI-generated project — use with caution

> **Disclaimer:** This project was **largely produced by AI** (the
> `deepseek-v4-flash-free` assistant) with human supervision. It is shared
> as a working prototype and may contain issues, suboptimal design, or gaps
> in verification. **Please review the code and test it on non-critical
> inputs before relying on it.**

---

# Distance Constrained Minimization — PyMOL Plugin

A [PyMOL](https://pymol.org) plugin that performs an **energy-minimization
scan** on the **centroid distance between two atom groups**, using
[OpenMM](https://openmm.org). Windows across a distance range are minimized
under a harmonic restraint, and the resulting conformations are loaded back
into PyMOL as a multi-state PDB object. A self-contained batch application
(Python zipapp) can also be generated and submitted to a compute cluster.

## Features

- **PyQt5 GUI** — registers under PyMOL's *Plugin* menu.
- **Atom groups from PyMOL selections** — assign the current `sele` to
  Group1/Group2; live centroid-distance display.
- **Centroid-distance scan** — step a harmonic bias over a distance range
  across N windows, minimizing each window.
- **Implicit solvent (OBC2)** — optional; forces `NoCutoff` (OBC2 is
  incompatible with periodic PME).
- **Streaming PDB output** — each window is written immediately, keeping
  memory bounded for large systems × many windows.
- **Self-contained batch CLI (`.pyz`)** — the real `.prmtop`/`.pdb` are
  packed into a Python zipapp; all parameters are baked in but overridable
  via `--help`/`--params` and flags such as `-s`, `-e`, `-n`, `-k`.
- **Works with or without OpenMM** — if OpenMM is not installed, `Run Scan`
  and `Compute CV` are disabled, but **Generate Batch Script** still works,
  so a cluster-ready app can always be produced.

## Requirements

| Use case | Requirement |
|---|---|
| Load the plugin / generate a batch app | PyMOL ≥ 2.5 with Qt (PyQt5) |
| Run scans locally (GUI + Compute CV) | OpenMM ≥ 8.0 and NumPy in PyMOL's Python env |
| Run a generated `.pyz` on a cluster | Python ≥ 3.7, OpenMM ≥ 8.0, NumPy |

## Build & install

Build the plugin archive:

```bash
make dist   # -> dist/distance_scan_plugin-<version>.tar.gz
```

In PyMOL:

1. `Plugin > Plugin Manager > Install New Plugin`.
2. Choose `dist/distance_scan_plugin-<version>.tar.gz`.
3. Restart PyMOL.

A **"Distance Constrained Minimization"** entry then appears under the
*Plugin* menu. Pushing a `vX.Y.Z` tag publishes the tarball as a
GitHub Release automatically (see below).

## Usage

1. Select the input `.prmtop` and `.pdb` files.
2. *Load Structure* to display the system in PyMOL.
3. Select atoms in PyMOL, then press **Set Group1** / **Set Group2**.
4. **Compute CV** shows the current centroid distance.
5. Enter scan parameters (start/end in nm, number of windows, force
   constant, tolerance, max iterations, implicit solvent).
6. **Run Scan** to minimize each window — the multi-state
   `scan_results` object appears in PyMOL afterwards.
7. Or **Generate Batch Script** to save a self-contained `scan_script.pyz`.

### Generated batch CLI

```bash
python scan_script.pyz --params                 # show effective settings, exit
python scan_script.pyz                         # run with baked-in parameters
python scan_script.pyz -o result.pdb -s 1.0 -e 5.0 -n 10 -k 10000 --implicit
```

The input files are embedded in the `.pyz`; nothing else must be uploaded.
Output defaults to `scan_results.pdb`.

## Development

```bash
make check          # syntax check (py_compile), no PyMOL needed
make dist           # build the plugin tarball
make test           # validate archive structure + Python syntax
make test-pymol     # real load test under `pymol -cq`
make clean          # remove the tarball
```

GitHub Actions (`.github/workflows/build-plugin.yml`) runs all tests on every
push to `master` and on every PR (building + uploading a tarball artifact).
Pushing a `vX.Y.Z` tag verifies the `# Version:` line in `src/__init__.py`
matches the tag, then creates a GitHub Release attached with the tarball.

## Repository layout

```
src/                        # plugin package (packed as distance_scan_plugin/)
├── __init__.py             # PyMOL plugin entry + metadata
├── gui.py                  # PyQt5 GUI
├── core.py                 # OpenMM scan / CV computation
├── batch_script.py         # zipapp batch-app generation
├── utils.py                # atom-selection helpers
└── templates/
    └── scan_zipapp_main.py # __main__.py template for the .pyz app
Makefile                    # build/check/test targets
scripts/test_plugin_load.py # archive validation & PyMOL load test
.github/workflows/          # CI (build + release)
```

## Maintenance

See `AGENTS.md` for the architecture and technical decisions. Changes are
developed on feature branches and merged through pull requests; AI-generated
commits carry a `Co-authored-by` trailer.

## License

Not specified — contact the maintainer (`@jsjyhzy`) for reuse terms.