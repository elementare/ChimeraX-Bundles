 #vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

from chimerax.core.tools import ToolInstance
from chimerax.atomic import StructureSeq, Structure, selected_atoms, all_atoms, all_atomic_structures
from chimerax.core.commands import run
from os.path import expanduser
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QDialog
from PyQt5.QtCore import QThread, pyqtSlot, pyqtSignal
import chimerax as cx
import os
import pyKVFinder
import numpy as np
import sys

dialog = None

class _Default(object):
    def __init__(self):
        super(_Default, self).__init__()
        #######################
        ### Main Parameters ###
        #######################
        self.step = 0.0
        self.resolution = "Low"
        self.probe_in = 1.4
        self.probe_out = 4.0
        self.removal_distance = 2.4
        self.volume_cutoff = 5.0
        self.surface = "Molecular Surface (VdW)"
        self.cavity_representation = "Filtered"
        self.base_name = "output"
        self.output_dir_path = expanduser('~/KVFinderResults')
        self.region_option = "Default"
        #######################
        ### File Locations  ###
        #######################
        self.parKVFinder = None
        self.dictionary = None
        #######################
        ###  Search Space   ###
        #######################
        # Box Adjustment
        self.box_adjustment = False
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.min_x = 0.0
        self.max_x = 0.0
        self.min_y = 0.0
        self.max_y = 0.0
        self.min_z = 0.0
        self.max_z = 0.0
        self.angle1 = 0
        self.angle2 = 0
        self.padding = 3.5
        # Ligand Adjustment
        self.ligand_adjustment = False
        self.ligand_cutoff = 5.0


class KVFinder(ToolInstance):

    # Inheriting from ToolInstance makes us known to the ChimeraX tool mangager,
    # so we can be notified and take appropriate action when sessions are closed,
    # saved, or restored, and we will be listed among running tools and so on.
    #
    # If cleaning up is needed on finish, override the 'delete' method
    # but be sure to call 'delete' from the superclass at the end.

    SESSION_ENDURING = False    # Does this instance persist when session closes
    SESSION_SAVE = True         # We do save/restore in sessions
    #help = "help:user/tools/tutorial.html"
                                # Let ChimeraX know about our help page

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)

        _translate = QtCore.QCoreApplication.translate
        self.display_name = "KVFinder"
        self._default = _Default()
        self.region_option = self._default.region_option

        self.app = QtWidgets.QApplication(sys.argv)
        self.tool_window = QtWidgets.QMainWindow()
        self.tool_window.fill_context_menu = self.fill_context_menu
        self.tool_window.setWindowTitle("ChimeraX KVFinder (Qt)")
        self.ui = Ui_pyKVFinder()
        self.ui.setupUi(self.tool_window)  

        self.ui.debug = SampleGUI(self)
        self.ui.debug.setObjectName("debug")
        self.ui.tabs.addTab(self.ui.debug, "")

        self.ui.tabs.setTabText(self.ui.tabs.indexOf(self.ui.debug), _translate("pyKVFinder", "Debug"))
        # self.tool_window.adjustSize()
        self.tool_window.show()

        # Set box centers
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

        # Results
        self.results = None
        self.input_pdb = None
        self.ligand_pdb = None
        self.cavity_pdb = None

        self._connect_ui()

        # Restore Default Parameters
        self.restore(is_startup=True)



    def _connect_ui(self):
        
        # ScrollBars binded to QListWidgets in Descriptors
        scroll_bar_volume = QtWidgets.QScrollBar(self.tool_window)
        self.ui.volume_list.setVerticalScrollBar(scroll_bar_volume)
        scroll_bar_area = QtWidgets.QScrollBar(self.tool_window)
        self.ui.area_list.setVerticalScrollBar(scroll_bar_area)
        scroll_bar_residues = QtWidgets.QScrollBar(self.tool_window)
        self.ui.residues_list.setVerticalScrollBar(scroll_bar_residues)

        ########################
        ### Buttons Callback ###
        ########################

        # hook up QMainWindow buttons callbacks
        self.ui.button_run.clicked.connect(self.run)
        # ui.button_exit.clicked.connect(tw.close)
        self.ui.button_restore.clicked.connect(self.restore)
        # ui.button_grid.clicked.connect(self.show_grid)
        self.ui.button_save_parameters.clicked.connect(self.save_parameters)

        # hook up Refresh buttons callback
        self.ui.refresh_input.clicked.connect(lambda: self.refresh(self.ui.input))

        # hook up resolution-step CheckBox callbacks
        self.ui.resolution_label.clicked.connect(self.check_resolution)
        self.ui.step_size_label.clicked.connect(self.check_step_size)

        # Parts Button
        # self.ui.regionOption_rbtn1.toggled.connect(self._optionCheck)
        # self.ui.regionOption_rbtn2.toggled.connect(self._optionCheck)
        # self.ui.regionOption_rbtn3.toggled.connect(self._optionCheck)
        # self.ui.regionOption_rbtn4.toggled.connect(self._optionCheck)

        self.ui.groupButton.buttonClicked.connect(self._optionCheck)

        # hook up Browse buttons callbacks
        # ui.button_browse.clicked.connect(self.select_directory)
        # ui.button_browse2.clicked.connect(
        #     lambda: self.select_file(
        #         "Choose parKVFinder executable", self.parKVFinder, "*"
        #     )
        # )
        self.ui.button_browse3.clicked.connect(
            lambda: self.select_file(
                "Choose van der Waals radii dictionary", self.ui.dictionary, "*"
            )
        )
        self.ui.button_browse4.clicked.connect(
            lambda: self.select_file(
                "Choose KVFinder Results File",
                self.ui.results_file_entry,
                "KVFinder Results File (*.toml);;All files (*)",
            )
        )



        self.ui.button_exit.clicked.connect(self.tool_window.close)
    
    def _optionCheck(self, sender):
        rb = self.sender()

        if rb.isChecked():
            self.session.logger.info(f'You selected {rb.text()}')
            self.region_option = rb.text()

    def restore(self, is_startup=False) -> None:
        """
        Callback for the "Restore Default Values" button
        """
        #from pymol import cmd
        from PyQt5.QtWidgets import QMessageBox, QCheckBox
        """
        # Restore Results Tab
        if not is_startup:
            reply = QMessageBox(self)
            reply.setText("Also restore Results Visualization tab?")
            reply.setWindowTitle("Restore Values")
            reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            reply.setIcon(QMessageBox.Information)
            reply.checkbox = QCheckBox("Also remove input and ligand PDBs?")
            reply.layout = reply.layout()
            reply.layout.addWidget(reply.checkbox, 1, 2)
            if reply.exec_() == QMessageBox.Yes:
                # Remove cavities, residues and pdbs (input, ligand, cavity)
                cmd.delete("cavities")
                cmd.delete("residues")
                if self.input_pdb and reply.checkbox.isChecked():
                    cmd.delete(self.input_pdb)
                if self.ligand_pdb and reply.checkbox.isChecked():
                    cmd.delete(self.ligand_pdb)
                if self.cavity_pdb:
                    cmd.delete(self.cavity_pdb)
                results = self.input_pdb = self.ligand_pdb = self.cavity_pdb = None
                cmd.frame(1)

                # Clean results
                self.clean_results()
                self.results_file_entry.clear()
        """
        # Restore PDB and ligand input
        self.refresh(self.ui.input)
        self.refresh(self.ui.ligand)

        # Delete grid
        #cmd.delete("grid")

        ### Main tab ###
        self.ui.step_size_label.setChecked(False)
        self.ui.step_size.setValue(self._default.step)
        self.ui.step_size.setEnabled(False)
        self.ui.resolution_label.setChecked(True)
        self.ui.resolution.setCurrentText(self._default.resolution)
        self.ui.resolution.setEnabled(True)
        self.ui.base_name.setText(self._default.base_name)
        self.ui.probe_in.setValue(self._default.probe_in)
        self.ui.probe_out.setValue(self._default.probe_out)
        self.ui.volume_cutoff.setValue(self._default.volume_cutoff)
        self.ui.removal_distance.setValue(self._default.removal_distance)
        self.ui.surface.setCurrentText(self._default.surface)
        self.ui.cavity_representation.setCurrentText(self._default.cavity_representation)
        self.ui.output_dir_path.setText(self._default.output_dir_path)
        # self.ui.parKVFinder.setText(self._default.parKVFinder)
        self.ui.dictionary.setText(self._default.dictionary)

        ### Search Space Tab ###
        # Box Adjustment
        self.ui.box_adjustment.setChecked(self._default.box_adjustment)
        self.ui.padding.setValue(self._default.padding)
        #self.ui.delete_box()
        # Ligand Adjustment
        self.ui.ligand_adjustment.setChecked(self._default.ligand_adjustment)
        self.ui.ligand.clear()
        self.ui.ligand_cutoff.setValue(self._default.ligand_cutoff)

    def refresh(self, combo_box ) -> None:
        """
        Callback for the "Refresh" button
        """
        combo_box.clear()

        if combo_box == self.ui.input:
            pdbNames = all_atomic_structures(self.session).names
            if isinstance(pdbNames, np.ndarray):
                for item in pdbNames:
                    combo_box.addItem(item)
            else:
                print(f"{pdbNames}, {type(pdbNames)}")
        
        """
        combo_box.clear()
        for item in cmd.get_names("all"):
            if (
                cmd.get_type(item) == "object:molecule"
                and item != "box"
                and item != "grid"
                and item != "cavities"
                and item != "residues"
                and item[-16:] != ".KVFinder.output"
                and item != "target_exclusive"
            ):
                combo_box.addItem(item)
        """
        return    
    
    def run(self) -> None:
        import time
        self.ui.region
        atomic = self.extract_pdb_session()
        pass
    

    def save_parameters(self) -> None:

        # Create base directory
        basedir = os.path.join(self.ui.output_dir_path.text(), "KV_Files")
        if not os.path.isdir(basedir):
            os.mkdir(basedir)

        # Create base_name directory
        basedir = os.path.join(basedir, self.ui.base_name.text())
        if not os.path.isdir(basedir):
            os.mkdir(basedir)    

        # Save input pdb
        if self.ui.input.currentText() != "":
            for x in all_atomic_structures(self.session).names:
                if x == self.ui.input.currentText():
                    pdb = os.path.join(
                        os.path.join(basedir, f"{self.input.currentText()}.pdb")
                    )
                    #cmd.save(pdb, self.input.currentText(), 0, "pdb")
        else:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Error", "Select an input PDB!")
            return False   

    def cprint(self, text):
        return self.session.logger.info(text)


    def extract_pdb_session(self, selected=True):

        if selected:
            sel_atoms = selected_atoms(self.session)
        else:
            sel_atoms = all_atoms(self.session)

        self.cprint(f"Info: Selected Atoms {len(sel_atoms)}")

        atomNP = np.zeros(shape=(len(sel_atoms), 8), dtype='<U32')
        vdw = pyKVFinder.read_vdw()
        for i in range(0, len(sel_atoms)):
            atom = sel_atoms[i]
            residue_name, atom_name, atom_element = str(atom.residue.name).upper(), str(atom.name).upper(), str(atom.element).upper()
            if residue_name in vdw.keys() and atom_name in vdw[residue_name].keys():
                radius = vdw[residue_name][atom_name]
            else:
                radius = vdw["GEN"][atom_element]
                self.cprint(f"Warning: Atom {atom_name} of residue {residue_name} \  not found in dictionary.")
                self.cprint(f"Warning: Using generic atom {atom_element} \radius: {radius} \u00c5.")

            try:
                atomNP[i] = [str(atom.residue.number), str(atom.residue.chain)[1:], residue_name, atom_name, atom.coord[0], atom.coord[1], atom.coord[2], radius ]
            except:
                self.cprint(f"Problem to modify line {str(i)}: {str(atom)}")

        return atomNP       

    def check_resolution(self):
        if self.ui.resolution_label.isChecked():
            self.ui.resolution.setEnabled(True)
            self.ui.resolution.setCurrentText(self._default.resolution)
            self.ui.step_size_label.setChecked(False)
            self.ui.step_size.setEnabled(False)
            self.ui.step_size.setValue(self._default.step)
        else:
            self.ui.resolution.setEnabled(False)
            self.ui.resolution.setCurrentText("Off")
            self.ui.step_size_label.setChecked(True)
            self.ui.step_size.setEnabled(True)
            self.ui.step_size.setValue(0.6)

    def check_step_size(self):
        if self.ui.step_size_label.isChecked():
            self.ui.resolution_label.setChecked(False)
            self.ui.resolution.setEnabled(False)
            self.ui.resolution.setCurrentText("Off")
            self.ui.step_size.setEnabled(True)
            self.ui.step_size.setValue(0.6)
        else:
            self.ui.resolution_label.setChecked(True)
            self.ui.resolution.setEnabled(True)
            self.ui.resolution.setCurrentText(self._default.resolution)
            self.ui.step_size.setEnabled(False)
            self.ui.step_size.setValue(self._default.step)    


    def fill_context_menu(self, menu, x, y):
        # Add any tool-specific items to the given context menu (a QMenu instance).
        # The menu will then be automatically filled out with generic tool-related actions
        # (e.g. Hide Tool, Help, Dockable Tool, etc.) 
        #
        # The x,y args are the x() and y() values of QContextMenuEvent, in the rare case
        # where the items put in the menu depends on where in the tool interface the menu
        # was raised.
        from Qt.QtGui import QAction
        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(lambda *args: self.line_edit.clear())
        menu.addAction(clear_action)

        # We will be adding an item to the tool's context menu, so override
        # the default MainToolWindow fill_context_menu method
        self.tool_window.fill_context_menu = self.fill_context_menu

    def select_file(self, caption, entry, filters) -> None:
        """
        Callback for the "Browse ..." button
        Open a QFileDialog to select a file.
        """
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtCore import QDir

        # Get results file
        fname, _ = QFileDialog.getOpenFileName(
            self, caption=caption, directory=os.getcwd(), filter=filters
        )

        if fname:
            fname = QDir.toNativeSeparators(fname)
            if os.path.exists(fname):
                entry.setText(fname)

        return


class Ui_pyKVFinder(object):
    def setupUi(self, pyKVFinder):
        pyKVFinder.setObjectName("pyKVFinder")
        self.gui = QtWidgets.QWidget()
        self.gui.setObjectName("gui")
        self.gridLayout = QtWidgets.QGridLayout(self.gui)
        self.gridLayout.setContentsMargins(10, 10, 10, 10)
        self.gridLayout.setVerticalSpacing(10)
        self.gridLayout.setObjectName("gridLayout")
        self.dialog_separator = QtWidgets.QFrame(self.gui)
        self.dialog_separator.setFrameShape(QtWidgets.QFrame.HLine)
        self.dialog_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.dialog_separator.setObjectName("dialog_separator")
        self.gridLayout.addWidget(self.dialog_separator, 2, 0, 1, 1)
        self.dialog_buttons = QtWidgets.QHBoxLayout()
        self.dialog_buttons.setContentsMargins(20, -1, 20, -1)
        self.dialog_buttons.setSpacing(6)
        self.dialog_buttons.setObjectName("dialog_buttons")
        self.button_run = QtWidgets.QPushButton(self.gui)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.button_run.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.button_run)

        self.button_run.setSizePolicy(sizePolicy)
        self.button_run.setText("Run pyKVFinder")
        self.button_run.setObjectName("button_run")
        self.dialog_buttons.addWidget(self.button_run)
        self.button_grid = QtWidgets.QPushButton(self.gui)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.button_grid.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.button_grid)

        self.button_grid.setSizePolicy(sizePolicy)
        self.button_grid.setObjectName("button_grid")
        self.dialog_buttons.addWidget(self.button_grid)
        self.button_save_parameters = QtWidgets.QPushButton(self.gui)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.button_save_parameters.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.button_save_parameters)

        self.button_save_parameters.setSizePolicy(sizePolicy)
        self.button_save_parameters.setText("Save Parameters")
        self.button_save_parameters.setObjectName("button_save_parameters")
        self.dialog_buttons.addWidget(self.button_save_parameters)
        self.button_restore = QtWidgets.QPushButton(self.gui)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.button_restore.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.button_restore)

        self.button_restore.setSizePolicy(sizePolicy)
        self.button_restore.setObjectName("button_restore")
        self.dialog_buttons.addWidget(self.button_restore)
        self.button_exit = QtWidgets.QPushButton(self.gui)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.button_exit.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.button_exit)

        self.button_exit.setSizePolicy(sizePolicy)
        self.button_exit.setText("Exit")
        self.button_exit.setObjectName("button_exit")
        self.dialog_buttons.addWidget(self.button_exit)
        self.gridLayout.addLayout(self.dialog_buttons, 3, 0, 1, 1)
        self.tabs = QtWidgets.QTabWidget(self.gui)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.tabs.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.tabs)

        self.tabs.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.tabs.setFont(font)
        self.tabs.setObjectName("tabs")
        self.main = QtWidgets.QWidget()
        self.main.setObjectName("main")
        self.verticalLayout_8 = QtWidgets.QVBoxLayout(self.main)
        self.verticalLayout_8.setObjectName("verticalLayout_8")

        self.parameters = QtWidgets.QGroupBox(self.main)
        sizePolicy = self._setPolicy(self.parameters)
        self.parameters.setSizePolicy(sizePolicy)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)

        self.parameters.setFont(font)
        self.parameters.setObjectName("parameters")

        self.verticalLayout = QtWidgets.QVBoxLayout(self.parameters)
        self.verticalLayout.setSpacing(3)
        self.verticalLayout.setObjectName("verticalLayout")

        self.hframe1 = QtWidgets.QFrame(self.parameters)
        self.hframe1.setObjectName("hframe1")

        self.horizontalLayout_14 = QtWidgets.QHBoxLayout(self.hframe1)
        self.horizontalLayout_14.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_14.setObjectName("horizontalLayout_14")

        self.input_label = QtWidgets.QLabel(self.hframe1)
        sizePolicy = self._setPolicy(self.input_label)
        self.input_label.setSizePolicy(sizePolicy)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        
        self.input_label.setFont(font)
        self.input_label.setMouseTracking(False)
        self.input_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.input_label.setTextFormat(QtCore.Qt.PlainText)
        self.input_label.setObjectName("input_label")

        self.horizontalLayout_14.addWidget(self.input_label)

        self.input = QtWidgets.QComboBox(self.hframe1)
        sizePolicy = self._setPolicy(self.input)
        self.input.setSizePolicy(sizePolicy)
        self.input.setObjectName("input")

        self.horizontalLayout_14.addWidget(self.input)

        self.refresh_input = QtWidgets.QPushButton(self.hframe1)
        sizePolicy = self._setPolicy(self.refresh_input)
        self.refresh_input.setSizePolicy(sizePolicy)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)

        self.refresh_input.setFont(font)
        self.refresh_input.setObjectName("refresh_input")

        self.horizontalLayout_14.addWidget(self.refresh_input)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_14.addItem(spacerItem)

        self.verticalLayout.addWidget(self.hframe1)

        self.hframe1_5 = QtWidgets.QHBoxLayout()
        self.hframe1_5.setObjectName("hframe1_5")

        self.regionOption_frame = QtWidgets.QFrame(self.parameters)
        self.regionOption_frame.setObjectName("regionoption_frame")

        # self.regionOption_box = QtWidgets.QGroupBox("Parts of structure")
        # self.regionOption_box.setMinimumHeight(QtWidgets.QRadioButton().sizeHint().height()*4)
        

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(5)
        # sizePolicy.setHeightForWidth(self.regionOption_box.sizePolicy().hasHeightForWidth())
        # sizePolicy = self._setPolicy(self.regionOption_box)
        # self.regionOption_box.setSizePolicy(sizePolicy)

        self.hL_Option = QtWidgets.QHBoxLayout(self.regionOption_frame)  
        self.hL_Option.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.hL_Option.setObjectName("hL_Option")
        
    
        self.regionOption_label = QtWidgets.QLabel("Structure: ")
        sizePolicy = self._setPolicy(self.regionOption_label)
        self.regionOption_label.setSizePolicy(sizePolicy)      

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        
        self.regionOption_label.setFont(font)
        self.regionOption_label.setMouseTracking(False)
        self.regionOption_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.regionOption_label.setTextFormat(QtCore.Qt.PlainText)
        self.regionOption_label.setObjectName("regionOption_label")

        


        self.hL_Option.addWidget(self.regionOption_label)

        self.regionOption_rbtn1 = QtWidgets.QRadioButton("Default")
        self.regionOption_rbtn1.setChecked(True)
        self.regionOption_rbtn1.setAutoExclusive(True)
        self.regionOption_rbtn2  = QtWidgets.QRadioButton("Selected")
        self.regionOption_rbtn3 = QtWidgets.QRadioButton("Protein")
        self.regionOption_rbtn4  = QtWidgets.QRadioButton("All ligands without HOH")

        self.groupButton = QtWidgets.QButtonGroup()

        self.groupButton.addButton(self.regionOption_rbtn1)
        self.groupButton.addButton(self.regionOption_rbtn2)
        self.groupButton.addButton(self.regionOption_rbtn3)
        self.groupButton.addButton(self.regionOption_rbtn4)

        # self.hL_Option.addWidget(self.regionOption_rbtn1)
        # self.hL_Option.addWidget(self.regionOption_rbtn2)
        # self.hL_Option.addWidget(self.regionOption_rbtn3)
        # self.hL_Option.addWidget(self.regionOption_rbtn4)
        self.hL_Option.addWidget(self.groupButton)
        self.hL_Option.addStretch(1)

        # self.hL_Option.addWidget(self.regionOption_label

        # self.regionOption_box.setLayout(self.hL_Option)

        self.hframe1_5.addWidget(self.regionOption_frame)

        self.verticalLayout.addLayout(self.hframe1_5)

        self.hframe2 = QtWidgets.QHBoxLayout()
        self.hframe2.setObjectName("hframe2")

        self.resolution_frame = QtWidgets.QFrame(self.parameters)
        self.resolution_frame.setObjectName("resolution_frame")

        self.horizontalLayout_21 = QtWidgets.QHBoxLayout(self.resolution_frame)
        self.horizontalLayout_21.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_21.setObjectName("horizontalLayout_21")

        self.resolution_label = QtWidgets.QCheckBox(self.resolution_frame)
        self.resolution_label.setChecked(True)
        self.resolution_label.setObjectName("resolution_label")

        self.horizontalLayout_21.addWidget(self.resolution_label)

        self.resolution = QtWidgets.QComboBox(self.resolution_frame)
        self.resolution.setObjectName("resolution")
        self.resolution.addItem("")
        self.resolution.addItem("")
        self.resolution.addItem("")
        self.resolution.addItem("")

        self.horizontalLayout_21.addWidget(self.resolution)

        self.hframe2.addWidget(self.resolution_frame)
        self.step_size_frame = QtWidgets.QFrame(self.parameters)
        self.step_size_frame.setObjectName("step_size_frame")
        self.horizontalLayout_20 = QtWidgets.QHBoxLayout(self.step_size_frame)
        self.horizontalLayout_20.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_20.setObjectName("horizontalLayout_20")
        self.step_size_label = QtWidgets.QCheckBox(self.step_size_frame)
        self.step_size_label.setObjectName("step_size_label")
        self.horizontalLayout_20.addWidget(self.step_size_label)
        self.step_size = QtWidgets.QDoubleSpinBox(self.step_size_frame)

        sizePolicy = self._setPolicy(self.step_size)

        self.step_size.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.step_size.setFont(font)
        self.step_size.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.step_size.setDecimals(1)
        self.step_size.setMaximum(20.0)
        self.step_size.setSingleStep(0.1)
        self.step_size.setProperty("value", 0.0)
        self.step_size.setObjectName("step_size")
        self.horizontalLayout_20.addWidget(self.step_size)
        self.hframe2.addWidget(self.step_size_frame)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.hframe2.addItem(spacerItem1)
        self.verticalLayout.addLayout(self.hframe2)
        self.hframe3 = QtWidgets.QHBoxLayout()
        self.hframe3.setObjectName("hframe3")
        self.probe_in_frame = QtWidgets.QFrame(self.parameters)
        self.probe_in_frame.setObjectName("probe_in_frame")
        self.horizontalLayout_13 = QtWidgets.QHBoxLayout(self.probe_in_frame)
        self.horizontalLayout_13.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_13.setObjectName("horizontalLayout_13")
        self.probe_in_label = QtWidgets.QLabel(self.probe_in_frame)

        #sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        #sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.probe_in_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.probe_in_label)

        self.probe_in_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.probe_in_label.setFont(font)
        self.probe_in_label.setMouseTracking(True)
        self.probe_in_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.probe_in_label.setTextFormat(QtCore.Qt.RichText)
        self.probe_in_label.setObjectName("probe_in_label")
        self.horizontalLayout_13.addWidget(self.probe_in_label)
        self.probe_in = QtWidgets.QDoubleSpinBox(self.probe_in_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.probe_in.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.probe_in)

        self.probe_in.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.probe_in.setFont(font)
        self.probe_in.setDecimals(1)
        self.probe_in.setMaximum(5.0)
        self.probe_in.setSingleStep(0.1)
        self.probe_in.setProperty("value", 1.4)
        self.probe_in.setObjectName("probe_in")
        self.horizontalLayout_13.addWidget(self.probe_in)
        self.hframe3.addWidget(self.probe_in_frame)
        self.probe_out_frame = QtWidgets.QFrame(self.parameters)
        self.probe_out_frame.setObjectName("probe_out_frame")
        self.horizontalLayout_10 = QtWidgets.QHBoxLayout(self.probe_out_frame)
        self.horizontalLayout_10.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")
        self.probe_out_label = QtWidgets.QLabel(self.probe_out_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.probe_out_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.probe_out_label)

        self.probe_out_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.probe_out_label.setFont(font)
        self.probe_out_label.setMouseTracking(True)
        self.probe_out_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.probe_out_label.setTextFormat(QtCore.Qt.RichText)
        self.probe_out_label.setObjectName("probe_out_label")
        self.horizontalLayout_10.addWidget(self.probe_out_label)
        self.probe_out = QtWidgets.QDoubleSpinBox(self.probe_out_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.probe_out.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.probe_out)

        self.probe_out.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.probe_out.setFont(font)
        self.probe_out.setDecimals(1)
        self.probe_out.setMaximum(50.0)
        self.probe_out.setSingleStep(0.1)
        self.probe_out.setProperty("value", 4.0)
        self.probe_out.setObjectName("probe_out")
        self.horizontalLayout_10.addWidget(self.probe_out)
        self.hframe3.addWidget(self.probe_out_frame)
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.hframe3.addItem(spacerItem2)
        self.verticalLayout.addLayout(self.hframe3)
        self.hframe4_2 = QtWidgets.QHBoxLayout()
        self.hframe4_2.setObjectName("hframe4_2")
        self.removal_distance_frame = QtWidgets.QFrame(self.parameters)
        self.removal_distance_frame.setObjectName("removal_distance_frame")
        self.horizontalLayout_16 = QtWidgets.QHBoxLayout(self.removal_distance_frame)
        self.horizontalLayout_16.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_16.setObjectName("horizontalLayout_16")
        self.removal_distance_label = QtWidgets.QLabel(self.removal_distance_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.removal_distance_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.removal_distance_label)

        self.removal_distance_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.removal_distance_label.setFont(font)
        self.removal_distance_label.setMouseTracking(True)
        self.removal_distance_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.removal_distance_label.setTextFormat(QtCore.Qt.RichText)
        self.removal_distance_label.setObjectName("removal_distance_label")
        self.horizontalLayout_16.addWidget(self.removal_distance_label)
        self.removal_distance = QtWidgets.QDoubleSpinBox(self.removal_distance_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.removal_distance.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.removal_distance)

        self.removal_distance.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.removal_distance.setFont(font)
        self.removal_distance.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.removal_distance.setDecimals(1)
        self.removal_distance.setMaximum(10.0)
        self.removal_distance.setSingleStep(0.1)
        self.removal_distance.setProperty("value", 2.4)
        self.removal_distance.setObjectName("removal_distance")
        self.horizontalLayout_16.addWidget(self.removal_distance)
        self.hframe4_2.addWidget(self.removal_distance_frame)
        self.volume_cutoff_frame = QtWidgets.QFrame(self.parameters)
        self.volume_cutoff_frame.setObjectName("volume_cutoff_frame")
        self.horizontalLayout_17 = QtWidgets.QHBoxLayout(self.volume_cutoff_frame)
        self.horizontalLayout_17.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_17.setObjectName("horizontalLayout_17")
        self.volume_cutoff_label = QtWidgets.QLabel(self.volume_cutoff_frame)
        
        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.volume_cutoff_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.volume_cutoff_label)

        self.volume_cutoff_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.volume_cutoff_label.setFont(font)
        self.volume_cutoff_label.setMouseTracking(True)
        self.volume_cutoff_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.volume_cutoff_label.setTextFormat(QtCore.Qt.RichText)
        self.volume_cutoff_label.setObjectName("volume_cutoff_label")
        self.horizontalLayout_17.addWidget(self.volume_cutoff_label)
        self.volume_cutoff = QtWidgets.QDoubleSpinBox(self.volume_cutoff_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.volume_cutoff.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.volume_cutoff)

        self.volume_cutoff.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.volume_cutoff.setFont(font)
        self.volume_cutoff.setDecimals(1)
        self.volume_cutoff.setMaximum(1000000000.0)
        self.volume_cutoff.setSingleStep(1.0)
        self.volume_cutoff.setProperty("value", 5.0)
        self.volume_cutoff.setObjectName("volume_cutoff")
        self.horizontalLayout_17.addWidget(self.volume_cutoff)
        self.hframe4_2.addWidget(self.volume_cutoff_frame)
        spacerItem3 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.hframe4_2.addItem(spacerItem3)
        self.verticalLayout.addLayout(self.hframe4_2)
        self.hframe_5 = QtWidgets.QHBoxLayout()
        self.hframe_5.setObjectName("hframe_5")
        self.surface_representation_frame = QtWidgets.QFrame(self.parameters)
        self.surface_representation_frame.setObjectName("surface_representation_frame")
        self.horizontalLayout_26 = QtWidgets.QHBoxLayout(self.surface_representation_frame)
        self.horizontalLayout_26.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_26.setObjectName("horizontalLayout_26")
        self.surface_label = QtWidgets.QLabel(self.surface_representation_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.surface_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.surface_label)

        self.surface_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.surface_label.setFont(font)
        self.surface_label.setMouseTracking(True)
        self.surface_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.surface_label.setTextFormat(QtCore.Qt.RichText)
        self.surface_label.setObjectName("surface_label")
        self.horizontalLayout_26.addWidget(self.surface_label)
        self.surface = QtWidgets.QComboBox(self.surface_representation_frame)
        self.surface.setObjectName("surface")
        self.surface.addItem("")
        self.surface.addItem("")
        self.horizontalLayout_26.addWidget(self.surface)
        self.hframe_5.addWidget(self.surface_representation_frame)
        self.cavity_representation_frame = QtWidgets.QFrame(self.parameters)
        self.cavity_representation_frame.setObjectName("cavity_representation_frame")
        self.horizontalLayout_11 = QtWidgets.QHBoxLayout(self.cavity_representation_frame)
        self.horizontalLayout_11.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_11.setObjectName("horizontalLayout_11")
        self.cavity_representation_label = QtWidgets.QLabel(self.cavity_representation_frame)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.cavity_representation_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.cavity_representation_label)

        self.cavity_representation_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.cavity_representation_label.setFont(font)
        self.cavity_representation_label.setMouseTracking(True)
        self.cavity_representation_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.cavity_representation_label.setTextFormat(QtCore.Qt.RichText)
        self.cavity_representation_label.setObjectName("cavity_representation_label")
        self.horizontalLayout_11.addWidget(self.cavity_representation_label)
        self.cavity_representation = QtWidgets.QComboBox(self.cavity_representation_frame)
        self.cavity_representation.setObjectName("cavity_representation")
        self.cavity_representation.addItem("")
        self.cavity_representation.addItem("")
        self.horizontalLayout_11.addWidget(self.cavity_representation)
        self.hframe_5.addWidget(self.cavity_representation_frame)
        spacerItem4 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.hframe_5.addItem(spacerItem4)
        self.verticalLayout.addLayout(self.hframe_5)
        self.hframe6_2 = QtWidgets.QFrame(self.parameters)
        self.hframe6_2.setObjectName("hframe6_2")
        self.horizontalLayout_15 = QtWidgets.QHBoxLayout(self.hframe6_2)
        self.horizontalLayout_15.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_15.setObjectName("horizontalLayout_15")
        self.output_base_name_label = QtWidgets.QLabel(self.hframe6_2)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.output_base_name_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.output_base_name_label)

        self.output_base_name_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.output_base_name_label.setFont(font)
        self.output_base_name_label.setMouseTracking(False)
        self.output_base_name_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.output_base_name_label.setTextFormat(QtCore.Qt.PlainText)
        self.output_base_name_label.setObjectName("output_base_name_label")
        self.horizontalLayout_15.addWidget(self.output_base_name_label)
        self.base_name = QtWidgets.QLineEdit(self.hframe6_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.base_name.setFont(font)
        self.base_name.setText("output")
        self.base_name.setCursorMoveStyle(QtCore.Qt.VisualMoveStyle)
        self.base_name.setClearButtonEnabled(True)
        self.base_name.setObjectName("base_name")
        self.horizontalLayout_15.addWidget(self.base_name)
        spacerItem5 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_15.addItem(spacerItem5)
        self.verticalLayout.addWidget(self.hframe6_2)
        self.hframe7_2 = QtWidgets.QFrame(self.parameters)
        self.hframe7_2.setObjectName("hframe7_2")
        self.horizontalLayout_12 = QtWidgets.QHBoxLayout(self.hframe7_2)
        self.horizontalLayout_12.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_12.setObjectName("horizontalLayout_12")

        self.output_dir_label = QtWidgets.QLabel(self.hframe7_2)
        sizePolicy = self._setPolicy(self.output_dir_label)
        self.output_dir_label.setSizePolicy(sizePolicy)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)

        self.output_dir_label.setFont(font)
        self.output_dir_label.setMouseTracking(False)
        self.output_dir_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.output_dir_label.setTextFormat(QtCore.Qt.PlainText)
        self.output_dir_label.setObjectName("output_dir_label")
        self.horizontalLayout_12.addWidget(self.output_dir_label)
        self.output_dir_path = QtWidgets.QLineEdit(self.hframe7_2)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)

        self.output_dir_path.setFont(font)
        self.output_dir_path.setText("")
        self.output_dir_path.setEchoMode(QtWidgets.QLineEdit.Normal)
        self.output_dir_path.setReadOnly(True)
        self.output_dir_path.setClearButtonEnabled(False)
        self.output_dir_path.setObjectName("output_dir_path")

        self.horizontalLayout_12.addWidget(self.output_dir_path)
        self.button_browse = QtWidgets.QPushButton(self.hframe7_2)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)

        self.button_browse.setFont(font)
        self.button_browse.setText("Browse...")
        self.button_browse.setObjectName("button_browse")

        self.horizontalLayout_12.addWidget(self.button_browse)

        self.verticalLayout.addWidget(self.hframe7_2)
        self.verticalLayout_8.addWidget(self.parameters)

        self.file_locations = QtWidgets.QGroupBox(self.main)
        self.file_locations.setObjectName("file_locations")

        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.file_locations)
        self.verticalLayout_3.setSpacing(3)
        self.verticalLayout_3.setObjectName("verticalLayout_3")

        self.hframe5_2 = QtWidgets.QFrame(self.file_locations)
        self.hframe5_2.setObjectName("hframe5_2")

        self.horizontalLayout_24 = QtWidgets.QHBoxLayout(self.hframe5_2)
        self.horizontalLayout_24.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_24.setObjectName("horizontalLayout_24")
        
        self.verticalLayout_3.addWidget(self.hframe5_2)

        self.hframe5_3 = QtWidgets.QFrame(self.file_locations)
        self.hframe5_3.setObjectName("hframe5_3")

        self.horizontalLayout_25 = QtWidgets.QHBoxLayout(self.hframe5_3)
        self.horizontalLayout_25.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_25.setObjectName("horizontalLayout_25")

        self.dictionary_label = QtWidgets.QLabel(self.hframe5_3)

        sizePolicy = self._setPolicy(self.dictionary_label)

        self.dictionary_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.dictionary_label.setFont(font)
        self.dictionary_label.setMouseTracking(False)
        self.dictionary_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.dictionary_label.setTextFormat(QtCore.Qt.PlainText)
        self.dictionary_label.setObjectName("dictionary_label")
        self.horizontalLayout_25.addWidget(self.dictionary_label)
        self.dictionary = QtWidgets.QLineEdit(self.hframe5_3)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.dictionary.setFont(font)
        self.dictionary.setText("")
        self.dictionary.setEchoMode(QtWidgets.QLineEdit.Normal)
        self.dictionary.setReadOnly(True)
        self.dictionary.setClearButtonEnabled(False)
        self.dictionary.setObjectName("dictionary")
        self.horizontalLayout_25.addWidget(self.dictionary)
        self.button_browse3 = QtWidgets.QPushButton(self.hframe5_3)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.button_browse3.setFont(font)
        self.button_browse3.setText("Browse...")
        self.button_browse3.setObjectName("button_browse3")
        self.horizontalLayout_25.addWidget(self.button_browse3)
        self.verticalLayout_3.addWidget(self.hframe5_3)
        self.verticalLayout_8.addWidget(self.file_locations)
        spacerItem6 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_8.addItem(spacerItem6)
        self.tabs.addTab(self.main, "")
        self.search_space = QtWidgets.QWidget()
        self.search_space.setObjectName("search_space")
        self.gridLayout_4 = QtWidgets.QGridLayout(self.search_space)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.box_adjustment = QtWidgets.QGroupBox(self.search_space)
        self.box_adjustment.setCheckable(True)
        self.box_adjustment.setChecked(True)
        self.box_adjustment.setObjectName("box_adjustment")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.box_adjustment)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.hframe12 = QtWidgets.QHBoxLayout()
        self.hframe12.setObjectName("hframe12")
        self.min_y_label = QtWidgets.QLabel(self.box_adjustment)
        self.min_y_label.setTextFormat(QtCore.Qt.RichText)
        self.min_y_label.setAlignment(QtCore.Qt.AlignCenter)
        self.min_y_label.setObjectName("min_y_label")
        self.hframe12.addWidget(self.min_y_label)
        self.min_y = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.min_y.setEnabled(False)
        self.min_y.setDecimals(1)
        self.min_y.setMaximum(50.0)
        self.min_y.setSingleStep(0.1)
        self.min_y.setObjectName("min_y")
        self.hframe12.addWidget(self.min_y)
        self.gridLayout_3.addLayout(self.hframe12, 6, 0, 1, 1)
        self.hframe13 = QtWidgets.QHBoxLayout()
        self.hframe13.setObjectName("hframe13")
        self.min_z_label = QtWidgets.QLabel(self.box_adjustment)
        self.min_z_label.setTextFormat(QtCore.Qt.RichText)
        self.min_z_label.setAlignment(QtCore.Qt.AlignCenter)
        self.min_z_label.setObjectName("min_z_label")
        self.hframe13.addWidget(self.min_z_label)
        self.min_z = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.min_z.setEnabled(False)
        self.min_z.setDecimals(1)
        self.min_z.setMaximum(50.0)
        self.min_z.setSingleStep(0.1)
        self.min_z.setObjectName("min_z")
        self.hframe13.addWidget(self.min_z)
        self.gridLayout_3.addLayout(self.hframe13, 8, 0, 1, 1)
        self.hframe15 = QtWidgets.QHBoxLayout()
        self.hframe15.setObjectName("hframe15")
        self.angle1_label = QtWidgets.QLabel(self.box_adjustment)
        self.angle1_label.setTextFormat(QtCore.Qt.RichText)
        self.angle1_label.setAlignment(QtCore.Qt.AlignCenter)
        self.angle1_label.setObjectName("angle1_label")
        self.hframe15.addWidget(self.angle1_label)
        self.angle1 = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.angle1.setEnabled(False)
        self.angle1.setDecimals(0)
        self.angle1.setMaximum(180.0)
        self.angle1.setSingleStep(1.0)
        self.angle1.setObjectName("angle1")
        self.hframe15.addWidget(self.angle1)
        self.gridLayout_3.addLayout(self.hframe15, 10, 0, 1, 1)
        self.hframe7 = QtWidgets.QHBoxLayout()
        self.hframe7.setObjectName("hframe7")
        self.button_draw_box = QtWidgets.QPushButton(self.box_adjustment)
        self.button_draw_box.setObjectName("button_draw_box")
        self.hframe7.addWidget(self.button_draw_box)
        self.button_delete_box = QtWidgets.QPushButton(self.box_adjustment)
        self.button_delete_box.setObjectName("button_delete_box")
        self.hframe7.addWidget(self.button_delete_box)
        self.button_redraw_box = QtWidgets.QPushButton(self.box_adjustment)
        self.button_redraw_box.setEnabled(False)
        self.button_redraw_box.setObjectName("button_redraw_box")
        self.hframe7.addWidget(self.button_redraw_box)
        self.gridLayout_3.addLayout(self.hframe7, 2, 0, 1, 1)
        self.hframe9 = QtWidgets.QHBoxLayout()
        self.hframe9.setObjectName("hframe9")
        self.min_x_label = QtWidgets.QLabel(self.box_adjustment)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.min_x_label.setFont(font)
        self.min_x_label.setStyleSheet("")
        self.min_x_label.setTextFormat(QtCore.Qt.RichText)
        self.min_x_label.setAlignment(QtCore.Qt.AlignCenter)
        self.min_x_label.setObjectName("min_x_label")
        self.hframe9.addWidget(self.min_x_label)
        self.min_x = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.min_x.setEnabled(False)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.min_x.setFont(font)
        self.min_x.setStyleSheet("")
        self.min_x.setDecimals(1)
        self.min_x.setMaximum(50.0)
        self.min_x.setSingleStep(0.1)
        self.min_x.setObjectName("min_x")
        self.hframe9.addWidget(self.min_x)
        self.gridLayout_3.addLayout(self.hframe9, 4, 0, 1, 1)
        self.hframe6 = QtWidgets.QHBoxLayout()
        self.hframe6.setObjectName("hframe6")
        self.box_adjustment_label = QtWidgets.QLabel(self.box_adjustment)
        self.box_adjustment_label.setEnabled(True)

        sizePolicy = self._setPolicy(self.box_adjustment_label)

        self.box_adjustment_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.box_adjustment_label.setFont(font)
        self.box_adjustment_label.setMouseTracking(False)
        self.box_adjustment_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.box_adjustment_label.setTextFormat(QtCore.Qt.PlainText)
        self.box_adjustment_label.setAlignment(QtCore.Qt.AlignCenter)
        self.box_adjustment_label.setObjectName("box_adjustment_label")
        self.hframe6.addWidget(self.box_adjustment_label)
        self.button_box_adjustment_help = QtWidgets.QToolButton(self.box_adjustment)
        self.button_box_adjustment_help.setMinimumSize(QtCore.QSize(30, 26))
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setItalic(False)
        font.setWeight(75)
        font.setKerning(True)
        self.button_box_adjustment_help.setFont(font)
        self.button_box_adjustment_help.setCursor(QtGui.QCursor(QtCore.Qt.WhatsThisCursor))
        self.button_box_adjustment_help.setFocusPolicy(QtCore.Qt.NoFocus)
        self.button_box_adjustment_help.setObjectName("button_box_adjustment_help")
        self.hframe6.addWidget(self.button_box_adjustment_help)
        self.gridLayout_3.addLayout(self.hframe6, 1, 0, 1, 1)
        self.hframe16 = QtWidgets.QHBoxLayout()
        self.hframe16.setObjectName("hframe16")
        self.angle2_label = QtWidgets.QLabel(self.box_adjustment)
        self.angle2_label.setTextFormat(QtCore.Qt.RichText)
        self.angle2_label.setAlignment(QtCore.Qt.AlignCenter)
        self.angle2_label.setObjectName("angle2_label")
        self.hframe16.addWidget(self.angle2_label)
        self.angle2 = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.angle2.setEnabled(False)
        self.angle2.setDecimals(0)
        self.angle2.setMaximum(180.0)
        self.angle2.setSingleStep(1.0)
        self.angle2.setObjectName("angle2")
        self.hframe16.addWidget(self.angle2)
        self.gridLayout_3.addLayout(self.hframe16, 11, 0, 1, 1)
        self.hframe10 = QtWidgets.QHBoxLayout()
        self.hframe10.setObjectName("hframe10")
        self.max_x_label = QtWidgets.QLabel(self.box_adjustment)
        self.max_x_label.setTextFormat(QtCore.Qt.RichText)
        self.max_x_label.setAlignment(QtCore.Qt.AlignCenter)
        self.max_x_label.setObjectName("max_x_label")
        self.hframe10.addWidget(self.max_x_label)
        self.max_x = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.max_x.setEnabled(False)
        self.max_x.setDecimals(1)
        self.max_x.setMaximum(50.0)
        self.max_x.setSingleStep(0.1)
        self.max_x.setObjectName("max_x")
        self.hframe10.addWidget(self.max_x)
        self.gridLayout_3.addLayout(self.hframe10, 5, 0, 1, 1)
        self.hframe14 = QtWidgets.QHBoxLayout()
        self.hframe14.setObjectName("hframe14")
        self.max_z_label = QtWidgets.QLabel(self.box_adjustment)
        self.max_z_label.setTextFormat(QtCore.Qt.RichText)
        self.max_z_label.setAlignment(QtCore.Qt.AlignCenter)
        self.max_z_label.setObjectName("max_z_label")
        self.hframe14.addWidget(self.max_z_label)
        self.max_z = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.max_z.setEnabled(False)
        self.max_z.setDecimals(1)
        self.max_z.setMaximum(50.0)
        self.max_z.setSingleStep(0.1)
        self.max_z.setObjectName("max_z")
        self.hframe14.addWidget(self.max_z)
        self.gridLayout_3.addLayout(self.hframe14, 9, 0, 1, 1)
        self.hframe11 = QtWidgets.QHBoxLayout()
        self.hframe11.setObjectName("hframe11")
        self.max_y_label = QtWidgets.QLabel(self.box_adjustment)
        self.max_y_label.setTextFormat(QtCore.Qt.RichText)
        self.max_y_label.setAlignment(QtCore.Qt.AlignCenter)
        self.max_y_label.setObjectName("max_y_label")
        self.hframe11.addWidget(self.max_y_label)
        self.max_y = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.max_y.setEnabled(False)
        self.max_y.setDecimals(1)
        self.max_y.setMaximum(50.0)
        self.max_y.setSingleStep(0.1)
        self.max_y.setObjectName("max_y")
        self.hframe11.addWidget(self.max_y)
        self.gridLayout_3.addLayout(self.hframe11, 7, 0, 1, 1)
        self.hframe8 = QtWidgets.QHBoxLayout()
        self.hframe8.setObjectName("hframe8")
        self.padding_label = QtWidgets.QLabel(self.box_adjustment)
        self.padding_label.setTextFormat(QtCore.Qt.RichText)
        self.padding_label.setAlignment(QtCore.Qt.AlignCenter)
        self.padding_label.setObjectName("padding_label")
        self.hframe8.addWidget(self.padding_label)
        self.padding = QtWidgets.QDoubleSpinBox(self.box_adjustment)
        self.padding.setDecimals(1)
        self.padding.setMaximum(10.0)
        self.padding.setSingleStep(0.1)
        self.padding.setProperty("value", 3.5)
        self.padding.setObjectName("padding")
        self.hframe8.addWidget(self.padding)
        self.gridLayout_3.addLayout(self.hframe8, 3, 0, 1, 1)
        spacerItem7 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout_3.addItem(spacerItem7, 12, 0, 1, 1)
        self.gridLayout_4.addWidget(self.box_adjustment, 0, 0, 1, 1)
        self.ligand_adjustment = QtWidgets.QGroupBox(self.search_space)
        self.ligand_adjustment.setEnabled(True)
        self.ligand_adjustment.setCheckable(True)
        self.ligand_adjustment.setChecked(True)
        self.ligand_adjustment.setObjectName("ligand_adjustment")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.ligand_adjustment)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.hframe17 = QtWidgets.QFrame(self.ligand_adjustment)
        self.hframe17.setObjectName("hframe17")
        self.horizontalLayout_18 = QtWidgets.QHBoxLayout(self.hframe17)
        self.horizontalLayout_18.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_18.setObjectName("horizontalLayout_18")
        self.ligand_label = QtWidgets.QLabel(self.hframe17)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.ligand_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.ligand_label)

        self.ligand_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.ligand_label.setFont(font)
        self.ligand_label.setMouseTracking(False)
        self.ligand_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.ligand_label.setTextFormat(QtCore.Qt.PlainText)
        self.ligand_label.setObjectName("ligand_label")
        self.horizontalLayout_18.addWidget(self.ligand_label)
        self.ligand = QtWidgets.QComboBox(self.hframe17)
        self.ligand.setObjectName("ligand")
        self.horizontalLayout_18.addWidget(self.ligand)
        self.refresh_ligand = QtWidgets.QPushButton(self.hframe17)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.refresh_ligand.sizePolicy().hasHeightForWidth())
        self.refresh_ligand.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.refresh_ligand.setFont(font)
        self.refresh_ligand.setObjectName("refresh_ligand")
        self.horizontalLayout_18.addWidget(self.refresh_ligand)
        self.verticalLayout_2.addWidget(self.hframe17)
        self.hframe18 = QtWidgets.QFrame(self.ligand_adjustment)
        self.hframe18.setObjectName("hframe18")
        self.horizontalLayout_19 = QtWidgets.QHBoxLayout(self.hframe18)
        self.horizontalLayout_19.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.horizontalLayout_19.setObjectName("horizontalLayout_19")
        self.ligand_cutoff_label = QtWidgets.QLabel(self.hframe18)
        self.ligand_cutoff_label.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.ligand_cutoff_label.sizePolicy().hasHeightForWidth())
        self.ligand_cutoff_label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.ligand_cutoff_label.setFont(font)
        self.ligand_cutoff_label.setMouseTracking(True)
        self.ligand_cutoff_label.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.ligand_cutoff_label.setTextFormat(QtCore.Qt.RichText)
        self.ligand_cutoff_label.setObjectName("ligand_cutoff_label")
        self.horizontalLayout_19.addWidget(self.ligand_cutoff_label)
        self.ligand_cutoff = QtWidgets.QDoubleSpinBox(self.hframe18)
        self.ligand_cutoff.setEnabled(True)

        sizePolicy = self._setPolicy(self.ligand_cutoff)

        self.ligand_cutoff.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.ligand_cutoff.setFont(font)
        self.ligand_cutoff.setDecimals(1)
        self.ligand_cutoff.setMaximum(1000000000.0)
        self.ligand_cutoff.setSingleStep(0.1)
        self.ligand_cutoff.setProperty("value", 5.0)
        self.ligand_cutoff.setObjectName("ligand_cutoff")
        self.horizontalLayout_19.addWidget(self.ligand_cutoff)
        spacerItem8 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_19.addItem(spacerItem8)
        self.verticalLayout_2.addWidget(self.hframe18)
        spacerItem9 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem9)
        self.gridLayout_4.addWidget(self.ligand_adjustment, 0, 1, 1, 1)
        self.tabs.addTab(self.search_space, "")
        self.results = QtWidgets.QWidget()
        self.results.setObjectName("results")
        self.gridLayout_5 = QtWidgets.QGridLayout(self.results)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.show_descriptors = QtWidgets.QHBoxLayout()
        self.show_descriptors.setObjectName("show_descriptors")
        self.show_descriptors_label = QtWidgets.QLabel(self.results)

        sizePolicy = self._setPolicy(self.show_descriptors_label)

        self.show_descriptors_label.setSizePolicy(sizePolicy)
        self.show_descriptors_label.setObjectName("show_descriptors_label")
        self.show_descriptors.addWidget(self.show_descriptors_label)
        self.default_view = QtWidgets.QRadioButton(self.results)

        sizePolicy = self._setPolicy(self.default_view)

        self.default_view.setSizePolicy(sizePolicy)
        self.default_view.setChecked(True)
        self.default_view.setAutoExclusive(True)
        self.default_view.setObjectName("default_view")
        self.show_descriptors.addWidget(self.default_view)
        self.depth_view = QtWidgets.QRadioButton(self.results)

        sizePolicy = self._setPolicy(self.depth_view)

        self.depth_view.setSizePolicy(sizePolicy)
        self.depth_view.setAcceptDrops(False)
        self.depth_view.setObjectName("depth_view")
        self.show_descriptors.addWidget(self.depth_view)
        self.hydropathy_view = QtWidgets.QRadioButton(self.results)
           
        sizePolicy = self._setPolicy(self.hydropathy_view)

        self.hydropathy_view.setSizePolicy(sizePolicy)
        self.hydropathy_view.setObjectName("hydropathy_view")
        self.show_descriptors.addWidget(self.hydropathy_view)
        spacerItem10 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.show_descriptors.addItem(spacerItem10)
        self.gridLayout_5.addLayout(self.show_descriptors, 1, 0, 1, 1)
        self.results_information = QtWidgets.QGroupBox(self.results)
        self.results_information.setObjectName("results_information")
        self.verticalLayout_7 = QtWidgets.QVBoxLayout(self.results_information)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.hframe26 = QtWidgets.QHBoxLayout()
        self.hframe26.setObjectName("hframe26")
        self.results_file_label = QtWidgets.QLabel(self.results_information)

        sizePolicy = self._setPolicy(self.results_file_label)

        self.results_file_label.setSizePolicy(sizePolicy)
        self.results_file_label.setObjectName("results_file_label")
        self.hframe26.addWidget(self.results_file_label)
        self.results_file_entry = QtWidgets.QLineEdit(self.results_information)
        self.results_file_entry.setReadOnly(True)
        self.results_file_entry.setObjectName("results_file_entry")
        self.hframe26.addWidget(self.results_file_entry)
        self.button_browse4 = QtWidgets.QPushButton(self.results_information)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.button_browse4.setFont(font)
        self.button_browse4.setText("Browse...")
        self.button_browse4.setObjectName("button_browse4")
        self.hframe26.addWidget(self.button_browse4)
        self.button_load_results = QtWidgets.QPushButton(self.results_information)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        font.setKerning(True)
        self.button_load_results.setFont(font)
        self.button_load_results.setText("Load")
        self.button_load_results.setObjectName("button_load_results")
        self.hframe26.addWidget(self.button_load_results)
        self.verticalLayout_7.addLayout(self.hframe26)
        self.hframe27 = QtWidgets.QHBoxLayout()
        self.hframe27.setObjectName("hframe27")
        self.input_file_label = QtWidgets.QLabel(self.results_information)
        self.input_file_label.setObjectName("input_file_label")
        self.hframe27.addWidget(self.input_file_label)
        self.input_file_entry = QtWidgets.QLineEdit(self.results_information)
        self.input_file_entry.setReadOnly(True)
        self.input_file_entry.setObjectName("input_file_entry")
        self.hframe27.addWidget(self.input_file_entry)
        self.verticalLayout_7.addLayout(self.hframe27)
        self.hframe28 = QtWidgets.QHBoxLayout()
        self.hframe28.setObjectName("hframe28")
        self.ligand_file_label = QtWidgets.QLabel(self.results_information)
        self.ligand_file_label.setObjectName("ligand_file_label")
        self.hframe28.addWidget(self.ligand_file_label)
        self.ligand_file_entry = QtWidgets.QLineEdit(self.results_information)
        self.ligand_file_entry.setReadOnly(True)
        self.ligand_file_entry.setObjectName("ligand_file_entry")
        self.hframe28.addWidget(self.ligand_file_entry)
        self.verticalLayout_7.addLayout(self.hframe28)
        self.hframe29 = QtWidgets.QHBoxLayout()
        self.hframe29.setObjectName("hframe29")
        self.cavities_file_label = QtWidgets.QLabel(self.results_information)
        self.cavities_file_label.setObjectName("cavities_file_label")
        self.hframe29.addWidget(self.cavities_file_label)
        self.cavities_file_entry = QtWidgets.QLineEdit(self.results_information)
        self.cavities_file_entry.setReadOnly(True)
        self.cavities_file_entry.setObjectName("cavities_file_entry")
        self.hframe29.addWidget(self.cavities_file_entry)
        self.verticalLayout_7.addLayout(self.hframe29)
        self.hframe30 = QtWidgets.QHBoxLayout()
        self.hframe30.setObjectName("hframe30")
        self.step_size_label_2 = QtWidgets.QLabel(self.results_information)
        self.step_size_label_2.setObjectName("step_size_label_2")
        self.hframe30.addWidget(self.step_size_label_2)
        self.step_size_entry = QtWidgets.QLineEdit(self.results_information)

        sizePolicy = self._setPolicy(self.step_size_entry)

        self.step_size_entry.setSizePolicy(sizePolicy)
        self.step_size_entry.setMaximumSize(QtCore.QSize(50, 16777215))
        self.step_size_entry.setText("")
        self.step_size_entry.setMaxLength(10)
        self.step_size_entry.setAlignment(QtCore.Qt.AlignCenter)
        self.step_size_entry.setReadOnly(True)
        self.step_size_entry.setObjectName("step_size_entry")
        self.hframe30.addWidget(self.step_size_entry)
        spacerItem11 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.hframe30.addItem(spacerItem11)
        self.verticalLayout_7.addLayout(self.hframe30)
        self.gridLayout_5.addWidget(self.results_information, 0, 0, 1, 1)
        self.descriptors = QtWidgets.QGroupBox(self.results)

        sizePolicy = self._setPolicy(self.descriptors)

        self.descriptors.setSizePolicy(sizePolicy)
        self.descriptors.setObjectName("descriptors")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.descriptors)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.vframe1 = QtWidgets.QVBoxLayout()
        self.vframe1.setObjectName("vframe1")
        self.volume_label = QtWidgets.QLabel(self.descriptors)

        sizePolicy = self._setPolicy(self.volume_label)

        self.volume_label.setSizePolicy(sizePolicy)
        self.volume_label.setAlignment(QtCore.Qt.AlignCenter)
        self.volume_label.setObjectName("volume_label")
        self.vframe1.addWidget(self.volume_label)
        self.volume_list = QtWidgets.QListWidget(self.descriptors)

        sizePolicy = self._setPolicy(self.volume_list)

        self.volume_list.setSizePolicy(sizePolicy)
        self.volume_list.setMinimumSize(QtCore.QSize(153, 0))
        self.volume_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.volume_list.setObjectName("volume_list")
        self.vframe1.addWidget(self.volume_list)
        self.horizontalLayout.addLayout(self.vframe1)
        self.vframe2 = QtWidgets.QVBoxLayout()
        self.vframe2.setObjectName("vframe2")
        self.area_label = QtWidgets.QLabel(self.descriptors)

        sizePolicy = self._setPolicy(self.area_label)

        self.area_label.setSizePolicy(sizePolicy)
        self.area_label.setAlignment(QtCore.Qt.AlignCenter)
        self.area_label.setObjectName("area_label")
        self.vframe2.addWidget(self.area_label)
        self.area_list = QtWidgets.QListWidget(self.descriptors)

        sizePolicy = self._setPolicy(self.area_list)

        self.area_list.setSizePolicy(sizePolicy)
        self.area_list.setMinimumSize(QtCore.QSize(153, 0))
        self.area_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.area_list.setObjectName("area_list")
        self.vframe2.addWidget(self.area_list)
        self.horizontalLayout.addLayout(self.vframe2)
        self.vframe4 = QtWidgets.QVBoxLayout()
        self.vframe4.setObjectName("vframe4")
        self.avg_depth_label = QtWidgets.QLabel(self.descriptors)
        self.avg_depth_label.setAlignment(QtCore.Qt.AlignCenter)
        self.avg_depth_label.setObjectName("avg_depth_label")
        self.vframe4.addWidget(self.avg_depth_label)
        self.avg_depth_list = QtWidgets.QListWidget(self.descriptors)

        sizePolicy = self._setPolicy(self.avg_depth_list)

        self.avg_depth_list.setSizePolicy(sizePolicy)
        self.avg_depth_list.setMinimumSize(QtCore.QSize(153, 0))
        self.avg_depth_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.avg_depth_list.setObjectName("avg_depth_list")
        self.vframe4.addWidget(self.avg_depth_list)
        self.horizontalLayout.addLayout(self.vframe4)
        self.vframe5 = QtWidgets.QVBoxLayout()
        self.vframe5.setObjectName("vframe5")
        self.max_depth_label = QtWidgets.QLabel(self.descriptors)
        self.max_depth_label.setAlignment(QtCore.Qt.AlignCenter)
        self.max_depth_label.setObjectName("max_depth_label")
        self.vframe5.addWidget(self.max_depth_label)
        self.max_depth_list = QtWidgets.QListWidget(self.descriptors)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.max_depth_list.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.max_depth_list)

        self.max_depth_list.setSizePolicy(sizePolicy)
        self.max_depth_list.setMinimumSize(QtCore.QSize(153, 0))
        self.max_depth_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.max_depth_list.setObjectName("max_depth_list")
        self.vframe5.addWidget(self.max_depth_list)
        self.horizontalLayout.addLayout(self.vframe5)
        self.verticalLayout_6 = QtWidgets.QVBoxLayout()
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.avg_hydropathy_label = QtWidgets.QLabel(self.descriptors)
        self.avg_hydropathy_label.setAlignment(QtCore.Qt.AlignCenter)
        self.avg_hydropathy_label.setObjectName("avg_hydropathy_label")
        self.verticalLayout_6.addWidget(self.avg_hydropathy_label)
        self.avg_hydropathy_list = QtWidgets.QListWidget(self.descriptors)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.avg_hydropathy_list.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.avg_hydropathy_list)

        self.avg_hydropathy_list.setSizePolicy(sizePolicy)
        self.avg_hydropathy_list.setMinimumSize(QtCore.QSize(153, 0))
        self.avg_hydropathy_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.avg_hydropathy_list.setObjectName("avg_hydropathy_list")
        self.verticalLayout_6.addWidget(self.avg_hydropathy_list)
        self.horizontalLayout.addLayout(self.verticalLayout_6)
        self.vframe3 = QtWidgets.QVBoxLayout()
        self.vframe3.setObjectName("vframe3")
        self.residues_label = QtWidgets.QLabel(self.descriptors)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.residues_label.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.residues_label)

        self.residues_label.setSizePolicy(sizePolicy)
        self.residues_label.setAlignment(QtCore.Qt.AlignCenter)
        self.residues_label.setObjectName("residues_label")
        self.vframe3.addWidget(self.residues_label)
        self.residues_list = QtWidgets.QListWidget(self.descriptors)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.residues_list.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.residues_list)

        self.residues_list.setSizePolicy(sizePolicy)
        self.residues_list.setMinimumSize(QtCore.QSize(153, 0))
        self.residues_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.residues_list.setObjectName("residues_list")
        self.vframe3.addWidget(self.residues_list)
        self.horizontalLayout.addLayout(self.vframe3)
        self.gridLayout_5.addWidget(self.descriptors, 2, 0, 1, 1)
        self.tabs.addTab(self.results, "")

        self.about = QtWidgets.QWidget()
        self.about.setObjectName("about")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.about)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.about_text = QtWidgets.QTextBrowser(self.about)
        self.about_text.setEnabled(True)
        self.about_text.viewport().setProperty("cursor", QtGui.QCursor(QtCore.Qt.IBeamCursor))
        self.about_text.setStyleSheet("background-color: #d3d3d3;color:black; padding: 20px; font: 10pt \"Sans Serif\";")
        self.about_text.setFrameShape(QtWidgets.QFrame.Box)
        self.about_text.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.about_text.setAutoFormatting(QtWidgets.QTextEdit.AutoBulletList)
        self.about_text.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.about_text.setAcceptRichText(True)
        self.about_text.setOpenExternalLinks(True)
        self.about_text.setObjectName("about_text")
        self.gridLayout_2.addWidget(self.about_text, 0, 0, 1, 1)
        self.tabs.addTab(self.about, "")
        self.gridLayout.addWidget(self.tabs, 1, 0, 1, 1)
        self.main_description = QtWidgets.QLabel(self.gui)
        self.main_description.setEnabled(True)

        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        # sizePolicy.setHorizontalStretch(0)
        # sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.main_description.sizePolicy().hasHeightForWidth())

        sizePolicy = self._setPolicy(self.main_description)

        self.main_description.setSizePolicy(sizePolicy)
        self.main_description.setMinimumSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(9)
        font.setBold(False)
        font.setWeight(50)
        self.main_description.setFont(font)
        self.main_description.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.main_description.setStyleSheet("background-color: #d3d3d3;color:black; padding: 10px")
        self.main_description.setFrameShape(QtWidgets.QFrame.Box)
        self.main_description.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.main_description.setText("parKVFinder software identifies and describes cavities in a target biomolecular structure using a dual probe system.\n"
"\n"
"The description includes spatial, depth, constitutional and hydropathy characterization. The spatial description includes shape, volume, and area. The depth description defines depths for each cavity point, shown in the B-factor, and calculates the average and maximum depth per cavity. The constitutional description includes amino acids that form the identified cavities. The hydropathy description maps Eisenberg & Weiss hydrophobicity scale at surface points, shown in the Q-factor, and estimates average hydropathy per cavity.")
        self.main_description.setTextFormat(QtCore.Qt.PlainText)
        self.main_description.setScaledContents(False)
        self.main_description.setAlignment(QtCore.Qt.AlignJustify|QtCore.Qt.AlignVCenter)
        self.main_description.setWordWrap(True)
        self.main_description.setObjectName("main_description")
        self.gridLayout.addWidget(self.main_description, 0, 0, 1, 1)
        pyKVFinder.setCentralWidget(self.gui)

        self.retranslateUi(pyKVFinder)
        self.tabs.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(pyKVFinder)

        pyKVFinder.setTabOrder(self.tabs, self.button_run)
        pyKVFinder.setTabOrder(self.button_run, self.button_grid)
        pyKVFinder.setTabOrder(self.button_grid, self.button_restore)
        pyKVFinder.setTabOrder(self.button_restore, self.button_exit)
        pyKVFinder.setTabOrder(self.button_exit, self.input)
        pyKVFinder.setTabOrder(self.input, self.refresh_input)
        pyKVFinder.setTabOrder(self.refresh_input, self.regionOption_rbtn4)
        pyKVFinder.setTabOrder(self.regionOption_rbtn4, self.regionOption_rbtn3)
        pyKVFinder.setTabOrder(self.regionOption_rbtn3, self.regionOption_rbtn2)
        pyKVFinder.setTabOrder(self.regionOption_rbtn2, self.regionOption_rbtn1)
        pyKVFinder.setTabOrder(self.regionOption_rbtn1, self.regionOption_label)
        pyKVFinder.setTabOrder(self.regionOption_label, self.probe_out)
        pyKVFinder.setTabOrder(self.probe_out, self.probe_in)
        pyKVFinder.setTabOrder(self.probe_in, self.volume_cutoff)
        pyKVFinder.setTabOrder(self.volume_cutoff, self.removal_distance)
        pyKVFinder.setTabOrder(self.removal_distance, self.base_name)
        pyKVFinder.setTabOrder(self.base_name, self.output_dir_path)
        pyKVFinder.setTabOrder(self.output_dir_path, self.button_browse)
        pyKVFinder.setTabOrder(self.button_browse, self.box_adjustment)
        pyKVFinder.setTabOrder(self.box_adjustment, self.button_draw_box)
        pyKVFinder.setTabOrder(self.button_draw_box, self.button_delete_box)
        pyKVFinder.setTabOrder(self.button_delete_box, self.button_redraw_box)
        pyKVFinder.setTabOrder(self.button_redraw_box, self.padding)
        pyKVFinder.setTabOrder(self.padding, self.min_x)
        pyKVFinder.setTabOrder(self.min_x, self.max_x)
        pyKVFinder.setTabOrder(self.max_x, self.min_y)
        pyKVFinder.setTabOrder(self.min_y, self.max_y)
        pyKVFinder.setTabOrder(self.max_y, self.min_z)
        pyKVFinder.setTabOrder(self.min_z, self.max_z)
        pyKVFinder.setTabOrder(self.max_z, self.angle1)
        pyKVFinder.setTabOrder(self.angle1, self.angle2)
        pyKVFinder.setTabOrder(self.angle2, self.ligand_adjustment)
        pyKVFinder.setTabOrder(self.ligand_adjustment, self.ligand)
        pyKVFinder.setTabOrder(self.ligand, self.refresh_ligand)
        pyKVFinder.setTabOrder(self.refresh_ligand, self.ligand_cutoff)
        pyKVFinder.setTabOrder(self.ligand_cutoff, self.results_file_entry)
        pyKVFinder.setTabOrder(self.results_file_entry, self.button_browse4)
        pyKVFinder.setTabOrder(self.button_browse4, self.button_load_results)
        pyKVFinder.setTabOrder(self.button_load_results, self.volume_list)
        pyKVFinder.setTabOrder(self.volume_list, self.area_list)
        pyKVFinder.setTabOrder(self.area_list, self.residues_list)
        pyKVFinder.setTabOrder(self.residues_list, self.about_text)

        self.gui.adjustSize()
    def _setPolicy(self, element):
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(element.sizePolicy().hasHeightForWidth())
        return sizePolicy

    def retranslateUi(self, pyKVFinder):
        _translate = QtCore.QCoreApplication.translate
        self.button_grid.setText(_translate("pyKVFinder", "Show Grid"))
        self.button_restore.setText(_translate("pyKVFinder", "Restore Default Values"))
        self.parameters.setTitle(_translate("pyKVFinder", "Parameters"))
        self.input_label.setText(_translate("pyKVFinder", "Input PDB:"))
        self.refresh_input.setText(_translate("pyKVFinder", "Refresh"))
        self.resolution_label.setText(_translate("pyKVFinder", "Resolution:"))
        self.resolution.setItemText(0, _translate("pyKVFinder", "Low"))
        self.resolution.setItemText(1, _translate("pyKVFinder", "Medium"))
        self.resolution.setItemText(2, _translate("pyKVFinder", "High"))
        self.resolution.setItemText(3, _translate("pyKVFinder", "Off"))
        self.step_size_label.setText(_translate("pyKVFinder", "Step Size (Å):"))
        self.probe_in_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Probe In (Å):</p></body></html>"))
        self.probe_out_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Probe Out (Å):</p></body></html>"))
        self.removal_distance_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Removal Distance (Å):</p></body></html>"))
        self.volume_cutoff_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Volume Cutoff (Å³):</p></body></html>"))
        self.surface_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Surface Representation:</p></body></html>"))
        self.surface.setItemText(0, _translate("pyKVFinder", "Molecular Surface (VdW)"))
        self.surface.setItemText(1, _translate("pyKVFinder", "Solvent Accesible Surface (SAS)"))
        self.cavity_representation_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Cavity Representation:</p></body></html>"))
        self.cavity_representation.setItemText(0, _translate("pyKVFinder", "Filtered"))
        self.cavity_representation.setItemText(1, _translate("pyKVFinder", "Full"))
        self.output_base_name_label.setText(_translate("pyKVFinder", "Output Base Name:"))
        self.output_dir_label.setText(_translate("pyKVFinder", "Output Directory:"))
        self.file_locations.setTitle(_translate("pyKVFinder", "File Locations"))
        #self.parKVFinder_label.setText(_translate("pyKVFinder", "parKVFinder:"))
        self.dictionary_label.setText(_translate("pyKVFinder", "vdW dictionary:"))
        self.tabs.setTabText(self.tabs.indexOf(self.main), _translate("pyKVFinder", "Main"))
        self.box_adjustment.setTitle(_translate("pyKVFinder", "Box Adjustment"))
        self.min_y_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Minimum Y (Å):</p></body></html>"))
        self.min_z_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Minimum Z (Å):</p></body></html>"))
        self.angle1_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Angle 1 (°):</p></body></html>"))
        self.button_draw_box.setText(_translate("pyKVFinder", "Draw Box"))
        self.button_delete_box.setText(_translate("pyKVFinder", "Delete Box"))
        self.button_redraw_box.setText(_translate("pyKVFinder", "Redraw Box"))
        self.min_x_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Minimum X (Å):</p></body></html>"))
        self.box_adjustment_label.setText(_translate("pyKVFinder", "Select residues and press Draw Box:"))
        self.button_box_adjustment_help.setText(_translate("pyKVFinder", "?"))
        self.angle2_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Angle 2 (°):</p></body></html>"))
        self.max_x_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Maximum X (Å):</p></body></html>"))
        self.max_z_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Maximum Z (Å):</p></body></html>"))
        self.max_y_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Maximum Y (Å):</p></body></html>"))
        self.padding_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Padding (Å):</p></body></html>"))
        self.ligand_adjustment.setTitle(_translate("pyKVFinder", "Ligand Adjustment"))
        self.ligand_label.setText(_translate("pyKVFinder", "Ligand PDB:"))
        self.refresh_ligand.setText(_translate("pyKVFinder", "Refresh"))
        self.ligand_cutoff_label.setText(_translate("pyKVFinder", "<html><head/><body><p>Ligand Cutoff (Å):</p></body></html>"))
        self.tabs.setTabText(self.tabs.indexOf(self.search_space), _translate("pyKVFinder", "Search Space"))
        self.show_descriptors_label.setText(_translate("pyKVFinder", "Show descriptors:"))
        self.default_view.setText(_translate("pyKVFinder", "Default"))
        self.depth_view.setText(_translate("pyKVFinder", "Depth"))
        self.hydropathy_view.setText(_translate("pyKVFinder", "Hydropathy"))
        self.results_information.setTitle(_translate("pyKVFinder", "Information"))
        self.results_file_label.setText(_translate("pyKVFinder", "Results File:"))
        self.input_file_label.setText(_translate("pyKVFinder", "Input File:"))
        self.ligand_file_label.setText(_translate("pyKVFinder", "Ligand File:"))
        self.cavities_file_label.setText(_translate("pyKVFinder", "Cavities File:"))
        self.step_size_label_2.setText(_translate("pyKVFinder", "Step Size (Å):"))
        self.descriptors.setTitle(_translate("pyKVFinder", "Descriptors"))
        self.volume_label.setText(_translate("pyKVFinder", "Volume (Å³)"))
        self.area_label.setText(_translate("pyKVFinder", "<html>Surface Area (Å&#178;)<\\html>"))
        self.avg_depth_label.setText(_translate("pyKVFinder", "Average Depth (Å)"))
        self.max_depth_label.setText(_translate("pyKVFinder", "Maximum Depth (Å)"))
        self.avg_hydropathy_label.setText(_translate("pyKVFinder", "Average Hydropathy"))
        self.residues_label.setText(_translate("pyKVFinder", "Interface Residues"))
        self.tabs.setTabText(self.tabs.indexOf(self.results), _translate("pyKVFinder", "Results"))
        self.about_text.setHtml(_translate("pyKVFinder", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'Sans Serif\'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">PyMOL2 parKVFinder Tools integrates PyMOL v2.x (http://PyMOL.org/) with parKVFinder (https://github.com/LBC-LNBio/parKVFinder).</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">In the simplest case to run parKVFinder:</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">1) Load a target biomolecular structure into PyMOL v2.x.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">2) Start PyMOL2 parKVFinder Tools plugin.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">3) Select an input PDB on \'Main\' tab.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">4) Ensure that parKVFinder executable path is correct on the &quot;Program Locations&quot; tab.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">5) Click the &quot;Run parKVFinder&quot; button.</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">Completed runs are available on \'Results\' tab, where users can check run information (i.e., input file, ligand file, output directory, step size) and spatial properties (i.e., volume, surface area and interface residues). In addition, the results can be loaded directly from a results file (.KVFinder.results.toml) by selecting a \'Results File\' by clicking on \'Browse ...\' and then clicking on \'Load\'. </span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">In addition to whole structure cavity detection, there are two search space adjustments: Box and Ligand adjustments.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- The \'Box adjustment\' mode creates a custom search box around a selection of interest by clicking on \'Draw Box\' button, which can be adapted by changing one box parameter (minimum and maximum XYZ, padding and angles) at a time by clicking on \'Redraw Box\'. For more information, there is a help button in \'Box adjustment\' group.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- The \'Ligand adjustment\' keeps cavity points around a target ligand PDB within a radius defined by the \'Ligand Cutoff\' parameter.</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">parKVFinder and PyMOL2 parKVFinder Tools was developed by:</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- João Victor da Silva Guerra</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- Helder Veras Filho</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- Leandro Oliveira Bortot</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- Rodrigo Vargas Honorato</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- José Geraldo de Carvalho Pereira</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">- Paulo Sergio Lopes de Oliveira (paulo.oliveira@lnbio.cnpem.br)</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">Brazilian Center for Research in Energy and Materials - CNPEM</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">Brazilian Biosciences National Laboratory - LNBio</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\">Please refer and cite our papers if you use it in a publication.</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; font-weight:600; text-decoration: underline; color:#000000;\">Citations</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:\'Droid Sans Mono\',\'monospace\',\'monospace\',\'Droid Sans Fallback\'; color:#000000;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">If you use <span style=\" text-decoration: underline;\">parKVFinder</span> or <span style=\" text-decoration: underline;\">PyMOL2 parKVFinder Tools</span>, please cite:</p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">João Victor da Silva Guerra, Helder Veras Ribeiro Filho, Leandro Oliveira Bortot, Rodrigo Vargas Honorato, José Geraldo de Carvalho Pereira, Paulo Sergio Lopes de Oliveira. ParKVFinder: A thread-level parallel approach in biomolecular cavity detection. SoftwareX (2020). <a href=\"https://doi.org/10.1016/j.softx.2020.100606\"><span style=\" text-decoration: underline; color:#0000ff;\">https://doi.org/10.1016/j.softx.2020.100606</span></a>.</p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">If you use <span style=\" text-decoration: underline;\">depth and hydropathy characterization</span>, please also cite:</p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Guerra, J.V.d., Ribeiro-Filho, H.V., Jara, G.E. et al. pyKVFinder: an efficient and integrable Python package for biomolecular cavity detection and characterization in data science. BMC Bioinformatics 22, 607 (2021). <a href=\"https://doi.org/10.1186/s12859-021-04519-4\"><span style=\" text-decoration: underline; color:#0000ff;\">https://doi.org/10.1186/s12859-021-04519-4</span></a>.</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">PyMOL citation may be found here:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><a href=\"http://pymol.sourceforge.net/faq.html#CITE\"><span style=\" text-decoration: underline; color:#0000ff;\">https://pymol.org/2/support.html?</span></a></p></body></html>"))
        self.tabs.setTabText(self.tabs.indexOf(self.about), _translate("pyKVFinder", "About"))
        
"""
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    pyKVFinder = QtWidgets.QMainWindow()
    ui = Ui_pyKVFinder()
    ui.setupUi(pyKVFinder)
    pyKVFinder.show()
    sys.exit(app.exec_())
"""

from io import StringIO

class InputGUI():
    def __init__(self, parentWidget):
        self.parentWidget = parentWidget

    def readline(self):
        text, ok = QtWidgets.QInputDialog.getText(self.parentWidget, 'Introduce value', 'Value:')
        if ok: 
            return str(text)
        else:
            return ''
        
class SampleGUI(QtWidgets.QWidget):
    def __init__(self, tool):
        super(SampleGUI, self).__init__()
        self.tool = tool
        self.u = self.tool.ui
        self.s = self.tool.session
        self.cx = cx
        self.log = ""
        
        self.initGUI()

    def initGUI(self):
        self.code = QtWidgets.QTextEdit()
        self.result = QtWidgets.QTextEdit()

        evalBtn = QtWidgets.QPushButton('Evaluate')
        evalBtn.clicked.connect(self.evaluate)

        clearBtn = QtWidgets.QPushButton('Clear')
        clearBtn.clicked.connect(self.clearT)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(evalBtn)
        hbox.addWidget(clearBtn)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.code)
        vbox.addLayout(hbox)
        vbox.addWidget(self.result)

        self.setLayout(vbox)
        #self.show()

    def evaluate(self):
        source_code = str(self.code.toPlainText())
        streams = sys.stdin, sys.stdout
        sys.stdin = InputGUI(self)                                                                                                                                                              
        redirected_output = sys.stdout = StringIO()
        exec(source_code)
        sys.stdin, sys.stdout = streams
        self.log += '>>> '+redirected_output.getvalue()+'\n'
        self.result.setText(self.log)

    def clearT(self):
        self.log = ""
        self.code.clear()
        self.result.clear()
