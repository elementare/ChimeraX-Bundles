from __future__ import absolute_import, annotations, print_function

import json
import os
from typing import Any, Dict, Optional
from chimerax.core.tools import ToolInstance
import toml
from PyQt6 import QtCore, QtWidgets

__name__ = "PyMOL KVFinder-web Tools"
__version__ = "v1.0.0"


# global reference to avoid garbage collection of our dialog
dialog = None
worker = None


##########################################
#          Relevant information          #
# Web service (KVFinder-web service)     #
# This variable defines the url of the   #
# KVFinder-web service. Change this      #
# variable to the service you are using  #
# Server                                 #
server = "http://kvfinder-web.cnpem.br"  #
# Path                                   #
path = "/api"                            #
#                                        #
# Days until job expire                  #
days_job_expire = 1                      #
#                                        #
# Data limit                             #
data_limit = "5 Mb"                      #
#                                        #
# Timers (msec)                          #
time_restart_job_checks = 5000           #
time_server_down = 60000                 #
time_no_jobs = 5000                      #
time_between_jobs = 2000                 #
time_wait_status = 5000                  #
#                                        #
# Times jobs completed with downloaded   #
# results are not checked in service     #
times_job_completed_no_checked = 500     #
#                                        #
# Verbosity: print extra information     #
# 0: No extra information                #
# 1: Print GUI information               #
# 2: Print Worker information            #
# 3: Print all information (Worker/GUI)  #
verbosity = 0                            #
##########################################

from chimerax.core.tools import ToolInstance


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
        run(self.session, "log html %s" % self.line_edit.text())

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

class PyMOLKVFinderWebTools(QtWidgets.QMainWindow):
    """
    PyMOL KVFinder Web Tools

    This class creates our client graphical user interface (GUI) with PyQt5 package in PyMOL software and defines functions and callback for GUI.
    """

    # Signals
    msgbox_signal = QtCore.pyqtSignal(bool)

    def __init__(self, server=server, path=path):
        super(PyMOLKVFinderWebTools, self).__init__()
        """
        This method initialize our graphical user interface core attributes and startup configuration, and our worker thread to communicate with KVFinder-web service located at 'server' variable.

        Parameters
        ----------
        server: str
            KVFinder-web service address (Default: http://kvfinder-web.cnpem.br). Users may set this variable to a locally configured KVFinder-web service by changing 'server' global variable.
        path: str
            Server path to communicate with KVFinder-web service (Default: /api)
        """
        from PyQt6.QtNetwork import QNetworkAccessManager

        # Define Default Parameters
        self._default = _Default()

        # Initialize PyMOLKVFinderWebTools GUI
        self.initialize_gui()

        # Restore Default Parameters
        self.restore(is_startup=True)

        # Set box centers
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

        # Define server
        self.server = f"{server}/{path.replace('/', '')}"
        self.network_manager = QNetworkAccessManager()

        # Check server status
        status = _check_server_status(self.server)
        self.set_server_status(status)

        # Create ./KVFinder-web directory for jobs
        jobs_dir = os.path.join(os.path.expanduser("~"), ".KVFinder-web")
        try:
            os.mkdir(jobs_dir)
        except FileExistsError:
            pass

        # Start Worker thread to handle available jobs
        global worker
        if worker is None:
            worker = self._start_worker_thread()

        # Get available jobs
        self.available_jobs.addItems(_get_jobs())
        self.fill_job_information()

        # Results
        self.results = None
        self.input_pdb = None
        self.ligand_pdb = None
        self.cavity_pdb = None

    def initialize_gui(self) -> None:
        """
        This method initializes graphical user interface from .ui file, bind scrollbars to QListWidgets and hooks up buttons with callbacks.
        """
        # Import the PyQt interface
        from PyQt6 import QtWidgets
        from PyQt6.uic import loadUi

        # populate the QMainWindow from our *.ui file
        uifile = os.path.join(os.path.dirname(__file__), "PyMOL-KVFinder-web-tools.ui")
        loadUi(uifile, self)

        # ScrollBars binded to QListWidgets in Descriptors
        scroll_bar_volume = QtWidgets.QScrollBar(self)
        self.volume_list.setVerticalScrollBar(scroll_bar_volume)
        scroll_bar_area = QtWidgets.QScrollBar(self)
        self.area_list.setVerticalScrollBar(scroll_bar_area)
        scroll_bar_residues = QtWidgets.QScrollBar(self)
        self.residues_list.setVerticalScrollBar(scroll_bar_residues)

        # about text
        self.about_text.setHtml(about_text)

        # Buttons Callback

        # hook up QMainWindow buttons callbacks
        self.button_run.clicked.connect(self.run)
        self.button_exit.clicked.connect(self.close)
        self.button_restore.clicked.connect(self.restore)
        self.button_grid.clicked.connect(self.show_grid)

        # hook up Parameters button callbacks
        self.button_browse.clicked.connect(self.select_directory)
        self.refresh_input.clicked.connect(lambda: self.refresh(self.input))

        # hook up Search Space button callbacks
        # Box Adjustment
        self.button_draw_box.clicked.connect(self.set_box)
        self.button_delete_box.clicked.connect(self.delete_box)
        self.button_redraw_box.clicked.connect(self.redraw_box)
        self.button_box_adjustment_help.clicked.connect(self.box_adjustment_help)
        # Ligand Adjustment
        self.refresh_ligand.clicked.connect(lambda: self.refresh(self.ligand))

        # hook up methods to results tab
        # Jobs
        self.available_jobs.currentIndexChanged.connect(self.fill_job_information)
        self.button_show_job.clicked.connect(self.show_id)
        self.button_add_job_id.clicked.connect(self.add_id)
        # Visualization
        self.button_browse_results.clicked.connect(self.select_results_file)
        self.button_load_results.clicked.connect(self.load_results)
        self.volume_list.itemSelectionChanged.connect(
            lambda list1=self.volume_list, list2=self.area_list: self.show_cavities(
                list1, list2
            )
        )
        self.area_list.itemSelectionChanged.connect(
            lambda list1=self.area_list, list2=self.volume_list: self.show_cavities(
                list1, list2
            )
        )
        self.avg_depth_list.itemSelectionChanged.connect(
            lambda list1=self.avg_depth_list, list2=self.max_depth_list: self.show_depth(
                list1, list2
            )
        )
        self.max_depth_list.itemSelectionChanged.connect(
            lambda list1=self.max_depth_list, list2=self.avg_depth_list: self.show_depth(
                list1, list2
            )
        )
        self.avg_hydropathy_list.itemSelectionChanged.connect(
            lambda list1=self.avg_hydropathy_list: self.show_hydropathy(list1)
        )
        self.residues_list.itemSelectionChanged.connect(self.show_residues)
        self.default_view.toggled.connect(self.show_default_view)
        self.depth_view.toggled.connect(self.show_depth_view)
        self.hydropathy_view.toggled.connect(self.show_hydropathy_view)

    def run(self) -> None:
        """
        Get detection parameters and molecular structures defined on the GUI and submit a job to KVFinder-web service.

        The job submission is handled by QtNetwork package, part of PyQt6, that uses a POST method to send a JSON with data to KVFinder-web service.
        """
        from PyQt6 import QtNetwork
        from PyQt6.QtCore import QJsonDocument, QUrl

        # Create job
        parameters = self.create_parameters()
        if type(parameters) is dict:
            self.job = Job(parameters)
        else:
            return

        print("\n[==> Submitting job to KVFinder-web service ...")

        # Post request
        try:
            # Prepare request
            url = QUrl(f"{self.server}/create")
            request = QtNetwork.QNetworkRequest(url)
            request.setHeader(
                QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader,
                "application/json",
            )

            # Prepare data
            data = QJsonDocument(self.job.input)

            # Post requests
            self.reply = self.network_manager.post(request, data.toJson())
            self.reply.finished.connect(self._handle_post_response)
        except Exception as e:
            print(e)

    def _handle_post_response(self) -> None:
        """
        This methods handles the POST method response.

        If there are no error in the request, this methods evaluates the response and process accordingly, by writing incoming results and job information to files.

        If there are an error in the request, this method displays a QMessageBox with the corresponding error message and HTTP error code.
        """
        from PyQt6 import QtNetwork

        # Get QNetworkReply error status
        er = self.reply.error()

        # Handle Post Response
        if er == QtNetwork.QNetworkReply.NetworkError.NoError:
            reply = str(self.reply.readAll(), "utf-8")
            reply = json.loads(reply)

            # Save job id
            self.job.id = reply["id"]

            # Results not available
            if "output" not in reply.keys():
                if verbosity in [1, 3]:
                    print("> Job successfully submitted to KVFinder-web service!")

                # Message to user
                message = Message(
                    "Job successfully submitted to KVFinder-web service!", self.job.id
                )
                message.exec()

                # Save job file
                self.job.status = "queued"
                self.job.save(self.job.id)
                print(f"> Job ID: {self.job.id}")

                # Add Job ID to Results tab
                self.available_jobs.clear()
                self.available_jobs.addItems(_get_jobs())
                self.available_jobs.setCurrentText(self.job.id)

            # Job already sent to KVFinder-web service
            else:
                status = reply["status"]

                # handle job completed
                if status == "completed":
                    if verbosity in [1, 3]:
                        print("> Job already completed in KVFinder-web service!")

                    # Message to user
                    message = Message(
                        "Job already completed in KVFinder-web service!\nDisplaying results ...",
                        self.job.id,
                        status,
                    )
                    message.exec()

                    # Export results
                    self.job.output = reply
                    try:
                        self.job.export()
                    except Exception as e:
                        print("Error occurred: ", e)

                    # Save job file
                    self.job.status = status
                    self.job.save(self.job.id)

                    # Add Job ID to Results tab
                    if self.job.id not in [
                        self.available_jobs.itemText(i)
                        for i in range(self.available_jobs.count())
                    ]:
                        self.available_jobs.addItem(self.job.id)
                    self.available_jobs.setCurrentText(self.job.id)

                    # Show ID
                    self.show_id()

                    # Select Results Tab
                    self.tabs.setCurrentIndex(2)

                # handle job not completed
                elif status == "running" or status == "queued":
                    if verbosity in [1, 3]:
                        print("> Job already submitted to KVFinder-web service!")

                    # Message to user
                    message = Message(
                        "Job already submitted to KVFinder-web service!",
                        self.job.id,
                        status,
                    )
                    message.exec()

        elif er == QtNetwork.QNetworkReply.NetworkError.ConnectionRefusedError:
            from PyQt6 import QtWidgets

            # Set server status in GUI
            self.server_down()

            # Message to user
            if verbosity in [1, 3]:
                print(
                    "\n\033[93mWarning:\033[0m KVFinder-web service is Offline! Try again later!\n"
                )
            QtWidgets.QMessageBox.critical(
                self,
                "Job Submission",
                "KVFinder-web service is Offline!\n\nTry again later!",
            )

        elif er == QtNetwork.QNetworkReply.NetworkError.UnknownContentError:
            from PyQt6 import QtWidgets

            # Set server status in GUI
            self.server_up()

            # Message to user
            if verbosity in [1, 3]:
                print(
                    f"\n\033[91mError:\033[0mJob exceedes the maximum payload of {data_limit} on KVFinder-web service!\n"
                )
            QtWidgets.QMessageBox.critical(
                self,
                "Job Submission",
                f"Job exceedes the maximum payload of {data_limit} on KVFinder-web service!",
            )

        elif er == QtNetwork.QNetworkReply.NetworkError.TimeoutError:
            from PyQt6 import QtWidgets

            # Set server status in GUI
            self.server_down()

            # Message to user
            if verbosity in [1, 3]:
                print(
                    "\n\033[93mWarning:\033[0m The connection to the KVFinder-web server timed out!\n"
                )
            QtWidgets.QMessageBox.critical(
                self,
                "Job Submission",
                "The connection to the KVFinder-web server timed out!\n\nCheck your connection and KVFinder-web server status!",
            )

        else:
            reply = str(self.reply.readAll(), "utf-8")
            # Message to user
            if verbosity in [1, 3]:
                print(f"\n\033[91mError {er}\033[0m\n\n")
            message = Message(
                f"Error {er}!",
                job_id=None,
                status=None,
                notification=f"{self.reply.errorString()}\n{reply}\n",
            )
            message.exec()

    def show_grid(self) -> None:
        """
        Callback for the "Show Grid" button.

        This method gets minimum and maximum coordinates of the KVFinder-web 3D-grid, dependent on selected parameters, and call draw_grid method with minimum and maximum coordinates.

        If there are an error, a QMessageBox will be displayed.
        """
        from pymol import cmd
        from PyQt6 import QtWidgets

        global x, y, z

        if self.input.count() > 0:
            # Get minimum and maximum dimensions of target PDB
            pdb = self.input.currentText()
            ([min_x, min_y, min_z], [max_x, max_y, max_z]) = cmd.get_extent(pdb)

            # Get Probe Out value
            probe_out = self.probe_out.value()
            probe_out = round(probe_out - round(probe_out, 4) % round(0.6, 4), 1)

            # Prepare dimensions
            min_x = round(min_x - (min_x % 0.6), 1) - probe_out
            min_y = round(min_y - (min_y % 0.6), 1) - probe_out
            min_z = round(min_z - (min_z % 0.6), 1) - probe_out
            max_x = round(max_x - (max_x % 0.6) + 0.6, 1) + probe_out
            max_y = round(max_y - (max_y % 0.6) + 0.6, 1) + probe_out
            max_z = round(max_z - (max_z % 0.6) + 0.6, 1) + probe_out

            # Get center of each dimension (x, y, z)
            x = (min_x + max_x) / 2
            y = (min_y + max_y) / 2
            z = (min_z + max_z) / 2

            # Draw Grid
            self.draw_grid(min_x, max_x, min_y, max_y, min_z, max_z)
        else:
            QtWidgets.QMessageBox.critical(self, "Error", "Select an input PDB!")
            return

    def draw_grid(self, min_x, max_x, min_y, max_y, min_z, max_z) -> None:
        """
        Draw Grid in PyMOL.

        An object named grid is created on PyMOL viewer.

        Parameters
        ----------
        min_x: float
            Minimum X coordinate.
        max_x: float
            Maximum X coordinate.
        min_y: float
            Minimum Y coordinate.
        max_y: float
            Maximum Y coordinate.
        min_z: float
            Minimum Z coordinate.
        max_z: float
            Maximum Z coordinate.
        """
        from math import cos, sin

        from pymol import cmd

        # Prepare dimensions
        angle1 = 0.0
        angle2 = 0.0
        min_x = x - min_x
        max_x = max_x - x
        min_y = y - min_y
        max_y = max_y - y
        min_z = z - min_z
        max_z = max_z - z

        # Get positions of grid vertices
        # P1
        x1 = (
            -min_x * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + x
        )

        y1 = -min_y * cos(angle1) + (-min_z) * sin(angle1) + y

        z1 = (
            min_x * sin(angle2)
            + min_y * sin(angle1) * cos(angle2)
            - min_z * cos(angle1) * cos(angle2)
            + z
        )

        # P2
        x2 = (
            max_x * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + x
        )

        y2 = (-min_y) * cos(angle1) + (-min_z) * sin(angle1) + y

        z2 = (
            (-max_x) * sin(angle2)
            - (-min_y) * sin(angle1) * cos(angle2)
            + (-min_z) * cos(angle1) * cos(angle2)
            + z
        )

        # P3
        x3 = (
            (-min_x) * cos(angle2)
            - max_y * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + x
        )

        y3 = max_y * cos(angle1) + (-min_z) * sin(angle1) + y

        z3 = (
            -(-min_x) * sin(angle2)
            - max_y * sin(angle1) * cos(angle2)
            + (-min_z) * cos(angle1) * cos(angle2)
            + z
        )

        # P4
        x4 = (
            (-min_x) * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + max_z * cos(angle1) * sin(angle2)
            + x
        )

        y4 = (-min_y) * cos(angle1) + max_z * sin(angle1) + y

        z4 = (
            -(-min_x) * sin(angle2)
            - (-min_y) * sin(angle1) * cos(angle2)
            + max_z * cos(angle1) * cos(angle2)
            + z
        )

        # P5
        x5 = (
            max_x * cos(angle2)
            - max_y * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + x
        )

        y5 = max_y * cos(angle1) + (-min_z) * sin(angle1) + y

        z5 = (
            (-max_x) * sin(angle2)
            - max_y * sin(angle1) * cos(angle2)
            + (-min_z) * cos(angle1) * cos(angle2)
            + z
        )

        # P6
        x6 = (
            max_x * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + max_z * cos(angle1) * sin(angle2)
            + x
        )

        y6 = (-min_y) * cos(angle1) + max_z * sin(angle1) + y

        z6 = (
            (-max_x) * sin(angle2)
            - (-min_y) * sin(angle1) * cos(angle2)
            + max_z * cos(angle1) * cos(angle2)
            + z
        )

        # P7
        x7 = (
            (-min_x) * cos(angle2)
            - max_y * sin(angle1) * sin(angle2)
            + max_z * cos(angle1) * sin(angle2)
            + x
        )

        y7 = max_y * cos(angle1) + max_z * sin(angle1) + y

        z7 = (
            -(-min_x) * sin(angle2)
            - max_y * sin(angle1) * cos(angle2)
            + max_z * cos(angle1) * cos(angle2)
            + z
        )

        # P8
        x8 = (
            max_x * cos(angle2)
            - max_y * sin(angle1) * sin(angle2)
            + max_z * cos(angle1) * sin(angle2)
            + x
        )

        y8 = max_y * cos(angle1) + max_z * sin(angle1) + y

        z8 = (
            (-max_x) * sin(angle2)
            - max_y * sin(angle1) * cos(angle2)
            + max_z * cos(angle1) * cos(angle2)
            + z
        )

        # Create box object
        if "grid" in cmd.get_names("objects"):
            cmd.delete("grid")

        # Create vertices
        cmd.pseudoatom("grid", name="v2", pos=[x2, y2, z2], color="white")
        cmd.pseudoatom("grid", name="v3", pos=[x3, y3, z3], color="white")
        cmd.pseudoatom("grid", name="v4", pos=[x4, y4, z4], color="white")
        cmd.pseudoatom("grid", name="v5", pos=[x5, y5, z5], color="white")
        cmd.pseudoatom("grid", name="v6", pos=[x6, y6, z6], color="white")
        cmd.pseudoatom("grid", name="v7", pos=[x7, y7, z7], color="white")
        cmd.pseudoatom("grid", name="v8", pos=[x8, y8, z8], color="white")

        # Connect vertices
        cmd.select("vertices", "(name v3,v7)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v2,v6)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v5,v8)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v2,v5)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v4,v6)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v4,v7)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v3,v5)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v6,v8)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v7,v8)")
        cmd.bond("vertices", "vertices")
        cmd.pseudoatom("grid", name="v1x", pos=[x1, y1, z1], color="white")
        cmd.pseudoatom("grid", name="v2x", pos=[x2, y2, z2], color="white")
        cmd.select("vertices", "(name v1x,v2x)")
        cmd.bond("vertices", "vertices")
        cmd.pseudoatom("grid", name="v1y", pos=[x1, y1, z1], color="white")
        cmd.pseudoatom("grid", name="v3y", pos=[x3, y3, z3], color="white")
        cmd.select("vertices", "(name v1y,v3y)")
        cmd.bond("vertices", "vertices")
        cmd.pseudoatom("grid", name="v4z", pos=[x4, y4, z4], color="white")
        cmd.pseudoatom("grid", name="v1z", pos=[x1, y1, z1], color="white")
        cmd.select("vertices", "(name v1z,v4z)")
        cmd.bond("vertices", "vertices")
        cmd.delete("vertices")

    def restore(self, is_startup=False) -> None:
        """
        Callback for the "Restore Default Values" button.

        This method restore detection parameters to default (class Default). If the GUI is not starting up, extra steps are taken to clean the enviroment.

        Parameters
        ----------
        is_startup: bool
            Whether the GUI is starting up.
        """
        from pymol import cmd
        from PyQt6 import QtWidgets

        # Restore Results Tab
        if not is_startup:
            reply = QtWidgets.QMessageBox(self)
            reply.setText("Also restore Results Visualization tab?")
            reply.setWindowTitle("Restore Values")
            reply.setStandardButtons(
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            reply.setIcon(QtWidgets.QMessageBox.Information)
            reply.checkbox = QtWidgets.QCheckBox("Also remove input and ligand PDBs?")
            reply.layout = reply.layout()
            reply.layout.addWidget(reply.checkbox, 1, 2)
            if reply.exec() == QtWidgets.QMessageBox.Yes:
                # Remove cavities, residues and pdbs (input, ligand, cavity)
                cmd.delete("cavities")
                cmd.delete("residues")
                if self.input_pdb and reply.checkbox.isChecked():
                    cmd.delete(self.input_pdb)
                if self.ligand_pdb and reply.checkbox.isChecked():
                    cmd.delete(self.ligand_pdb)
                if self.cavity_pdb:
                    cmd.delete(self.cavity_pdb)
                global results
                results = self.input_pdb = self.ligand_pdb = self.cavity_pdb = None
                cmd.frame(1)

                # Clean results
                self.clean_results()
                self.vis_results_file_entry.clear()

        # Restore PDB and ligand input
        self.refresh(self.input)
        self.refresh(self.ligand)

        # Delete grid
        cmd.delete("grid")

        # Main tab #
        self.base_name.setText(self._default.base_name)
        self.probe_in.setValue(self._default.probe_in)
        self.probe_out.setValue(self._default.probe_out)
        self.volume_cutoff.setValue(self._default.volume_cutoff)
        self.removal_distance.setValue(self._default.removal_distance)
        self.output_dir_path.setText(self._default.output_dir_path)

        # Search Space Tab #
        # Box Adjustment
        self.box_adjustment.setChecked(self._default.box_adjustment)
        self.padding.setValue(self._default.padding)
        self.delete_box()
        # Ligand Adjustment
        self.ligand_adjustment.setChecked(self._default.ligand_adjustment)
        self.ligand.clear()
        self.ligand_cutoff.setValue(self._default.ligand_cutoff)

    def refresh(self, combo_box) -> None:
        """
        Callback for the "Refresh" button.

        This method gets objects on the PyMOL viewer and displays them on a target combo box.

        Parameters
        ----------
        combo_box: QComboBox
            A target QComboBox to add the object names that are on PyMOL scene
        """
        from pymol import cmd

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

        return

    def select_directory(self) -> None:
        """
        Callback for the "Browse ..." button.

        This method opens a QFileDialog to select a directory.
        """
        from PyQt6 import QtCore, QtWidgets

        fname = QtWidgets.QFileDialog.getExistingDirectory(
            caption="Choose Output Directory", directory=os.getcwd()
        )

        if fname:
            fname = QtCore.QDir.toNativeSeparators(fname)
            if os.path.isdir(fname):
                self.output_dir_path.setText(fname)

        return

    def set_box(self) -> None:
        """
        This method creates the box coordinates, enables 'Delete Box' and 'Redraw Box' buttons and calls draw_box method.

        It gets the minimum and maximum coordinates of the current selection 'sele'. With that, it calculates the center, minimum and maximum coordinates and rotation angles of the box. Afterwards, enable the components of Box adjusment frame and set their values.
        """
        from pymol import cmd

        # Delete Box object in PyMOL
        if "box" in cmd.get_names("selections"):
            cmd.delete("box")
        # Get dimensions of selected residues
        selection = "sele"
        if selection in cmd.get_names("selections"):
            ([min_x, min_y, min_z], [max_x, max_y, max_z]) = cmd.get_extent(selection)
        else:
            ([min_x, min_y, min_z], [max_x, max_y, max_z]) = cmd.get_extent("")

        # Get center of each dimension (x, y, z)
        self.x = (min_x + max_x) / 2
        self.y = (min_y + max_y) / 2
        self.z = (min_z + max_z) / 2

        # Set Box variables in interface
        self.min_x.setValue(round(self.x - (min_x - self.padding.value()), 1))
        self.max_x.setValue(round((max_x + self.padding.value()) - self.x, 1))
        self.min_y.setValue(round(self.y - (min_y - self.padding.value()), 1))
        self.max_y.setValue(round((max_y + self.padding.value()) - self.y, 1))
        self.min_z.setValue(round(self.z - (min_z - self.padding.value()), 1))
        self.max_z.setValue(round((max_z + self.padding.value()) - self.z, 1))
        self.angle1.setValue(0)
        self.angle2.setValue(0)

        # Setting background box values
        self.min_x_set = self.min_x.value()
        self.max_x_set = self.max_x.value()
        self.min_y_set = self.min_y.value()
        self.max_y_set = self.max_y.value()
        self.min_z_set = self.min_z.value()
        self.max_z_set = self.max_z.value()
        self.angle1_set = self.angle1.value()
        self.angle2_set = self.angle2.value()
        self.padding_set = self.padding.value()

        # Draw box
        self.draw_box()

        # Enable/Disable buttons
        self.button_draw_box.setEnabled(False)
        self.button_redraw_box.setEnabled(True)
        self.min_x.setEnabled(True)
        self.min_y.setEnabled(True)
        self.min_z.setEnabled(True)
        self.max_x.setEnabled(True)
        self.max_y.setEnabled(True)
        self.max_z.setEnabled(True)
        self.angle1.setEnabled(True)
        self.angle2.setEnabled(True)

    def draw_box(self) -> None:
        """
        Callback for the "Draw box" button.

        This method calculates each vertice of the custom box. Then, it draws and connects them on the PyMOL viewer as a object named 'box'.
        """
        from math import cos, pi, sin

        import pymol
        from pymol import cmd

        # Convert angle
        angle1 = (self.angle1.value() / 180.0) * pi
        angle2 = (self.angle2.value() / 180.0) * pi

        # Get positions of box vertices
        # P1
        x1 = (
            -self.min_x.value() * cos(angle2)
            - (-self.min_y.value()) * sin(angle1) * sin(angle2)
            + (-self.min_z.value()) * cos(angle1) * sin(angle2)
            + self.x
        )

        y1 = (
            -self.min_y.value() * cos(angle1)
            + (-self.min_z.value()) * sin(angle1)
            + self.y
        )

        z1 = (
            self.min_x.value() * sin(angle2)
            + self.min_y.value() * sin(angle1) * cos(angle2)
            - self.min_z.value() * cos(angle1) * cos(angle2)
            + self.z
        )

        # P2
        x2 = (
            self.max_x.value() * cos(angle2)
            - (-self.min_y.value()) * sin(angle1) * sin(angle2)
            + (-self.min_z.value()) * cos(angle1) * sin(angle2)
            + self.x
        )

        y2 = (
            (-self.min_y.value()) * cos(angle1)
            + (-self.min_z.value()) * sin(angle1)
            + self.y
        )

        z2 = (
            (-self.max_x.value()) * sin(angle2)
            - (-self.min_y.value()) * sin(angle1) * cos(angle2)
            + (-self.min_z.value()) * cos(angle1) * cos(angle2)
            + self.z
        )

        # P3
        x3 = (
            (-self.min_x.value()) * cos(angle2)
            - self.max_y.value() * sin(angle1) * sin(angle2)
            + (-self.min_z.value()) * cos(angle1) * sin(angle2)
            + self.x
        )

        y3 = (
            self.max_y.value() * cos(angle1)
            + (-self.min_z.value()) * sin(angle1)
            + self.y
        )

        z3 = (
            -(-self.min_x.value()) * sin(angle2)
            - self.max_y.value() * sin(angle1) * cos(angle2)
            + (-self.min_z.value()) * cos(angle1) * cos(angle2)
            + self.z
        )

        # P4
        x4 = (
            (-self.min_x.value()) * cos(angle2)
            - (-self.min_y.value()) * sin(angle1) * sin(angle2)
            + self.max_z.value() * cos(angle1) * sin(angle2)
            + self.x
        )

        y4 = (
            (-self.min_y.value()) * cos(angle1)
            + self.max_z.value() * sin(angle1)
            + self.y
        )

        z4 = (
            -(-self.min_x.value()) * sin(angle2)
            - (-self.min_y.value()) * sin(angle1) * cos(angle2)
            + self.max_z.value() * cos(angle1) * cos(angle2)
            + self.z
        )

        # P5
        x5 = (
            self.max_x.value() * cos(angle2)
            - self.max_y.value() * sin(angle1) * sin(angle2)
            + (-self.min_z.value()) * cos(angle1) * sin(angle2)
            + self.x
        )

        y5 = (
            self.max_y.value() * cos(angle1)
            + (-self.min_z.value()) * sin(angle1)
            + self.y
        )

        z5 = (
            (-self.max_x.value()) * sin(angle2)
            - self.max_y.value() * sin(angle1) * cos(angle2)
            + (-self.min_z.value()) * cos(angle1) * cos(angle2)
            + self.z
        )

        # P6
        x6 = (
            self.max_x.value() * cos(angle2)
            - (-self.min_y.value()) * sin(angle1) * sin(angle2)
            + self.max_z.value() * cos(angle1) * sin(angle2)
            + self.x
        )

        y6 = (
            (-self.min_y.value()) * cos(angle1)
            + self.max_z.value() * sin(angle1)
            + self.y
        )

        z6 = (
            (-self.max_x.value()) * sin(angle2)
            - (-self.min_y.value()) * sin(angle1) * cos(angle2)
            + self.max_z.value() * cos(angle1) * cos(angle2)
            + self.z
        )

        # P7
        x7 = (
            (-self.min_x.value()) * cos(angle2)
            - self.max_y.value() * sin(angle1) * sin(angle2)
            + self.max_z.value() * cos(angle1) * sin(angle2)
            + self.x
        )

        y7 = (
            self.max_y.value() * cos(angle1) + self.max_z.value() * sin(angle1) + self.y
        )

        z7 = (
            -(-self.min_x.value()) * sin(angle2)
            - self.max_y.value() * sin(angle1) * cos(angle2)
            + self.max_z.value() * cos(angle1) * cos(angle2)
            + self.z
        )

        # P8
        x8 = (
            self.max_x.value() * cos(angle2)
            - self.max_y.value() * sin(angle1) * sin(angle2)
            + self.max_z.value() * cos(angle1) * sin(angle2)
            + self.x
        )

        y8 = (
            self.max_y.value() * cos(angle1) + self.max_z.value() * sin(angle1) + self.y
        )

        z8 = (
            (-self.max_x.value()) * sin(angle2)
            - self.max_y.value() * sin(angle1) * cos(angle2)
            + self.max_z.value() * cos(angle1) * cos(angle2)
            + self.z
        )

        # Create box object
        pymol.stored.list = []
        if "box" in cmd.get_names("selections"):
            cmd.iterate("box", "stored.list.append((name, color))", quiet=1)
        list_color = pymol.stored.list
        cmd.delete("box")
        if len(list_color) > 0:
            for item in list_color:
                at_name = item[0]
                at_c = item[1]
                cmd.set_color(at_name + "color", cmd.get_color_tuple(at_c))
        else:
            for at_name in [
                "v2",
                "v3",
                "v4",
                "v5",
                "v6",
                "v7",
                "v8",
                "v1x",
                "v1y",
                "v1z",
                "v2x",
                "v3y",
                "v4z",
            ]:
                cmd.set_color(at_name + "color", [0.86, 0.86, 0.86])

        # Create vertices
        cmd.pseudoatom("box", name="v2", pos=[x2, y2, z2], color="v2color")
        cmd.pseudoatom("box", name="v3", pos=[x3, y3, z3], color="v3color")
        cmd.pseudoatom("box", name="v4", pos=[x4, y4, z4], color="v4color")
        cmd.pseudoatom("box", name="v5", pos=[x5, y5, z5], color="v5color")
        cmd.pseudoatom("box", name="v6", pos=[x6, y6, z6], color="v6color")
        cmd.pseudoatom("box", name="v7", pos=[x7, y7, z7], color="v7color")
        cmd.pseudoatom("box", name="v8", pos=[x8, y8, z8], color="v8color")

        # Connect vertices
        cmd.select("vertices", "(name v3,v7)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v2,v6)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v5,v8)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v2,v5)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v4,v6)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v4,v7)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v3,v5)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v6,v8)")
        cmd.bond("vertices", "vertices")
        cmd.select("vertices", "(name v7,v8)")
        cmd.bond("vertices", "vertices")
        cmd.pseudoatom("box", name="v1x", pos=[x1, y1, z1], color="red")
        cmd.pseudoatom("box", name="v2x", pos=[x2, y2, z2], color="red")
        cmd.select("vertices", "(name v1x,v2x)")
        cmd.bond("vertices", "vertices")
        cmd.pseudoatom("box", name="v1y", pos=[x1, y1, z1], color="forest")
        cmd.pseudoatom("box", name="v3y", pos=[x3, y3, z3], color="forest")
        cmd.select("vertices", "(name v1y,v3y)")
        cmd.bond("vertices", "vertices")
        cmd.pseudoatom("box", name="v4z", pos=[x4, y4, z4], color="blue")
        cmd.pseudoatom("box", name="v1z", pos=[x1, y1, z1], color="blue")
        cmd.select("vertices", "(name v1z,v4z)")
        cmd.bond("vertices", "vertices")
        cmd.delete("vertices")

    def delete_box(self) -> None:
        """
        Callback for the "Delete box" button.

        Deletes box object on PyMOL viewer, disables 'Delete Box' and 'Redraw Box' buttons, enables 'Draw Box' button and set box variables to default values (class Default).
        """
        from pymol import cmd

        # Reset all box variables
        self.x = 0
        self.y = 0
        self.z = 0

        # Delete Box and Vertices objects in PyMOL
        cmd.delete("vertices")
        cmd.delete("box")

        # Set Box variables in the interface
        self.min_x.setValue(self._default.min_x)
        self.max_x.setValue(self._default.max_x)
        self.min_y.setValue(self._default.min_y)
        self.max_y.setValue(self._default.max_y)
        self.min_z.setValue(self._default.min_z)
        self.max_z.setValue(self._default.max_z)
        self.angle1.setValue(self._default.angle1)
        self.angle2.setValue(self._default.angle2)

        # Change state of buttons in the interface
        self.button_draw_box.setEnabled(True)
        self.button_redraw_box.setEnabled(False)
        self.min_x.setEnabled(False)
        self.min_y.setEnabled(False)
        self.min_z.setEnabled(False)
        self.max_x.setEnabled(False)
        self.max_y.setEnabled(False)
        self.max_z.setEnabled(False)
        self.angle1.setEnabled(False)
        self.angle2.setEnabled(False)

    def redraw_box(self) -> None:
        """
        Callback for the "Redraw box" button.

        This method redraws the custom box based on changes in the box variables displayed on the GUI (min_x, max_x, min_y, max_y, min_z, max_z, angle1, angle2 and/or padding) and/or PyMOL viewer (selection object 'sele').

        Warning
        -------
        It is advisable to change one variable at a time to achieve the expected result.
        """
        from pymol import cmd

        # Provided a selection
        if "sele" in cmd.get_names("selections"):
            # Get dimensions of selected residues
            ([min_x, min_y, min_z], [max_x, max_y, max_z]) = cmd.get_extent("sele")

            if (
                self.min_x.value() != self.min_x_set
                or self.max_x.value() != self.max_x_set
                or self.min_y.value() != self.min_y_set
                or self.max_y.value() != self.max_y_set
                or self.min_z.value() != self.min_z_set
                or self.max_z.value() != self.max_z_set
                or self.angle1.value() != self.angle1_set
                or self.angle2.value() != self.angle2_set
            ):
                self.min_x_set = self.min_x.value()
                self.max_x_set = self.max_x.value()
                self.min_y_set = self.min_y.value()
                self.max_y_set = self.max_y.value()
                self.min_z_set = self.min_z.value()
                self.max_z_set = self.max_z.value()
                self.angle1_set = self.angle1.value()
                self.angle2_set = self.angle2.value()
            # Padding or selection altered
            else:
                # Get center of each dimension (x, y, z)
                self.x = (min_x + max_x) / 2
                self.y = (min_y + max_y) / 2
                self.z = (min_z + max_z) / 2

                # Set background box values
                self.min_x_set = (
                    round(self.x - (min_x - self.padding.value()), 1)
                    + self.min_x.value()
                    - self.min_x_set
                )
                self.max_x_set = (
                    round((max_x + self.padding.value()) - self.x, 1)
                    + self.max_x.value()
                    - self.max_x_set
                )
                self.min_y_set = (
                    round(self.y - (min_y - self.padding.value()), 1)
                    + self.min_y.value()
                    - self.min_y_set
                )
                self.max_y_set = (
                    round((max_y + self.padding.value()) - self.y, 1)
                    + self.max_y.value()
                    - self.max_y_set
                )
                self.min_z_set = (
                    round(self.z - (min_z - self.padding.value()), 1)
                    + self.min_z.value()
                    - self.min_z_set
                )
                self.max_z_set = (
                    round((max_z + self.padding.value()) - self.z, 1)
                    + self.max_z.value()
                    - self.max_z_set
                )
                self.angle1_set = 0 + self.angle1.value()
                self.angle2_set = 0 + self.angle2.value()
                self.padding_set = self.padding.value()
        # Not provided a selection
        else:
            if (
                self.min_x.value() != self.min_x_set
                or self.max_x.value() != self.max_x_set
                or self.min_y.value() != self.min_y_set
                or self.max_y.value() != self.max_y_set
                or self.min_z.value() != self.min_z_set
                or self.max_z.value() != self.max_z_set
                or self.angle1.value() != self.angle1_set
                or self.angle2.value() != self.angle2_set
            ):
                self.min_x_set = self.min_x.value()
                self.max_x_set = self.max_x.value()
                self.min_y_set = self.min_y.value()
                self.max_y_set = self.max_y.value()
                self.min_z_set = self.min_z.value()
                self.max_z_set = self.max_z.value()
                self.angle1_set = self.angle1.value()
                self.angle2_set = self.angle2.value()

            if self.padding_set != self.padding.value():
                # Prepare dimensions without old padding
                min_x = self.padding_set - self.min_x_set
                max_x = self.max_x_set - self.padding_set
                min_y = self.padding_set - self.min_y_set
                max_y = self.max_y_set - self.padding_set
                min_z = self.padding_set - self.min_z_set
                max_z = self.max_z_set - self.padding_set

                # Get center of each dimension (x, y, z)
                self.x = (min_x + max_x) / 2
                self.y = (min_y + max_y) / 2
                self.z = (min_z + max_z) / 2

                # Set background box values
                self.min_x_set = round(self.x - (min_x - self.padding.value()), 1)
                self.max_x_set = round((max_x + self.padding.value()) - self.x, 1)
                self.min_y_set = round(self.y - (min_y - self.padding.value()), 1)
                self.max_y_set = round((max_y + self.padding.value()) - self.y, 1)
                self.min_z_set = round(self.z - (min_z - self.padding.value()), 1)
                self.max_z_set = round((max_z + self.padding.value()) - self.z, 1)
                self.angle1_set = self.angle1.value()
                self.angle2_set = self.angle2.value()
                self.padding_set = self.padding.value()

        # Set Box variables in the interface
        self.min_x.setValue(self.min_x_set)
        self.max_x.setValue(self.max_x_set)
        self.min_y.setValue(self.min_y_set)
        self.max_y.setValue(self.max_y_set)
        self.min_z.setValue(self.min_z_set)
        self.max_z.setValue(self.max_z_set)
        self.angle1.setValue(self.angle1_set)
        self.angle2.setValue(self.angle2_set)

        # Redraw box
        self.draw_box()

    def box_adjustment_help(self) -> None:
        """
        Callback for the Help button on the top right corner of the Box adjustment frame.

        This method displays a help message to the user, explaining the variables shown on the Box adjustment frame.
        """
        from PyQt6 import QtCore, QtWidgets

        text = QtCore.QCoreApplication.translate(
            "KVFinderWeb",
            '<html><head/><body><p align="justify"><span style=" font-weight:600; text-decoration: underline;">Box Adjustment mode:</span></p><p align="justify">- Create a selection (optional);</p><p align="justify">- Define a <span style=" font-weight:600;">Padding</span> (optional);</p><p align="justify">- Click on <span style=" font-weight:600;">Draw Box</span> button.</p><p align="justify"><br/><span style="text-decoration: underline;">Customize your <span style=" font-weight:600;">box</span></span>:</p><p align="justify">- Change one item at a time (e.g. <span style=" font-style:italic;">Padding</span>, <span style=" font-style:italic;">Minimum X</span>, <span style=" font-style:italic;">Maximum X</span>, ...);</p><p align="justify">- Click on <span style=" font-weight:600;">Redraw Box</span> button.<br/></p><p><span style=" font-weight:400; text-decoration: underline;">Delete </span><span style=" text-decoration: underline;">box</span><span style=" font-weight:400; text-decoration: underline;">:</span></p><p align="justify">- Click on <span style=" font-weight:600;">Delete Box</span> button.<br/></p><p align="justify"><span style="text-decoration: underline;">Colors of the <span style=" font-weight:600;">box</span> object:</span></p><p align="justify">- <span style=" font-weight:600;">Red</span> corresponds to <span style=" font-weight:600;">X</span> axis;</p><p align="justify">- <span style=" font-weight:600;">Green</span> corresponds to <span style=" font-weight:600;">Y</span> axis;</p><p align="justify">- <span style=" font-weight:600;">Blue</span> corresponds to <span style=" font-weight:600;">Z</span> axis.</p></body></html>',
            None,
        )
        help_information = QtWidgets.QMessageBox(self)
        help_information.setText(text)
        help_information.setWindowTitle("Help")
        help_information.setStyleSheet("QLabel{min-width:500 px;}")
        help_information.exec()

    def create_parameters(self) -> Dict[str, Any]:
        """
        Creates a Python dictionary, containing the detection parameters and molecular structures, for the creation of the KVFinder-web service JSON.

        This method pass the variables defined in the GUI to a Python dictionary that will ultimately be used to create the JSON, which will be sent to KVFinder-web service via HTTP protocol.

        Returns
        -------
        parameters: dict
            Python dictionary containing detection parameters and molecular structures names loaded in PyMOL
        """
        # Create dict
        parameters = dict()

        # title
        parameters["title"] = "KVFinder-web job file"

        # status
        parameters["status"] = "submitting"

        # files
        parameters["files"] = dict()
        # pdb
        if self.input.currentText() != "":
            parameters["files"]["pdb"] = self.input.currentText()
        else:
            from PyQt6 import QtWidgets

            QtWidgets.QMessageBox.critical(self, "Error", "Select an input PDB!")
            return False
        # ligand
        if self.ligand_adjustment.isChecked():
            if self.ligand.currentText() != "":
                parameters["files"]["ligand"] = self.ligand.currentText()
            else:
                from PyQt6 import QtWidgets

                QtWidgets.QMessageBox.critical(self, "Error", "Select an ligand PDB!")
                return False
        # output
        parameters["files"]["output"] = self.output_dir_path.text()
        # base_name
        parameters["files"]["base_name"] = self.base_name.text()

        # modes
        parameters["modes"] = dict()
        # whole protein mode
        parameters["modes"]["whole_protein_mode"] = not self.box_adjustment.isChecked()
        # box adjustment mode
        parameters["modes"]["box_mode"] = self.box_adjustment.isChecked()
        # resolution_mode
        parameters["modes"]["resolution_mode"] = "Low"
        # surface_mode
        parameters["modes"]["surface_mode"] = True
        # kvp_mode
        parameters["modes"]["kvp_mode"] = False
        # ligand_mode
        parameters["modes"]["ligand_mode"] = self.ligand_adjustment.isChecked()

        # step_size
        parameters["step_size"] = dict()
        parameters["step_size"]["step_size"] = 0.0

        # probes
        parameters["probes"] = dict()
        # probe_in
        parameters["probes"]["probe_in"] = self.probe_in.value()
        # probe_out
        parameters["probes"]["probe_out"] = self.probe_out.value()

        if (self.volume_cutoff.value() == 0.0) and (
            self.removal_distance.value() == 0.0
        ):
            from PyQt6 import QtWidgets

            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Removal distance and Volume Cutoff cannot be zero at the same time!",
            )
            return False

        # cutoffs
        parameters["cutoffs"] = dict()
        # volume_cutoff
        parameters["cutoffs"]["volume_cutoff"] = self.volume_cutoff.value()
        # ligand_cutoff
        parameters["cutoffs"]["ligand_cutoff"] = self.ligand_cutoff.value()
        # removal_distance
        parameters["cutoffs"]["removal_distance"] = self.removal_distance.value()

        # visiblebox
        box = self.create_box_parameters()
        parameters["visiblebox"] = dict()
        parameters["visiblebox"].update(box)

        # internalbox
        box = self.create_box_parameters(is_internal_box=True)
        parameters["internalbox"] = dict()
        parameters["internalbox"].update(box)

        return parameters

    def create_box_parameters(
        self, is_internal_box=False
    ) -> Dict[str, Dict[str, float]]:
        """
        Create custom box coordinates (P1, P2, P3 and P4) that limits the search space in the box adjustment mode.

        parKVFinder software uses two sets of box to perform the cavity detection (a private box - called internal - and a visible box). The visible box is smaller than the private box by the contribution of the Probe Out size in each axis.

        Parameters
        ----------
        is_internal_box: bool
            Whether the box coordinates being calculated are of the internal box (private box)

        Returns
        -------
        box: dict
            A Python dictionary containing xyz coordinates for P1 (origin), P2 (X-axis), P3 (Y-axis) and P4 (Z-axis) of the internal or visible box
        """
        from math import cos, pi, sin

        # Get box parameters
        if self.box_adjustment.isChecked():
            min_x = self.min_x_set
            max_x = self.max_x_set
            min_y = self.min_y_set
            max_y = self.max_y_set
            min_z = self.min_z_set
            max_z = self.max_z_set
            angle1 = self.angle1_set
            angle2 = self.angle2_set
        else:
            min_x = 0.0
            max_x = 0.0
            min_y = 0.0
            max_y = 0.0
            min_z = 0.0
            max_z = 0.0
            angle1 = 0.0
            angle2 = 0.0

        # Add probe_out to internal box
        if is_internal_box:
            min_x += self.probe_out.value()
            max_x += self.probe_out.value()
            min_y += self.probe_out.value()
            max_y += self.probe_out.value()
            min_z += self.probe_out.value()
            max_z += self.probe_out.value()

        # Convert angle
        angle1 = (angle1 / 180.0) * pi
        angle2 = (angle2 / 180.0) * pi

        # Get positions of box vertices
        # P1
        x1 = (
            -min_x * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + self.x
        )

        y1 = -min_y * cos(angle1) + (-min_z) * sin(angle1) + self.y

        z1 = (
            min_x * sin(angle2)
            + min_y * sin(angle1) * cos(angle2)
            - min_z * cos(angle1) * cos(angle2)
            + self.z
        )

        # P2
        x2 = (
            max_x * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + self.x
        )

        y2 = (-min_y) * cos(angle1) + (-min_z) * sin(angle1) + self.y

        z2 = (
            (-max_x) * sin(angle2)
            - (-min_y) * sin(angle1) * cos(angle2)
            + (-min_z) * cos(angle1) * cos(angle2)
            + self.z
        )

        # P3
        x3 = (
            (-min_x) * cos(angle2)
            - max_y * sin(angle1) * sin(angle2)
            + (-min_z) * cos(angle1) * sin(angle2)
            + self.x
        )

        y3 = max_y * cos(angle1) + (-min_z) * sin(angle1) + self.y

        z3 = (
            -(-min_x) * sin(angle2)
            - max_y * sin(angle1) * cos(angle2)
            + (-min_z) * cos(angle1) * cos(angle2)
            + self.z
        )

        # P4
        x4 = (
            (-min_x) * cos(angle2)
            - (-min_y) * sin(angle1) * sin(angle2)
            + max_z * cos(angle1) * sin(angle2)
            + self.x
        )

        y4 = (-min_y) * cos(angle1) + max_z * sin(angle1) + self.y

        z4 = (
            -(-min_x) * sin(angle2)
            - (-min_y) * sin(angle1) * cos(angle2)
            + max_z * cos(angle1) * cos(angle2)
            + self.z
        )

        # Create points
        p1 = {"x": x1, "y": y1, "z": z1}
        p2 = {"x": x2, "y": y2, "z": z2}
        p3 = {"x": x3, "y": y3, "z": z3}
        p4 = {"x": x4, "y": y4, "z": z4}
        box = {"p1": p1, "p2": p2, "p3": p3, "p4": p4}

        return box

    def closeEvent(self, event) -> None:
        """
        Add one step to closeEvent of QMainWindow.

        This method works as a garbage collector for our global dialog after closing the GUI.
        """
        global dialog
        dialog = None

    def _start_worker_thread(self) -> bool:
        """
        Start the worker thread that communicate the GUI with the KVFinder-web service.

        This method establish some connections between Slots and Signals of the GUI thread and the worker thread.
        """
        # Get KVFinder-web service status
        server_status = _check_server_status(self.server)

        # Start Worker thread
        self.thread = Worker(self.server, server_status)
        self.thread.start()

        # Communication between GUI and Worker threads
        self.thread.id_signal.connect(self.msg_results_not_available)
        self.thread.server_down.connect(self.server_down)
        self.thread.server_up.connect(self.server_up)
        self.thread.server_status_signal.connect(self.set_server_status)
        self.thread.available_jobs_signal.connect(self.set_available_jobs)
        self.msgbox_signal.connect(self.thread.wait_status)

        return True

    def add_id(self) -> None:
        """
        Callback for "Add ID" button.

        This method creates a Job ID Form (class Form) and when submitted, calls a method to check the Job ID in the KVFinder-web service.
        """
        # Create Form
        form = Form(self.server, self.output_dir_path.text())
        reply = form.exec()

        if reply:
            # Get data from form
            self.data = form.get_data()

            # Check job id
            self._check_job_id(self.data)

        return

    def _check_job_id(self, data: Dict[str, Any]) -> None:
        """
        Checks a Job ID in the KVFinder-web service.

        Parameters
        ----------
        data: dict
            A Python dictionary containing the data of a Job ID Form (class Form)
        """
        from PyQt6 import QtNetwork
        from PyQt6.QtCore import QUrl

        if verbosity in [1, 3]:
            print(f"[==> Requesting Job ID ({data['id']}) to KVFinder-web service ...")

        try:
            # Prepare request
            url = QUrl(f"{self.server}/{data['id']}")
            request = QtNetwork.QNetworkRequest(url)
            request.setHeader(
                QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader,
                "application/json",
            )

            # Get Request
            self.reply = self.network_manager.get(request)
            self.reply.finished.connect(self._handle_get_response)
        except Exception as e:
            print("Error occurred: ", e)

    def _handle_get_response(self) -> None:
        """
        This methods handles the GET method response.

        If there are no error in the request, this methods evaluates the response and process accordingly, by writing incoming results and job information to files.

        If there are an error in the request, this method displays a QMessageBox with the corresponding error message and HTTP error code.
        """
        from PyQt6 import QtNetwork

        # Get QNetwork error status
        error = self.reply.error()

        if error == QtNetwork.QNetworkReply.NetworkError.NoError:
            # Read data retrived from server
            reply = json.loads(str(self.reply.readAll(), "utf-8"))

            # Create parameters
            parameters = {
                "status": reply["status"],
                "id_added_manually": True,
                "files": self.data["files"],
                "modes": None,
                "step_size": None,
                "probes": None,
                "cutoffs": None,
                "visiblebox": None,
                "internalbox": None,
            }
            if parameters["files"]["pdb"] is not None:
                parameters["files"]["pdb"] = os.path.basename(
                    parameters["files"]["pdb"]
                ).replace(".pdb", "")
            if parameters["files"]["ligand"] is not None:
                parameters["files"]["ligand"] = os.path.basename(
                    parameters["files"]["ligand"]
                ).replace(".pdb", "")

            # Create job file
            job = Job(parameters)
            job.id = self.data["id"]
            job.id_added_manually = True
            job.status = reply["status"]
            job.output = reply

            # Save job
            job.save(job.id)

            # Message to user
            if verbosity in [1, 3]:
                print("> Job successfully added!")
            message = Message("Job successfully added!", job.id, job.status)
            message.exec()

            # Include job to available jobs
            self.available_jobs.addItem(job.id)

            # Export
            if job.status == "completed":
                try:
                    job.export()
                except Exception as e:
                    print("Error occurred: ", e)

        elif error == QtNetwork.QNetworkReply.NetworkError.ContentNotFoundError:
            from PyQt6 import QtWidgets

            # Message to user
            if verbosity in [1, 3]:
                print(
                    f"> Job ID ({self.data['id']}) was not found in KVFinder-web service!"
                )
            QtWidgets.QMessageBox.critical(
                self,
                "Job Submission",
                f"Job ID ({self.data['id']}) was not found in KVFinder-web service!",
            )

        elif error == QtNetwork.QNetworkReply.NetworkError.ConnectionRefusedError:
            from PyQt6 import QtWidgets

            # Message to user
            if verbosity in [1, 3]:
                print("> KVFinder-web service is Offline! Try again later!\n")
            QtWidgets.QMessageBox.critical(
                self,
                "Job Submission",
                "KVFinder-web service is Offline!\n\nTry again later!",
            )

        # Clean data
        self.data = None

    def show_id(self) -> None:
        """
        Callback for "Show" button.

        This method gets the Job ID selected in the Available Jobs combo box and calls method to load its results.
        """
        # Get job ID
        job_id = self.available_jobs.currentText()

        # Message to user
        print(f"> Displaying results from Job ID: {job_id}")

        # Get job path
        job_fn = os.path.join(
            os.path.expanduser("~"),
            ".KVFinder-web",
            self.available_jobs.currentText(),
            "job.toml",
        )

        # Get job information of ID
        with open(job_fn, "r") as f:
            job_info = toml.load(f=f)

        # Set results file
        results_file = f"{job_info['files']['output']}/{job_id}/{job_info['files']['base_name']}.KVFinder.results.toml"
        self.vis_results_file_entry.setText(results_file)

        # Select Visualization tab
        self.results_tabs.setCurrentIndex(1)

        # Load results
        self.load_results()

    def load_results(self) -> None:
        """
        Callback for "Load" button.

        This method gets a path of results file and loads it on the visualization tab.
        The information loaded include: Input file, Ligand file, Cavities file, Step Size, Volume, Area and Interface Residues. Additionaly, it loads all files on PyMOL viewer.
        """
        from pymol import cmd

        # Get results file
        results_file = self.vis_results_file_entry.text()

        # Check if results file exist
        if os.path.exists(results_file) and results_file.endswith(".toml"):
            print(f"> Loading results from: {self.vis_results_file_entry.text()}")
        else:
            from PyQt6 import QtWidgets

            error_msg = QtWidgets.QMessageBox.critical(
                self, "Error", "Results file cannot be opened! Check results file path."
            )
            return False

        # Create global variable for results
        global results

        # Read results file
        results = toml.load(results_file)

        if "FILES" in results.keys():
            results["FILES_PATH"] = results.pop("FILES")
        elif "FILES_PATH" in results.keys():
            pass
        else:
            from PyQt6 import QtWidgets

            error_msg = QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Results file has incorrect format! Please check your file.",
            )
            error_msg.exec()
            return False

        if "PARAMETERS" in results.keys():
            if "STEP" in results["PARAMETERS"].keys():
                results["PARAMETERS"]["STEP_SIZE"] = results["PARAMETERS"].pop("STEP")

        # Clean results
        self.clean_results()

        # Refresh information
        self.refresh_information()

        # Refresh volume
        self.refresh_volume()

        # Refresh area
        self.refresh_area()

        # Refresh depth
        self.refresh_avg_depth()
        self.refresh_max_depth()

        # Refresh hydropathy
        self.refresh_avg_hydropathy()

        # Refresh residues
        self.refresh_residues()

        # Set default view in results
        self.default_view.setChecked(True)

        # Load files as PyMOL objects
        cmd.delete("cavities")
        cmd.delete("residues")
        cmd.frame(1)

        # Load input
        if "INPUT" in results["FILES_PATH"].keys():
            input_fn = results["FILES_PATH"]["INPUT"]
            self.input_pdb = os.path.basename(input_fn.replace(".pdb", ""))
            self.load_file(input_fn, self.input_pdb)
        else:
            self.input_pdb = None

        # Load ligand
        if "LIGAND" in results["FILES_PATH"].keys():
            ligand_fn = results["FILES_PATH"]["LIGAND"]
            self.ligand_pdb = os.path.basename(ligand_fn.replace(".pdb", ""))
            self.load_file(ligand_fn, self.ligand_pdb)
        else:
            self.ligand_pdb = None

        # Load cavity
        cavity_fn = results["FILES_PATH"]["OUTPUT"]
        self.cavity_pdb = os.path.basename(cavity_fn.replace(".pdb", ""))
        self.load_cavity(cavity_fn, self.cavity_pdb)

        return

    def select_results_file(self) -> None:
        """
        Callback for the "Browse ..." button

        This method opens a QFileDialog to select a results file of parKVFinder.
        """
        from PyQt6 import QtCore, QtWidgets

        # Get results file
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            caption="Choose KVFinder Results File",
            directory=os.getcwd(),
            filter="KVFinder Results File (*.KVFinder.results.toml);;All files (*)",
        )

        if fname:
            fname = QtCore.QDir.toNativeSeparators(fname)
            if os.path.exists(fname):
                self.vis_results_file_entry.setText(fname)

        return

    @staticmethod
    def load_cavity(fname, name) -> None:
        """
        Load cavities object from filename.

        This method removes old objects with the same name from PyMOL viewer and then, it loads the cavities on it.

        Parameters
        ----------
        fname: str
            Cavity file path
        name: str
            Cavity object name
        """
        from pymol import cmd

        # Remove previous results in objects with same cavity name
        for obj in cmd.get_names("all"):
            if name == obj:
                cmd.delete(obj)

        # Load cavity filename
        if os.path.exists(fname):
            cmd.load(fname, name, zoom=0)
            cmd.hide("everything", name)
            cmd.show("nonbonded", name)

    @staticmethod
    def load_file(fname, name) -> None:
        """
        Load a molecular structure object from filename.

        This method removes old objects with the same name from PyMOL viewer and then, it loads the molecular structure on it.

        Parameters
        ----------
        fname: str
            Path of a PDB-formatted file.
        name: str
            Object name
        """
        from pymol import cmd

        # Remove previous results in objects with same pdb name
        for obj in cmd.get_names("all"):
            if name == obj:
                cmd.delete(obj)

        # Load pdb filename
        if os.path.exists(fname):
            cmd.load(fname, name, zoom=0)

    def refresh_information(self) -> None:
        """
        Fill "Information" frame on the Visualization tab.
        """
        # Input File
        if "INPUT" in results["FILES_PATH"].keys():
            self.vis_input_file_entry.setText(f"{results['FILES_PATH']['INPUT']}")
        else:
            self.vis_input_file_entry.setText(f"")

        # Ligand File
        if "LIGAND" in results["FILES_PATH"].keys():
            self.vis_ligand_file_entry.setText(f"{results['FILES_PATH']['LIGAND']}")
        else:
            self.vis_ligand_file_entry.setText(f"")

        # Cavities File
        self.vis_cavities_file_entry.setText(f"{results['FILES_PATH']['OUTPUT']}")

        # Step Size
        if "PARAMETERS" in results.keys():
            if "STEP_SIZE" in results["PARAMETERS"].keys():
                self.vis_step_size_entry.setText(
                    f"{results['PARAMETERS']['STEP_SIZE']:.2f}"
                )

        return

    def refresh_volume(self) -> None:
        """
        Fill "Volume" QListBox with volume information of the results file.
        """
        # Get cavity indexes
        indexes = sorted(results["RESULTS"]["VOLUME"].keys())
        # Include Volume
        for index in indexes:
            item = f"{index}: {results['RESULTS']['VOLUME'][index]}"
            self.volume_list.addItem(item)
        return

    def refresh_area(self) -> None:
        """
        Fill "Surface Area" QListBox with volume information of the results file.
        """
        # Get cavity indexes
        indexes = sorted(results["RESULTS"]["AREA"].keys())
        # Include Area
        for index in indexes:
            item = f"{index}: {results['RESULTS']['AREA'][index]}"
            self.area_list.addItem(item)
        return

    def refresh_avg_depth(self) -> None:
        # Get cavity indexes
        indexes = sorted(results["RESULTS"]["AVG_DEPTH"].keys())
        # Include Average Depth
        for index in indexes:
            item = f"{index}: {results['RESULTS']['AVG_DEPTH'][index]}"
            self.avg_depth_list.addItem(item)
        return

    def refresh_max_depth(self) -> None:
        # Get cavity indexes
        indexes = sorted(results["RESULTS"]["MAX_DEPTH"].keys())
        # Include Maximum Depth
        for index in indexes:
            item = f"{index}: {results['RESULTS']['MAX_DEPTH'][index]}"
            self.max_depth_list.addItem(item)
        return

    def refresh_avg_hydropathy(self) -> None:
        # Get cavity indexes
        indexes = sorted(results["RESULTS"]["AVG_HYDROPATHY"].keys())
        # Include Average Hydropathy
        for index in indexes:
            if index != "EisenbergWeiss":
                item = f"{index}: {results['RESULTS']['AVG_HYDROPATHY'][index]}"
                self.avg_hydropathy_list.addItem(item)
        return

    def refresh_residues(self) -> None:
        """
        Fill "Interface Residues" QListBox with volume information of the results file.
        """
        # Get cavity indexes
        indexes = sorted(results["RESULTS"]["RESIDUES"].keys())
        # Include Interface Residues
        for index in indexes:
            self.residues_list.addItem(index)
        return

    def show_residues(self) -> None:
        """
        Creates a object named 'residues' on PyMOL viewer to display interface residues surrounding the cavity tags selected on the "Interface Residues" QListBox.
        """
        from pymol import cmd

        # Get selected cavities from residues list
        cavs = [item.text() for item in self.residues_list.selectedItems()]

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("res")
        cmd.delete("residues")

        # Return if no cavity is selected
        if len(cavs) < 1:
            return

        # Get residues from cavities selected
        residues = []
        for cav in cavs:
            for residue in results["RESULTS"]["RESIDUES"][cav]:
                if residue not in residues:
                    residues.append(residue)

        # Check if input pdb is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.input_pdb:
                control = 1
        if control == 0:
            return

        # Select residues
        command = f"{self.input_pdb} and"
        while len(residues) > 0:
            res, chain, _ = residues.pop(0)
            command = f"{command} (resid {res} and chain {chain}) or"
        command = f"{command[:-3]}"
        cmd.select("res", command)

        # Create residues object
        cmd.create("residues", "res")
        cmd.delete("res")
        cmd.hide("everything", "residues")
        cmd.show("sticks", "residues")
        cmd.disable(self.cavity_pdb)
        cmd.enable(self.cavity_pdb)
        cmd.set("auto_zoom", 1)

    def show_cavities(self, list1, list2) -> None:
        from pymol import cmd

        # Get items from list1
        cavs = [item.text()[0:3] for item in list1.selectedItems()]

        # Select items of list2
        number_of_items = list1.count()
        for index in range(number_of_items):
            if list2.item(index).text()[0:3] in cavs:
                list2.item(index).setSelected(True)
            else:
                list2.item(index).setSelected(False)

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("cavs")
        cmd.delete("cavities")

        # Return if no cavity is selected
        if len(cavs) < 1:
            return

        # Check if cavity file is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.cavity_pdb:
                control = 1
        if control == 0:
            return

        # Color filling cavity points as blue nonbonded
        command = f"obj {self.cavity_pdb} and (resname "
        while len(cavs) > 0:
            command = f"{command}{cavs.pop(0)},"
        command = f"{command[:-1]})"
        cmd.select("cavs", command)

        # Create cavities object with blue nonbonded
        cmd.create("cavities", "cavs")
        cmd.delete("cavs")
        cmd.color("blue", "cavities")
        cmd.show("nonbonded", "cavities")

        # Color surface cavity points as red nb_spheres
        cmd.select("cavs", "cavities and name HS+HA")
        cmd.color("red", "cavs")
        cmd.show("nb_spheres", "cavs")
        cmd.delete("cavs")

        # Reset cavities output object
        cmd.disable(self.cavity_pdb)
        cmd.enable(self.cavity_pdb)
        for item in cmd.get_names("all"):
            if item == "hydropathy":
                cmd.disable("hydropathy")
                cmd.enable("hydropathy")
            if item == "depths":
                cmd.disable("depths")
                cmd.enable("depths")
        cmd.set("auto_zoom", 1)

    def show_depth(self, list1, list2) -> None:
        from pymol import cmd

        # Get items from list1
        cavs = [item.text()[0:3] for item in list1.selectedItems()]

        # Select items of list2
        number_of_items = list1.count()
        for index in range(number_of_items):
            if list2.item(index).text()[0:3] in cavs:
                list2.item(index).setSelected(True)
            else:
                list2.item(index).setSelected(False)

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("deps")
        cmd.delete("depths")

        # Return if no cavity is selected
        if len(cavs) < 1:
            return

        # Check if cavity file is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.cavity_pdb:
                control = 1
        if control == 0:
            return

        # Color filling cavity points as blue nonbonded
        command = f"obj {self.cavity_pdb} and (resname "
        while len(cavs) > 0:
            command = f"{command}{cavs.pop(0)},"
        command = f"{command[:-1]})"
        cmd.select("deps", command)

        # Create cavities object with blue nonbonded
        cmd.create("depths", "deps")
        cmd.delete("deps")
        cmd.spectrum("b", "rainbow", "depths")
        cmd.show("nb_spheres", "depths")

        # Reset cavities output object
        cmd.disable(self.cavity_pdb)
        for item in cmd.get_names("all"):
            if item == "cavities":
                cmd.disable("cavities")
                cmd.enable("cavities")
            if item == "depths":
                cmd.disable("hydropathy")
                cmd.enable("hydropathy")
        cmd.enable(self.cavity_pdb)
        cmd.set("auto_zoom", 1)

    def show_hydropathy(self, list1) -> None:
        from pymol import cmd

        # Get items from list1
        cavs = [item.text()[0:3] for item in list1.selectedItems()]

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("hyd")
        cmd.delete("hydropathy")

        # Return if no cavity is selected
        if len(cavs) < 1:
            return

        # Check if cavity file is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.cavity_pdb:
                control = 1
        if control == 0:
            return

        # Color filling cavity points as blue nonbonded
        command = f"obj {self.cavity_pdb} and (resname "
        while len(cavs) > 0:
            command = f"{command}{cavs.pop(0)},"
        command = f"{command[:-1]}) and (name HA+HS)"
        cmd.select("hyd", command)

        # Create cavities object with blue nonbonded
        cmd.create("hydropathy", "hyd")
        cmd.delete("hyd")
        cmd.spectrum("q", "yellow_white_blue", "hydropathy")
        cmd.show("nb_spheres", "hydropathy")

        # Reset cavities output object
        cmd.disable(self.cavity_pdb)
        for item in cmd.get_names("all"):
            if item == "cavities":
                cmd.disable("cavities")
                cmd.enable("cavities")
            if item == "depths":
                cmd.disable("depths")
                cmd.enable("depths")
        cmd.enable(self.cavity_pdb)
        cmd.set("auto_zoom", 1)

    def show_default_view(self) -> None:
        from pymol import cmd

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("view")

        # Check if cavity file is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.cavity_pdb:
                control = 1
        if control == 0:
            return

        # Color filling cavity points as blue nonbonded
        command = f"obj {self.cavity_pdb} and (name H+HA+HS)"
        command = f"{command[:-1]})"
        cmd.select("view", command)

        # Create cavities object with blue nonbonded
        cmd.hide("everything", self.cavity_pdb)
        cmd.show("nonbonded", "view")
        cmd.color("white", "view")
        cmd.delete("view")

    def show_depth_view(self) -> None:
        from pymol import cmd

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("view")

        # Check if cavity file is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.cavity_pdb:
                control = 1
        if control == 0:
            return

        # Color filling cavity points as blue nonbonded
        command = f"obj {self.cavity_pdb} and (name H+HA+HS)"
        command = f"{command[:-1]})"
        cmd.select("view", command)

        # Create cavities object with blue nonbonded
        cmd.hide("everything", self.cavity_pdb)
        cmd.show("nonbonded", "view")
        cmd.spectrum("b", "rainbow", "view")
        cmd.delete("view")

    def show_hydropathy_view(self) -> None:
        from pymol import cmd

        # Clean objects
        cmd.set("auto_zoom", 0)
        cmd.delete("view")

        # Check if cavity file is loaded
        control = 0
        for item in cmd.get_names("all"):
            if item == self.cavity_pdb:
                control = 1
        if control == 0:
            return

        # Color filling cavity points as blue nonbonded
        command = f"obj {self.cavity_pdb} and (name HA+HS)"
        command = f"{command[:-1]})"
        cmd.select("view", command)

        # Create cavities object with blue nonbonded
        cmd.hide("everything", self.cavity_pdb)
        cmd.show("nonbonded", "view")
        cmd.spectrum("q", "yellow_white_blue", "view")
        cmd.delete("view")

    def clean_results(self) -> None:
        """
        Clean the "Visualization" tab.

        This method removes all information displayed in the fields of the "Visualization" tab.
        """
        # Input File
        self.vis_input_file_entry.setText(f"")

        # Ligand File
        self.vis_ligand_file_entry.setText(f"")

        # Cavities File
        self.vis_cavities_file_entry.setText(f"")

        # Step Size
        self.vis_step_size_entry.setText(f"")

        # Volume
        self.volume_list.clear()

        # Area
        self.area_list.clear()

        # Depth
        self.avg_depth_list.clear()
        self.max_depth_list.clear()

        # Hydropathy
        self.avg_hydropathy_list.clear()

        # Residues
        self.residues_list.clear()

    @QtCore.pyqtSlot(bool)
    def set_server_status(self, status) -> None:
        """
        PyQt Slot to change the "Server Status" field to Online or Offline.
        """
        if status:
            self.server_up()
        else:
            self.server_down()

    @QtCore.pyqtSlot()
    def server_up(self) -> None:
        """
        PyQt Slot to change the "Server Status" field to Online.
        """
        self.server_status.clear()
        self.server_status.setText("Online")
        self.server_status.setStyleSheet("color: green;")

    @QtCore.pyqtSlot()
    def server_down(self) -> None:
        """
        PyQt Slot to change the "Server Status" field to Offline.
        """
        self.server_status.clear()
        self.server_status.setText("Offline")
        self.server_status.setStyleSheet("color: red;")

    @QtCore.pyqtSlot(list)
    def set_available_jobs(self, available_jobs) -> None:
        """
        PyQt Slot to add the jobs of the available_jobs variable to the "Available Jobs" combo box.

        Parameters
        ----------
        available_jobs: list
            A list of jobs currently in the KVFinder-web service
        """
        # Get current selected job
        current = self.available_jobs.currentText()

        # Update available jobs
        self.available_jobs.clear()
        self.available_jobs.addItems(available_jobs)

        # If current still in available jobs, select it
        if current in available_jobs:
            self.available_jobs.setCurrentText(current)

    def fill_job_information(self) -> None:
        """
        Automatically fill the information of the Job ID selected on the "Available Jobs" combo box.

        This method displays, on "Job Information" frame, the job status, input file, ligand file, output directory and parameters file.
        """
        if self.available_jobs.currentText() != "":
            # Get job path
            job_fn = os.path.join(
                os.path.expanduser("~"),
                ".KVFinder-web",
                self.available_jobs.currentText(),
                "job.toml",
            )

            # Read job file
            with open(job_fn, "r") as f:
                job_info = toml.load(f=f)

            # Fill job information labels
            status = job_info["status"].capitalize()
            if status == "Queued" or status == "Running":
                self.job_status_entry.setText(status)
                self.job_status_entry.setStyleSheet("color: blue;")
                # Disable button
                self.button_show_job.setEnabled(False)
            elif status == "Completed":
                self.job_status_entry.setText(status)
                self.job_status_entry.setStyleSheet("color: green;")
                # Enable button
                self.button_show_job.setEnabled(True)
            # Input file
            if "pdb" in job_info["files"].keys():
                self.job_input_entry.setText(f"{job_info['files']['pdb']}")
            else:
                self.job_input_entry.clear()
            # Ligand file
            if "ligand" in job_info["files"].keys():
                self.job_ligand_entry.setText(f"{job_info['files']['ligand']}")
            else:
                self.job_ligand_entry.clear()
            # Output directory
            self.job_output_dir_path_entry.setText(f"{job_info['files']['output']}")
            # ID added manually
            if "id_added_manually" in job_info.keys():
                if job_info["id_added_manually"]:
                    self.job_parameters_entry.setText(f"Not available")
                    if "pdb" not in job_info["files"].keys():
                        self.job_input_entry.setText(f"Not available")
                    if "ligand" not in job_info["files"].keys():
                        self.job_ligand_entry.setText(f"Not available")
            else:
                self.job_parameters_entry.setText(
                    f"{job_info['files']['output']}/{self.available_jobs.currentText()}/{job_info['files']['base_name']}_parameters.toml"
                )
        else:
            # Disable button
            self.button_show_job.setEnabled(False)
            # Fill job information labels
            self.job_status_entry.clear()
            self.job_input_entry.clear()
            self.job_ligand_entry.clear()
            self.job_output_dir_path_entry.clear()
            self.job_parameters_entry.clear()

    @QtCore.pyqtSlot(str)
    def msg_results_not_available(self, job_id) -> None:
        """
        PyQt Slot to inform the user that a job, registered on ~/.KVFinder-web directory, is no longer available on the KVFinder-web service.

        Parameters
        ----------
        job_id: str
            Job ID
        """
        from PyQt6 import QtWidgets

        # Message to user
        message = QtWidgets.QMessageBox(self)
        message.setWindowTitle(f"Job Notification")
        message.setText(
            f"Job ID: {job_id}\nThis job is not available anymore in KVFinder-web service!\n"
        )
        message.setInformativeText(
            f"Jobs are kept for {days_job_expire} days after completion."
        )
        if message.exec() == QtWidgets.QMessageBox.Ok:
            # Send signal to Worker thread
            self.msgbox_signal.emit(False)

