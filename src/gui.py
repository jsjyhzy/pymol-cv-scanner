# -*- coding: utf-8 -*-
"""PyQt5 GUI for the distance scan plugin."""

import os
import tempfile
import multiprocessing as mp

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QGroupBox, QLabel, QLineEdit, QPushButton,
                             QProgressBar, QMessageBox, QFileDialog, QFrame,
                             QCheckBox)

from .core import OPENMM_AVAILABLE, scan_cv_to_file, compute_cv_value
from .batch_script import create_batch_zipapp
from .utils import get_current_selection_indices


class DistanceScanPlugin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Distance Constrained Minimization")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setMinimumSize(600, 650)
        self.openmm_available = OPENMM_AVAILABLE
        self.init_ui()

        self.group1_indices = []
        self.group2_indices = []
        self.current_cv = None
        self.process = None
        self.timer = None
        self.progress_queue = None
        self.nwindows = 0

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # File selection
        file_group = QGroupBox("Input Files")
        file_layout = QGridLayout()
        file_group.setLayout(file_layout)

        self.prmtop_edit = QLineEdit()
        self.pdb_edit = QLineEdit()
        btn_prmtop = QPushButton("Browse")
        btn_pdb = QPushButton("Browse")
        btn_prmtop.clicked.connect(self.browse_prmtop)
        btn_pdb.clicked.connect(self.browse_pdb)

        file_layout.addWidget(QLabel("PRMTOP:"), 0, 0)
        file_layout.addWidget(self.prmtop_edit, 0, 1)
        file_layout.addWidget(btn_prmtop, 0, 2)
        file_layout.addWidget(QLabel("PDB:"), 1, 0)
        file_layout.addWidget(self.pdb_edit, 1, 1)
        file_layout.addWidget(btn_pdb, 1, 2)

        btn_load = QPushButton("Load Structure")
        btn_load.clicked.connect(self.load_structure)
        file_layout.addWidget(btn_load, 2, 0, 1, 3)

        main_layout.addWidget(file_group)

        # Group selection
        group_group = QGroupBox("Atom Groups (PyMOL Selection)")
        group_layout = QVBoxLayout()
        group_group.setLayout(group_layout)
        group_layout.addWidget(QLabel("1. Click atoms in PyMOL to select a group."))
        group_layout.addWidget(QLabel("2. Press the button to assign the current selection."))

        hbox1 = QHBoxLayout()
        self.group1_label = QLabel("Group1: none")
        self.group1_label.setStyleSheet("color: blue;")
        btn_set1 = QPushButton("Set Group1")
        btn_clear1 = QPushButton("Clear Group1")
        btn_set1.clicked.connect(self.set_group1)
        btn_clear1.clicked.connect(self.clear_group1)
        hbox1.addWidget(self.group1_label)
        hbox1.addWidget(btn_set1)
        hbox1.addWidget(btn_clear1)
        group_layout.addLayout(hbox1)

        hbox2 = QHBoxLayout()
        self.group2_label = QLabel("Group2: none")
        self.group2_label.setStyleSheet("color: blue;")
        btn_set2 = QPushButton("Set Group2")
        btn_clear2 = QPushButton("Clear Group2")
        btn_set2.clicked.connect(self.set_group2)
        btn_clear2.clicked.connect(self.clear_group2)
        hbox2.addWidget(self.group2_label)
        hbox2.addWidget(btn_set2)
        hbox2.addWidget(btn_clear2)
        group_layout.addLayout(hbox2)

        main_layout.addWidget(group_group)

        # CV display
        cv_group = QGroupBox("Collective Variable")
        cv_layout = QHBoxLayout()
        cv_group.setLayout(cv_layout)
        self.cv_label = QLabel("Current CV: not computed")
        self.btn_compute = QPushButton("Compute CV")
        self.btn_compute.clicked.connect(self.compute_cv)
        cv_layout.addWidget(self.cv_label)
        cv_layout.addWidget(self.btn_compute)
        main_layout.addWidget(cv_group)

        # Scan parameters
        scan_group = QGroupBox("Scan Parameters")
        scan_layout = QGridLayout()
        scan_group.setLayout(scan_layout)

        self.start_edit = QLineEdit("0.2")
        self.end_edit = QLineEdit("2.0")
        self.nwindows_edit = QLineEdit("20")
        self.force_edit = QLineEdit("5000")
        self.tol_edit = QLineEdit("1e-4")
        self.iter_edit = QLineEdit("2000")
        self.implicit_check = QCheckBox("Use implicit solvent (OBC2)")

        scan_layout.addWidget(QLabel("Start (nm):"), 0, 0)
        scan_layout.addWidget(self.start_edit, 0, 1)
        scan_layout.addWidget(QLabel("End (nm):"), 0, 2)
        scan_layout.addWidget(self.end_edit, 0, 3)
        scan_layout.addWidget(QLabel("Windows:"), 1, 0)
        scan_layout.addWidget(self.nwindows_edit, 1, 1)
        scan_layout.addWidget(QLabel("Force constant (kJ/(mol nm²)):"), 2, 0)
        scan_layout.addWidget(self.force_edit, 2, 1)
        scan_layout.addWidget(QLabel("Tolerance (kJ/mol):"), 1, 2)
        scan_layout.addWidget(self.tol_edit, 1, 3)
        scan_layout.addWidget(QLabel("Max iterations:"), 2, 2)
        scan_layout.addWidget(self.iter_edit, 2, 3)
        scan_layout.addWidget(self.implicit_check, 3, 0, 1, 4)

        main_layout.addWidget(scan_group)

        # Run button & progress
        action_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Scan")
        self.run_button.clicked.connect(self.run_scan)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.hide()
        action_layout.addWidget(self.run_button)
        action_layout.addWidget(self.progress)
        main_layout.addLayout(action_layout)

        # Batch script generation
        batch_layout = QHBoxLayout()
        self.batch_button = QPushButton("Generate Batch Script")
        self.batch_button.clicked.connect(self.generate_batch_script)
        batch_layout.addWidget(self.batch_button)
        batch_layout.addStretch()
        main_layout.addLayout(batch_layout)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        main_layout.addWidget(self.status_label)

        if not self.openmm_available:
            self.run_button.setEnabled(False)
            self.btn_compute.setEnabled(False)
            self.status_label.setText(
                "OpenMM is not installed: Run Scan and Compute CV are disabled. "
                "You can still generate a batch script.")

    # Slots
    def browse_prmtop(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select PRMTOP file", "",
                                               "Amber prmtop (*.prmtop);;All files (*.*)")
        if fname:
            self.prmtop_edit.setText(fname)

    def browse_pdb(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select PDB file", "",
                                               "PDB files (*.pdb);;All files (*.*)")
        if fname:
            self.pdb_edit.setText(fname)

    def load_structure(self):
        from pymol import cmd
        pdb_path = self.pdb_edit.text().strip()
        if not pdb_path or not os.path.exists(pdb_path):
            QMessageBox.critical(self, "Error", "PDB file does not exist.")
            return
        cmd.load(pdb_path, "input_structure")
        cmd.show("cartoon", "input_structure")
        cmd.zoom("input_structure")
        self.status_label.setText("Structure loaded: input_structure")

    def set_group1(self):
        indices = get_current_selection_indices()
        if not indices:
            QMessageBox.warning(self, "Warning", "No atoms selected in PyMOL.")
            return
        self.group1_indices = indices
        self.group1_label.setText(f"Group1: {len(indices)} atoms (first: {indices[0]})")
        self.status_label.setText(f"Group1 set with {len(indices)} atoms.")
        self._highlight_group("group1", indices)

    def clear_group1(self):
        from pymol import cmd
        self.group1_indices = []
        self.group1_label.setText("Group1: none")
        cmd.delete("group1")
        self.status_label.setText("Group1 cleared.")

    def set_group2(self):
        indices = get_current_selection_indices()
        if not indices:
            QMessageBox.warning(self, "Warning", "No atoms selected in PyMOL.")
            return
        self.group2_indices = indices
        self.group2_label.setText(f"Group2: {len(indices)} atoms (first: {indices[0]})")
        self.status_label.setText(f"Group2 set with {len(indices)} atoms.")
        self._highlight_group("group2", indices)

    def clear_group2(self):
        from pymol import cmd
        self.group2_indices = []
        self.group2_label.setText("Group2: none")
        cmd.delete("group2")
        self.status_label.setText("Group2 cleared.")

    def _highlight_group(self, name, indices):
        from pymol import cmd
        if indices:
            sel_str = " or ".join([f"index {i+1}" for i in indices])
            cmd.select(name, sel_str)
            cmd.show("spheres", name)
            cmd.color("red" if name == "group1" else "blue", name)

    def compute_cv(self):
        if not self._check_prmtop_pdb():
            return
        if not self.group1_indices or not self.group2_indices:
            QMessageBox.warning(self, "Warning", "Both groups must be defined.")
            return

        try:
            cv = compute_cv_value(
                self.prmtop_edit.text().strip(),
                self.pdb_edit.text().strip(),
                self.group1_indices,
                self.group2_indices,
                self.implicit_check.isChecked()
            )
            self.current_cv = cv
            self.cv_label.setText(f"Current CV: {cv:.4f} nm")
            self.status_label.setText(f"CV computed: {cv:.4f} nm")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to compute CV:\n{str(e)}")
            self.status_label.setText("CV computation failed.")

    def run_scan(self):
        if not self._check_prmtop_pdb():
            return
        if not self.group1_indices or not self.group2_indices:
            QMessageBox.warning(self, "Warning", "Both groups must be defined.")
            return

        try:
            start = float(self.start_edit.text())
            end = float(self.end_edit.text())
            self.nwindows = int(self.nwindows_edit.text())
            force_const = float(self.force_edit.text())
            tolerance = float(self.tol_edit.text())
            max_iter = int(self.iter_edit.text())
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", f"Please check numeric entries:\n{str(e)}")
            return

        if start >= end:
            QMessageBox.critical(self, "Invalid Range", "Start must be less than end.")
            return
        if self.nwindows < 2:
            QMessageBox.critical(self, "Invalid Windows", "Number of windows must be at least 2.")
            return

        self.run_button.setEnabled(False)
        self.progress.setRange(0, self.nwindows)
        self.progress.setValue(0)
        self.progress.show()
        self.status_label.setText(f"Scanning... (0/{self.nwindows})")

        fd, out_file = tempfile.mkstemp(suffix='.pdb', prefix='scan_')
        os.close(fd)

        self.progress_queue = mp.Queue()

        args = (
            self.prmtop_edit.text().strip(),
            self.pdb_edit.text().strip(),
            self.group1_indices,
            self.group2_indices,
            start,
            end,
            self.nwindows,
            force_const,
            tolerance,
            max_iter,
            out_file,
            self.progress_queue,
            self.implicit_check.isChecked()
        )

        self.process = mp.Process(target=scan_cv_to_file, args=args)
        self.process.start()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(lambda: self._check_process(out_file))
        self.timer.start(500)

    def _check_process(self, out_file):
        if self.progress_queue is not None:
            try:
                while not self.progress_queue.empty():
                    window_index = self.progress_queue.get_nowait()
                    self.progress.setValue(window_index)
                    self.status_label.setText(f"Scanning... ({window_index}/{self.nwindows})")
            except Exception:
                pass

        if self.process is None:
            return
        if not self.process.is_alive():
            self.timer.stop()
            self._on_scan_done(out_file)

    def _on_scan_done(self, out_file):
        from pymol import cmd
        self.progress.hide()
        self.run_button.setEnabled(True)
        self.progress_queue = None

        if self.process.exitcode != 0:
            QMessageBox.critical(self, "Scan Error", "The scan subprocess failed.")
            self.status_label.setText("Scan failed.")
            if os.path.exists(out_file):
                os.unlink(out_file)
            self.process = None
            return

        try:
            cmd.load(out_file, "scan_results", state=0)
            cmd.show("cartoon", "scan_results")
            cmd.zoom("scan_results")
            states = len(cmd.get_states('scan_results'))
            self.status_label.setText(f"Loaded {states} states into 'scan_results'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load results:\n{str(e)}")
            self.status_label.setText("Load failed.")
        finally:
            if os.path.exists(out_file):
                os.unlink(out_file)
            self.process = None

    def generate_batch_script(self):
        if not self._check_prmtop_pdb():
            return
        if not self.group1_indices or not self.group2_indices:
            QMessageBox.warning(self, "Warning", "Both groups must be defined.")
            return

        try:
            start = float(self.start_edit.text())
            end = float(self.end_edit.text())
            nwindows = int(self.nwindows_edit.text())
            force_const = float(self.force_edit.text())
            tolerance = float(self.tol_edit.text())
            max_iter = int(self.iter_edit.text())
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", f"Please check numeric entries:\n{str(e)}")
            return

        if start >= end:
            QMessageBox.critical(self, "Invalid Range", "Start must be less than end.")
            return
        if nwindows < 2:
            QMessageBox.critical(self, "Invalid Windows", "Number of windows must be at least 2.")
            return

        default_name = "scan_script.pyz"
        script_path, _ = QFileDialog.getSaveFileName(self, "Save Batch Script", default_name,
                                                     "Python zipapp (*.pyz);;All files (*.*)")
        if not script_path:
            return

        try:
            create_batch_zipapp(
                script_path,
                self.prmtop_edit.text().strip(),
                self.pdb_edit.text().strip(),
                self.group1_indices,
                self.group2_indices,
                start, end, nwindows,
                force_const, tolerance, max_iter,
                self.implicit_check.isChecked()
            )
            QMessageBox.information(self, "Success",
                                    f"Batch script saved to:\n{script_path}\n\n"
                                    "Run it on any machine with OpenMM installed:\n"
                                    "python scan_script.pyz\n\n"
                                    "The prmtop and pdb are packed inside the app.\n"
                                    "Parameters can be overridden from the command line "
                                    "(run with --help for details).\n"
                                    "The output will be saved as 'scan_results.pdb'.")
            self.status_label.setText(f"Script saved: {os.path.basename(script_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save script:\n{str(e)}")

    def _check_prmtop_pdb(self):
        prm = self.prmtop_edit.text().strip()
        pdb = self.pdb_edit.text().strip()
        if not prm or not os.path.exists(prm):
            QMessageBox.critical(self, "Error", "PRMTOP file missing or not found.")
            return False
        if not pdb or not os.path.exists(pdb):
            QMessageBox.critical(self, "Error", "PDB file missing or not found.")
            return False
        return True

    def closeEvent(self, event):
        if self.process is not None and self.process.is_alive():
            self.process.terminate()
            self.process.join(1)
        if self.timer is not None:
            self.timer.stop()
        if self.progress_queue is not None:
            self.progress_queue.close()
        event.accept()