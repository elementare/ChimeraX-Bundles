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
from chimerax.atomic import StructureSeq, Structure
from chimerax.core.commands import run
import os
import pyKVFinder
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
        # 'session'   - chimerax.core.session.Session instance
        # 'tool_name' - string

        # Initialize base class.
        super().__init__(session, tool_name)

        # Set name displayed on title bar (defaults to tool_name)
        # Must be after the superclass init, which would override it.
        self.display_name = "KVFinder"

        # Create the main window for our tool.  The window object will have
        # a 'ui_area' where we place the widgets composing our interface.
        # The window isn't shown until we call its 'manage' method.
        #
        # Note that by default, tool windows are only hidden rather than
        # destroyed when the user clicks the window's close button.  To change
        # this behavior, specify 'close_destroys=True' in the MainToolWindow
        # constructor.
        from chimerax.ui import MainToolWindow
        self.tool_window = MainToolWindow(self)

        # We will be adding an item to the tool's context menu, so override
        # the default MainToolWindow fill_context_menu method
        self.tool_window.fill_context_menu = self.fill_context_menu

        # Our user interface is simple enough that we could probably inline
        # the code right here, but for any kind of even moderately complex
        # interface, it is probably better to put the code in a method so
        # that this __init__ method remains readable.
        self._build_ui()

    def _build_ui(self):
        # Put our widgets in the tool window

        # We will use an editable single-line text input field (QLineEdit)
        # with a descriptive text label to the left of it (QLabel).  To
        # arrange them horizontally side by side we use QHBoxLayout
        from Qt.QtWidgets import QLabel, QLineEdit, QHBoxLayout
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Log this text:"))
        self.line_edit = QLineEdit()

        # Arrange for our 'return_pressed' method to be called when the
        # user presses the Return key
        self.line_edit.returnPressed.connect(self.return_pressed)
        layout.addWidget(self.line_edit)

        # Set the layout as the contents of our window
        self.tool_window.ui_area.setLayout(layout)

        # Show the window on the user-preferred side of the ChimeraX
        # main window
        self.tool_window.manage('side')

    def return_pressed(self):
        # The use has pressed the Return key; log the current text as HTML
        from chimerax.core.commands import run
        # ToolInstance has a 'session' attribute...

        if self.line_edit.text() == "cavities":
   
            path = "/home/ABTLUS/carlos23001/GithubProjects/ChimeraX-Bundles/tmp/file.pdb"

            run(self.session, f"save {path} #1")
            
            results = pyKVFinder.run_workflow(path, probe_out=12.0, volume_cutoff=100.0, ignore_backbone=True, include_depth=True, include_hydropathy=True)
            
            self.session.logger.info(str(results.cavities))
        else:
            structures = [m for m in self.session.models if isinstance(m, Structure)]
            if len(structures) > 1:
                self.session.logger.info("Tem mais de uma estrutura")
                self.session.logger.info(str(structures))
            else:
                structure = structures[0]
                self.session.logger.info(f"atoms: {str(structure.atoms)}, {len(structure.atoms)}")
                self.session.logger.info(f"first atom: {str(structure.atoms[int(self.line_edit.text())])}")
                self.session.logger.info(f"atomspec: {str(structure.atomspec)}")
                #self.session.logger.info(f"molecule: {str(structure.molecules)}, {len(structure.molecules)}")
                self.session.logger.info(f"name: {str(structure.name)}")


        

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
