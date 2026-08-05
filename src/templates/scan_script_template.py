#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Standalone batch script for distance-constrained minimization.
Input files are embedded as base64+gzip compressed data.
Run with: python scan_script.py
Output: scan_results.pdb (multi-model PDB)
"""

import base64
import gzip
import tempfile
import os
import numpy as np
import openmm as mm
from openmm import unit
from openmm.app import AmberPrmtopFile, PDBFile, Simulation

def decode_file(encoded_data, suffix):
    """Decode base64+gzip data and write to a temporary file."""
    compressed = base64.b64decode(encoded_data)
    data = gzip.decompress(compressed)
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    return path

def run_scan():
    # Embedded file data (base64 of gzipped content)
    prmtop_b64 = """{prmtop_b64}"""
    pdb_b64 = """{pdb_b64}"""
    
    # Groups (0-based atom indices)
    group1 = {g1}
    group2 = {g2}
    
    # Scan parameters
    start_dist = {start}
    end_dist = {end}
    nwindows = {nwindows}
    force_constant = {force_const}  # kJ/(mol nm^2)
    tolerance = {tolerance}         # kJ/mol
    max_iter = {max_iter}
    output_file = "scan_results.pdb"
    
    # Decode embedded files to temporary files
    print("Extracting input files...")
    prmtop_file = decode_file(prmtop_b64, ".prmtop")
    pdb_file = decode_file(pdb_b64, ".pdb")
    print(f"PRMTOP: {{prmtop_file}}")
    print(f"PDB: {{pdb_file}}")
    
    # Load system
    prmtop = AmberPrmtopFile(prmtop_file)
    pdb = PDBFile(pdb_file)
    n_atoms = prmtop.topology.getNumAtoms()
    
    # Check periodicity
    box_vectors = pdb.topology.getPeriodicBoxVectors()
    if box_vectors is not None:
        nonbondedMethod = mm.app.PME
        nonbondedCutoff = 1.0 * unit.nanometer
    else:
        nonbondedMethod = mm.app.NoCutoff
        nonbondedCutoff = None
    
    system = prmtop.createSystem(
        nonbondedMethod=nonbondedMethod,
        nonbondedCutoff=nonbondedCutoff,
        constraints=mm.app.HBonds,
        rigidWater=False
    )
    
    # Centroid force
    centroid_force = mm.CustomCentroidBondForce(2, "distance(g1, g2)")
    centroid_force.addGroup(group1)
    centroid_force.addGroup(group2)
    centroid_force.addBond([0, 1], [])
    
    # Bias (harmonic restraint)
    bias = mm.CustomCVForce("0.5 * k * (cv1 - target)^2")
    bias.addCollectiveVariable("cv1", centroid_force)
    bias.addGlobalParameter("k", force_constant * unit.kilojoule_per_mole / unit.nanometer**2)
    bias.addGlobalParameter("target", 0.0 * unit.nanometer)
    system.addForce(bias)
    
    # Setup simulation – OpenMM will automatically select the best available platform
    integrator = mm.LangevinIntegrator(300*unit.kelvin, 1.0/unit.picosecond, 0.002*unit.picoseconds)
    simulation = Simulation(prmtop.topology, system, integrator)
    simulation.context.setPositions(pdb.positions)
    if box_vectors is not None:
        simulation.context.setPeriodicBoxVectors(*box_vectors)
    
    # Scan
    targets = np.linspace(start_dist, end_dist, nwindows)
    all_coords = []
    
    for i, target in enumerate(targets):
        print(f"Window {{i+1}}/{nwindows}: target = {{target:.3f}} nm")
        simulation.context.setParameter("target", target * unit.nanometer)
        simulation.minimizeEnergy(tolerance=tolerance, maxIterations=max_iter)
        state = simulation.context.getState(getPositions=True)
        pos = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
        # Ensure positions match topology (truncate if extra particles exist)
        if len(pos) > n_atoms:
            print(f"Warning: Context has {{len(pos)}} particles, topology has {{n_atoms}} atoms. Truncating.")
            pos = pos[:n_atoms]
        elif len(pos) < n_atoms:
            raise RuntimeError(f"Context has fewer particles ({{len(pos)}}) than topology ({{n_atoms}}).")
        all_coords.append(pos)
    
    # Write multi-model PDB manually (one model at a time)
    with open(output_file, 'w') as f:
        for model_idx, pos in enumerate(all_coords):
            f.write(f"MODEL     {{model_idx+1}}\n")
            PDBFile.writeModel(prmtop.topology, pos * unit.nanometer, f, keepIds=True)
            f.write("ENDMDL\n")
    
    # Clean up temporary files
    os.unlink(prmtop_file)
    os.unlink(pdb_file)
    
    print(f"Done! Results saved to {{output_file}}")

if __name__ == "__main__":
    run_scan()