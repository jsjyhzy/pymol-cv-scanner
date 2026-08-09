# -*- coding: utf-8 -*-
"""OpenMM calculation core: CV computation and scanning."""

# OpenMM (and NumPy) are only required for local scanning. Keep their import
# optional so the plugin can still be loaded and used to generate batch
# scripts on machines where only PyMOL is installed.
try:
    import numpy as np
    import openmm as mm
    from openmm import unit
    from openmm.app import AmberPrmtopFile, PDBFile, Simulation
    OPENMM_AVAILABLE = True
except ImportError:
    np = None
    mm = None
    unit = None
    AmberPrmtopFile = None
    PDBFile = None
    Simulation = None
    OPENMM_AVAILABLE = False


def _require_openmm():
    if not OPENMM_AVAILABLE:
        raise RuntimeError(
            "OpenMM is not installed, so local scanning is unavailable. "
            "You can still generate a batch script and run it on a machine "
            "that has OpenMM installed."
        )


def scan_cv_to_file(prmtop_file, pdb_file, group1_indices, group2_indices,
                    start_dist, end_dist, nwindows, force_constant,
                    tolerance, max_iter, output_file, progress_queue=None,
                    implicit_solvent=False):
    """
    Perform constrained minimization and write a multi‑model PDB to output_file.
    Runs in a separate process.
    progress_queue receives the current window index (1‑based) if provided.
    implicit_solvent: use the OBC2 implicit solvent model (forces NoCutoff).
    """
    _require_openmm()
    prmtop = AmberPrmtopFile(prmtop_file)
    pdb = PDBFile(pdb_file)
    n_atoms = prmtop.topology.getNumAtoms()

    # Periodicity. Implicit solvent requires NoCutoff (OBC2 is incompatible
    # with periodic PME), so the box is ignored in that case.
    box_vectors = pdb.topology.getPeriodicBoxVectors()
    if implicit_solvent or box_vectors is None:
        nonbondedMethod = mm.app.NoCutoff
        nonbondedCutoff = None
    else:
        nonbondedMethod = mm.app.PME
        nonbondedCutoff = 1.0 * unit.nanometer

    system = prmtop.createSystem(
        nonbondedMethod=nonbondedMethod,
        nonbondedCutoff=nonbondedCutoff,
        constraints=mm.app.HBonds,
        rigidWater=False,
        implicitSolvent=mm.app.OBC2 if implicit_solvent else None
    )

    # Centroid force
    centroid_force = mm.CustomCentroidBondForce(2, "distance(g1, g2)")
    centroid_force.addGroup(group1_indices)
    centroid_force.addGroup(group2_indices)
    centroid_force.addBond([0, 1], [])

    # Bias (harmonic restraint)
    bias = mm.CustomCVForce("0.5 * k * (cv1 - target)^2")
    bias.addCollectiveVariable("cv1", centroid_force)
    bias.addGlobalParameter("k", force_constant * unit.kilojoule_per_mole / unit.nanometer**2)
    bias.addGlobalParameter("target", 0.0 * unit.nanometer)
    system.addForce(bias)

    integrator = mm.LangevinIntegrator(300*unit.kelvin, 1.0/unit.picosecond, 0.002*unit.picoseconds)
    platform = mm.Platform.getPlatformByName('Reference')
    simulation = Simulation(prmtop.topology, system, integrator, platform)
    simulation.context.setPositions(pdb.positions)
    if box_vectors is not None:
        simulation.context.setPeriodicBoxVectors(*box_vectors)

    targets = np.linspace(start_dist, end_dist, nwindows)

    # Write multi‑model PDB one model at a time (streaming, to bound memory)
    with open(output_file, 'w') as f:
        for i, target in enumerate(targets):
            simulation.context.setParameter("target", target * unit.nanometer)
            simulation.minimizeEnergy(tolerance=tolerance, maxIterations=max_iter)
            state = simulation.context.getState(getPositions=True)
            pos = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
            # Truncate if extra particles exist
            if len(pos) > n_atoms:
                print(f"Warning: Context has {len(pos)} particles, topology has {n_atoms} atoms. Truncating.")
                pos = pos[:n_atoms]
            elif len(pos) < n_atoms:
                raise RuntimeError(f"Context has fewer particles ({len(pos)}) than topology ({n_atoms}).")
            f.write(f"MODEL     {i+1}\n")
            PDBFile.writeModel(prmtop.topology, pos * unit.nanometer, f, keepIds=True)
            f.write("ENDMDL\n")
            if progress_queue is not None:
                progress_queue.put(i + 1)


def compute_cv_value(prmtop_file, pdb_file, group1_indices, group2_indices,
                     implicit_solvent=False):
    """Compute centroid distance (nm) for given coordinates (runs in main thread)."""
    _require_openmm()
    prmtop = AmberPrmtopFile(prmtop_file)
    pdb = PDBFile(pdb_file)

    system = prmtop.createSystem(
        nonbondedMethod=mm.app.NoCutoff,
        constraints=None,
        rigidWater=False,
        implicitSolvent=mm.app.OBC2 if implicit_solvent else None
    )
    centroid_force = mm.CustomCentroidBondForce(2, "distance(g1, g2)")
    centroid_force.addGroup(group1_indices)
    centroid_force.addGroup(group2_indices)
    centroid_force.addBond([0, 1], [])
    cv_force = mm.CustomCVForce("cv1")
    cv_force.addCollectiveVariable("cv1", centroid_force)
    system.addForce(cv_force)

    integrator = mm.VerletIntegrator(0.001 * unit.picoseconds)
    platform = mm.Platform.getPlatformByName('Reference')
    simulation = Simulation(prmtop.topology, system, integrator, platform)
    simulation.context.setPositions(pdb.positions)
    box_vectors = pdb.topology.getPeriodicBoxVectors()
    if box_vectors is not None:
        simulation.context.setPeriodicBoxVectors(*box_vectors)

    cv_val = cv_force.getCollectiveVariableValues(simulation.context)[0]
    if hasattr(cv_val, 'value_in_unit'):
        return cv_val.value_in_unit(unit.nanometer)
    else:
        return float(cv_val)