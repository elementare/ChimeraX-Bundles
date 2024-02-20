#! /usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
#  This is the KVFinder-web service client for PyMOL. It was developed using  #
#  Qt interface and Python. Changes in this file are not advised, as it       #
#  controls all interactions with KVFinder-web service.                       #
#                                                                             #
#  PyMOL KVFinder Web Tools is free software: you can redistribute it and/or  #
#  modify it under the terms of the GNU General Public License as published   #
#  by the Free Software Foundation, either version 3 of the License, or       #
#  (at your option) any later version.                                        #
#                                                                             #
#  PyMOL KVFinder Web Tools is distributed in the hope that it will be        #
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of     #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the              #
#  GNU General Public License for more details.                               #
#                                                                             #
#  You should have received a copy of the GNU General Public License along    #
#  with PyMOL KVFinder Web Tools. If not, see <http://www.gnu.org/licenses/>. #
#                                                                             #
###############################################################################

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


class _Default(object):
    """
    Object with default detection parameters of parKVFinder software

    Attributes
    ----------
    probe_in: float
        Probe In size (A)
    probe_out: float
        Probe Out size (A)
    removal_distance: float
        Length to be removed from the cavity-bulk frontier (A)
    volume_cutoff: float
        Cavities volume filter (A3)
    base_name: str
        Base name for any outputted file
    output_dir_path: str
        Path of the output directory
    box_adjustment: bool
        Whether the box adjustment mode is enabled
    x: float
        x coordinate of the center of the box
    y: float
        y coordinate of the center of the box
    z: float
        z coordinate of the center of the box
    min_x: float
        Distance of the minimum x coordinate from x coordinate of the center of the box
    max_x: float
        Distance of the maximum x coordinate from x coordinate of the center of the box
    min_y: float
        Distance of the minimum y coordinate from y coordinate of the center of the box
    max_y: float
        Distance of the maximum y coordinate from y coordinate of the center of the box
    min_z: float
        Distance of the minimum z coordinate from z coordinate of the center of the box
    max_z: float
        Distance of the maximum z coordinate from z coordinate of the center of the box
    angle1: float
        Angle 1 of the custom box
    angle2: float
        Angle 2 of the custom box
    padding: float
        Padding of the custom box
    ligand_adjustment: bool
        Whether the ligand adjustment mode is enabled
    ligand_cutoff: float
        Length to limit a space around a ligand (A)
    """

    def __init__(self):
        super(_Default, self).__init__()
        """
        Initialize class with defult detection parameters in attributes
        """

        # Main Parameters #
        self.probe_in = 1.4
        self.probe_out = 4.0
        self.removal_distance = 2.4
        self.volume_cutoff = 5.0
        self.base_name = "output"
        self.output_dir_path = os.getcwd()
        # Search Space #
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


def __init_plugin__(app=None):
    """
    Add an entry to the PyMOL "Plugin" menu
    """
    from pymol.plugins import addmenuitemqt

    addmenuitemqt("PyMOL KVFinder-web Tools", run_plugin_gui)


def run_plugin_gui():
    """
    Open PyMOL KVFinder-web Tools dialog
    """
    import sys

    global dialog

    if dialog is None:
        dialog = QtWidgets.QApplication([])
        window = PyMOLKVFinderWebTools()
        window.show()
    dialog.exec()


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


class Job(object):
    """
    KVFinder-web job

    Object handles job information.
    """

    def __init__(self, parameters: Optional[Dict[str, Any]]):
        """
        Create a Job object with default attributes and fill it with the parameters from the GUI.

        Parameters
        ----------
        parameters: dict
            Python dictionary containing detection parameters and molecular structures names loaded in PyMOL
        """
        # Job Information (local)
        self.status: Optional[str] = None
        self.pdb: Optional[str] = None
        self.ligand: Optional[str] = None
        self.output_directory: Optional[str] = None
        self.base_name: Optional[str] = None
        self.id_added_manually: Optional[bool] = False
        # Request information (server)
        self.id: Optional[str] = None
        self.input: Optional[Dict[str, Any]] = {}
        self.output: Optional[Dict[str, Any]] = None
        # Upload parameters in self.input
        self.upload(parameters)

    @property
    def cavity(self) -> Optional[Dict[str, Any]]:
        """
        Defines cavity as a property.

        If the output is None, there are no cavities. Otherwise, there are.
        """
        if self.output is None:
            return None
        else:
            return self.output["output"]["pdb_kv"]

    @property
    def report(self) -> Optional[Dict[str, Any]]:
        """
        Defines report as a property.

        If the output is None, there is no report. Otherwise, there is.
        """
        if self.output is None:
            return None
        else:
            return self.output["output"]["report"]

    @property
    def log(self) -> Optional[Dict[str, Any]]:
        """
        Defines log as a property.

        If the output is None, there is no log. Otherwise, there is.
        """
        if self.output is None:
            return None
        else:
            return self.output["output"]["log"]

    def _add_pdb(self, pdb_fn: str, is_ligand: bool = False) -> None:
        """
        Reads a PDB-formatted file of a molecular structure to be sent to KVFinder-web service.

        The file is passed as a list of lines to a attribute of Job.

        Parameters
        ----------
        pdb_fn: str
            Path to a PDB-formatted file
        is_ligand: bool
            Whether the molecular structure should be treated as a ligand in parKVFinder software
        """
        with open(pdb_fn) as f:
            pdb = f.read()
        if is_ligand:
            self.input["pdb_ligand"] = pdb
        else:
            self.input["pdb"] = pdb

    def upload(self, parameters: Optional[Dict[str, Any]]) -> None:
        """
        Loads job information from a Python dictionary containing the parameters.

        Parameters
        ----------
        parameters: dict
            Python dictionary containing detection parameters and molecular structures names loaded in PyMOL
        """
        from pymol import cmd

        # Job Information (local)
        # Status
        self.status = parameters["status"]
        # ID Added Manually
        if "id_added_manually" in parameters.keys():
            if parameters["id_added_manually"]:
                self.id_added_manually = parameters["id_added_manually"]
        # Output directory
        self.output_directory = parameters["files"]["output"]
        # Base_name
        self.base_name = parameters["files"]["base_name"]
        # Input PDB
        if "pdb" in parameters["files"].keys():
            if parameters["files"]["pdb"] is not None:
                self.pdb = os.path.join(
                    self.output_directory, parameters["files"]["pdb"] + ".pdb"
                )
                if not os.path.exists(self.pdb):
                    if parameters["files"]["pdb"] in cmd.get_names("all"):
                        cmd.save(self.pdb, parameters["files"]["pdb"], 0, "pdb")
        # Ligand PDB
        if "ligand" in parameters["files"].keys():
            if parameters["files"]["ligand"] is not None:
                self.ligand = os.path.join(
                    self.output_directory, parameters["files"]["ligand"] + ".pdb"
                )
                if not os.path.exists(self.ligand):
                    if parameters["files"]["ligand"] in cmd.get_names("all"):
                        cmd.save(self.ligand, parameters["files"]["ligand"], 0, "pdb")
        # Request information (service)
        # Input PDB
        if self.pdb:
            self._add_pdb(self.pdb)
        # Ligand PDB
        if self.ligand:
            self._add_pdb(self.ligand, is_ligand=True)
        # Settings
        self.input["settings"] = dict()
        # Modes
        self.input["settings"]["modes"] = parameters["modes"]
        # Step size
        self.input["settings"]["step_size"] = parameters["step_size"]
        # Probes
        self.input["settings"]["probes"] = parameters["probes"]
        # Cutoffs
        self.input["settings"]["cutoffs"] = parameters["cutoffs"]
        # Visible box
        self.input["settings"]["visiblebox"] = parameters["visiblebox"]
        # Internal box
        self.input["settings"]["internalbox"] = parameters["internalbox"]

    def save(self, id: int) -> None:
        """
        Saves job information to a TOML-formatted file.

        This method registers the job information in a file, inside ~/.KVFinder-web directory, that will be used later to retrieve jobs from KVFinder-web service.

        Parameters
        ----------
        id: int
            Job ID
        """
        # Create job directory in ~/.KVFinder-web/
        job_dn = os.path.join(os.path.expanduser("~"), ".KVFinder-web", str(id))
        try:
            os.mkdir(job_dn)
        except FileExistsError:
            pass

        # Create job file inside ~/.KVFinder-web/id
        job_fn = os.path.join(job_dn, "job.toml")
        with open(job_fn, "w") as f:
            f.write("# TOML configuration file for KVFinder-web job\n\n")
            f.write('title = "KVFinder-web job file"\n\n')
            f.write(f'status = "{self.status}"\n\n')
            if self.id_added_manually:
                f.write(f"id_added_manually = true\n\n")
            f.write(f"[files]\n")
            if self.pdb is not None:
                f.write(f'pdb = "{self.pdb}"\n')
            if self.ligand is not None:
                f.write(f'ligand = "{self.ligand}"\n')
            f.write(f'output = "{self.output_directory}"\n')
            f.write(f'base_name = "{self.base_name}"\n')
            f.write("\n")
            toml.dump(o=self.input["settings"], f=f)
            f.write("\n")

    @classmethod
    def load(cls, fn: Optional[str]) -> Job:
        """
        Creates a Job object with job information from a TOML-formatted file.

        This method reads the job information from a file, inside ~/.KVFinder-web directory, that will communicate with KVFinder-web service.

        Parameters
        ----------
        fn: str
            Path to a TOML-formatted file containing job information

        Returns
        -------
        Job: Job
            A Job object with attributes loaded from a file containing job information
        """
        # Read job file
        with open(fn, "r") as f:
            job_info = toml.load(f=f)

        # Fix pdb and ligand in job_info
        if "pdb" in job_info["files"].keys():
            job_info["files"]["pdb"] = os.path.basename(
                job_info["files"]["pdb"]
            ).replace(".pdb", "")
        if "ligand" in job_info["files"].keys():
            job_info["files"]["ligand"] = os.path.basename(
                job_info["files"]["ligand"]
            ).replace(".pdb", "")

        # Treat manually added id
        if "id_added_manually" in job_info.keys():
            if job_info["id_added_manually"]:
                job_info["modes"] = None
                job_info["step_size"] = None
                job_info["probes"] = None
                job_info["cutoffs"] = None
                job_info["visiblebox"] = None
                job_info["internalbox"] = None

        return cls(job_info)

    def export(self) -> None:
        """
        Exports job results to files.

        This method exports cavities, results and log files received from KVFinder-web service together with detection parameters, registered in the TOML-formatted file inside ~/.KVFinder-web directory.
        """
        # Prepare base file
        base_dir = os.path.join(self.output_directory, self.id)

        try:
            os.mkdir(base_dir)
        except FileExistsError:
            pass

        # Export cavity
        cavity_fn = os.path.join(base_dir, f"{self.base_name}.KVFinder.output.pdb")
        with open(cavity_fn, "w") as f:
            f.write(self.cavity)

        # Export report
        report_fn = os.path.join(base_dir, f"{self.base_name}.KVFinder.results.toml")
        report = toml.loads(self.report)
        report["FILES_PATH"]["INPUT"] = self.pdb
        report["FILES_PATH"]["LIGAND"] = self.ligand
        report["FILES_PATH"]["OUTPUT"] = cavity_fn
        with open(report_fn, "w") as f:
            f.write("# TOML results file for parKVFinder software\n\n")
            toml.dump(o=report, f=f)

        # Export log
        log_fn = os.path.join(base_dir, "KVFinder.log")
        with open(log_fn, "w") as f:
            for line in self.log.split("\n"):
                if "Running parKVFinder for: " in line:
                    line = f"Running parKVFinder for job ID: {self.id}"
                    f.write(f"{line}\n")
                elif "Dictionary: " in line:
                    pass
                else:
                    f.write(f"{line}\n")

        # Export parameters
        if not self.id_added_manually:
            parameter_fn = os.path.join(
                self.output_directory, self.id, f"{self.base_name}_parameters.toml"
            )
            with open(parameter_fn, "w") as f:
                f.write("# TOML configuration file for KVFinder-web job.\n\n")
                f.write('title = "KVFinder-web parameters file"\n\n')
                f.write(f"[files]\n")
                f.write("# The path of the input PDB file.\n")
                f.write(f'pdb = "{self.pdb}"\n')
                f.write("# The path for the ligand's PDB file.\n")
                if self.ligand is not None:
                    f.write(f'ligand = "{self.ligand}"\n')
                else:
                    f.write(f'ligand = "-"\n')
                f.write("\n")
                f.write(f"[settings]\n")
                f.write(f"# Settings for cavity detection.\n\n")
                settings = {"settings": self.input["settings"]}
                toml.dump(o=settings, f=f)
                f.write("\n")


class Worker(QtCore.QThread):
    """
    Worker thread

    This class handles jobs submitted to the KVFinder-web service, including jobs status and download of completed jobs.
    """

    # Signals
    id_signal = QtCore.pyqtSignal(str)
    server_down = QtCore.pyqtSignal()
    server_up = QtCore.pyqtSignal()
    server_status_signal = QtCore.pyqtSignal(bool)
    available_jobs_signal = QtCore.pyqtSignal(list)

    def __init__(self, server, server_status):
        super().__init__()
        """
        This method constructs our worker thread.

        Parameters
        ----------
        server: str
            KVFinder-web service address and path (Default: http://kvfinder-web.cnpem.br/api). Users may set this variable to a locally configured KVFinder-web service by changing 'server' global variable
        server_status: str
            Whether the KVFinder-web service defined by global variable 'server' is Online or Offline
        """
        self.server = server
        self.wait = False
        self.server_status = server_status

    def run(self) -> None:
        """
        Starts worker thread.

        The worker thread is initialized when the GUI thread is started.

        This method gets all registered jobs, inside ./KVFinder-web directory, and check their statuses in the KVFinder-web.

        If the job is completed, the job is automatically downloaded from the KVFinder-web service and registered as 'completed' in its respective TOML-formatted file, inside ~/.KVFinder-web directory.

        If the job is expired in the KVFinder-web service, i. e., it is no longer available, its respective TOML-formatted file is erased and a pop up message will be displayed for the user.

        If the GUI thread is terminated, the worker thread will also be terminated after completing check the jobs. If the PyMOL thread is terminated, the worker thread is terminated immediateately.

        If, for some reason, the KVFinder-web service is unreachable, the worker thread will communicate the GUI thread, that will change the value of the "Server Status" field to Offline. Otherwise, the "Server Status" field will be set to Online.
        """
        from PyQt6 import QtCore

        # Times completed jobs with results are not checked in KVFinder-web service
        counter = 0

        while True:
            # Loop to wait QMessageBox signal from GUI thread that delete jobs that are no long available in KVFinder-web service
            while self.wait:
                # Wait timer to check wait status
                loop = QtCore.QEventLoop()
                QtCore.QTimer.singleShot(time_wait_status, loop.quit)
                loop.exec()

            # Constantly getting available jobs
            jobs = _get_jobs()
            self.available_jobs_signal.emit(jobs)

            # Message to user
            if verbosity in [2, 3]:
                print(f"\n[==> Currently available jobs are: {jobs}")

            # Jobs available to check status and server up
            if jobs and self.server_status:
                # Flag to indicate that there is at least one job completed with downloaded results in this loop
                flag = False

                # Check all job ids
                for job_id in jobs:
                    # Message to user
                    if verbosity in [2, 3]:
                        print(f"> Checking Job ID: {job_id}")

                    # Get job information
                    job_fn = os.path.join(
                        os.path.expanduser("~"), ".KVFinder-web", job_id, "job.toml"
                    )
                    self.job_info = Job.load(fn=job_fn)
                    self.job_info.id = job_id

                    # Save current status
                    status = self.job_info.status

                    # Handle job status
                    if status == "queued" or status == "running":
                        # Get request for job results
                        self._get_results(job_id)

                    elif status == "completed":
                        # Check if results files exist
                        output_exists = self._check_output_exists()

                        if not output_exists:
                            self._get_results(job_id)
                        else:
                            # If completed jobs with results reaches times_job_completed_no_checked counter (10), try to get job results
                            if counter == times_job_completed_no_checked:
                                self._get_results(job_id)
                                counter = 0

                            # Indicate that there is at least one job completed with downloaded
                            flag = True

                    # Wait timer to check next available job
                    if len(jobs) > 1:
                        loop = QtCore.QEventLoop()
                        QtCore.QTimer.singleShot(time_between_jobs, loop.quit)
                        loop.exec()

                # If at least one job completed with downloaded results, increment counter
                if flag:
                    counter += 1
                    flag = False

                # Wait timer to restart available job checks
                loop = QtCore.QEventLoop()
                QtCore.QTimer.singleShot(time_restart_job_checks, loop.quit)
                loop.exec()

            # No jobs available to check status
            else:
                # Message to user
                if verbosity in [2, 3]:
                    print("> Checking KVFinder-web service status ...")

                # Check service status
                status = _check_server_status(self.server)
                while not status:
                    if verbosity in [2, 3]:
                        print(
                            "\n\033[93mWarning:\033[0m KVFinder-web service is Offline!\n"
                        )
                    # Send signal that service is down
                    self.server_status_signal.emit(status)

                    # Wait timer to repeat service status check
                    loop = QtCore.QEventLoop()
                    QtCore.QTimer.singleShot(time_server_down, loop.quit)
                    loop.exec()

                    # Message to user
                    if verbosity in [2, 3]:
                        print("> Checking KVFinder-web service status ...")

                # Update server_status value
                self.server_status = status
                # Send signal that service is up
                self.server_status_signal.emit(self.server_status)

                # Wait timer when no jobs are being checked
                loop = QtCore.QEventLoop()
                QtCore.QTimer.singleShot(time_no_jobs, loop.quit)
                loop.exec()

            if dialog is None:
                self.terminate()

    def _get_results(self, job_id) -> None:
        """
        Submit a GET method to the KVFinder-web service for a Job ID.

        Parameters
        ----------
        job_id: str
            Job ID
        """
        from PyQt6 import QtNetwork
        from PyQt6.QtCore import QUrl

        try:
            self.network_manager = QtNetwork.QNetworkAccessManager()

            # Prepare request
            url = QUrl(f"{self.server}/{job_id}")
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
        Handles the GET method response.

        This methods evaluates the response and process accordingly.

        If there is no error, the job status is checked and the TOML-formatted file with job information updated. If the job is 'completed', the results are automatically downloaded and processed.

        If there is a Content error, the job is erased from ~/.KVFinder-web directory, because it is no longer available on the KVFinder-web service.

        If there is a Connection error, the worker thread will communicate the GUI thread, that will change the value of the "Server Status" field to Offline.
        """
        from PyQt6 import QtNetwork

        # Get QNetwork error status
        error = self.reply.error()

        if error == QtNetwork.QNetworkReply.NetworkError.NoError:
            # Read data retrived from service
            reply = json.loads(str(self.reply.readAll(), "utf-8"))

            # Pass outputs to Job class
            self.job_info.output = reply
            self.job_info.status = reply["status"]
            self.job_info.save(self.job_info.id)

            # Export results
            if self.job_info.status == "completed":
                try:
                    self.job_info.export()
                except Exception as e:
                    print("Error occurred: ", e)

            # Send Server Up Signal to GUI Thread
            self.server_up.emit()

        elif error == QtNetwork.QNetworkReply.NetworkError.ContentNotFoundError:
            # Send Server Up Signal to GUI Thread
            self.server_up.emit()

            # Send Job Id to GUI Thread
            self.wait = True
            self.id_signal.emit(self.job_info.id)

            # Remove job id from .KVFinder-web
            job_dn = os.path.join(
                os.path.expanduser("~"), ".KVFinder-web", self.job_info.id
            )
            try:
                self.erase_job_dir(job_dn)
                self.available_jobs_signal.emit(_get_jobs())
            except Exception as e:
                print("Error occurred: ", e)

        elif error == QtNetwork.QNetworkReply.NetworkError.ConnectionRefusedError:
            # Message to user
            if verbosity in [2, 3]:
                print("\n\033[93mWarning:\033[0m KVFinder-web service is Offline!\n")

            # Send Server Down Signal to GUI Thread
            self.server_down.emit()

    def _check_output_exists(self) -> bool:
        """
        Checks if the output of a Job already exists.

        Returns
        -------
        exist: bool
            Whether any of the output files exist
        """
        # Prepare base file
        base_dir = os.path.join(self.job_info.output_directory, self.job_info.id)

        # Get output files paths
        log = os.path.join(base_dir, "KVFinder.log")
        report = os.path.join(
            base_dir, f"{self.job_info.base_name}.KVFinder.results.toml"
        )
        cavity = os.path.join(
            base_dir, f"{self.job_info.base_name}.KVFinder.output.pdb"
        )
        if not self.job_info.id_added_manually:
            parameters = os.path.join(
                base_dir, f"{self.job_info.base_name}_parameters.toml"
            )
        else:
            parameters = True

        # Check if files exist
        log_exist = os.path.exists(log)
        report_exist = os.path.exists(report)
        cavity_exist = os.path.exists(cavity)
        try:
            parameters_exist = os.path.exists(parameters)
        except Exception:
            parameters_exist = True

        exist = log_exist and report_exist and cavity_exist and parameters_exist

        return exist

    @QtCore.pyqtSlot(bool)
    def wait_status(self, status) -> None:
        """
        PyQt Slot that change the wait attribute to True or False.

        This slot defines if the worker thread should wait for user interaction.

        Parameters
        ----------
        status: bool
            Whether is to wait for user interaction
        """
        self.wait = status

    @staticmethod
    def erase_job_dir(d) -> None:
        """
        Erases a job directory and its subdirectories.

        Parameters
        ----------
        d: str
            Path to a job directory to be erased
        """
        for f in os.listdir(d):
            f = os.path.join(d, f)
            if os.path.isdir(f):
                Worker.erase_job_dir(f)
            else:
                os.remove(f)
        os.rmdir(d)


class Form(QtWidgets.QDialog):
    """
    Class that defines a custom QDialog to Add a Job ID to currently registered jobs.
    """

    def __init__(self, server, output_dir):
        super(Form, self).__init__()
        """
        Construct a Form GUI and save server address to attribute

        Parameters
        ----------
        server: str
            KVFinder-web service address and path (Default: http://kvfinder-web.cnpem.br/api). Users may set this variable to a locally configured KVFinder-web service by changing 'server' global variable
        output_dir: str
            Path to output directory
        """
        # Initialize Form
        self.initialize_gui(output_dir)

        # Define server
        self.server = server

    def initialize_gui(self, output_dir) -> None:
        """
        Defines Form GUI with Qt interface and hook up button callbacks.

        Parameters
        ----------
        output_dir: str
            Path to output directory
        """
        from PyQt6 import QtCore, QtWidgets

        # Set Window Title
        self.setWindowTitle("Job ID Form")

        # Set alignment of QDialog
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        # self.resize(800, 220)
        self.setFixedHeight(220)

        # Create header label
        self.header = QtWidgets.QLabel(self)
        self.header.setText("Fill the fields and click on 'Add' button:")
        self.header.setAlignment(QtCore.Qt.AlignCenter)

        # Create Job ID layout
        self.hframe1 = QtWidgets.QHBoxLayout()
        self.job_id_label = QtWidgets.QLabel(self)
        self.job_id_label.setText("Job ID:")
        self.job_id = QtWidgets.QLineEdit(self)
        self.hframe1.addWidget(self.job_id_label)
        self.hframe1.addWidget(self.job_id)

        # Create Output Base Name layout
        self.hframe2 = QtWidgets.QHBoxLayout()
        self.base_name_label = QtWidgets.QLabel(self)
        self.base_name_label.setText("Output Base Name:")
        self.base_name = QtWidgets.QLineEdit(self)
        self.base_name.setText("output")
        self.base_name.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.hspacer = QtWidgets.QSpacerItem(
            40,
            20,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.hframe2.addWidget(self.base_name_label)
        self.hframe2.addWidget(self.base_name)
        self.hframe2.addItem(self.hspacer)

        # Create Output Directory layout
        self.hframe3 = QtWidgets.QHBoxLayout()
        self.output_dir_label = QtWidgets.QLabel(self)
        self.output_dir_label.setText("Output Directory:")
        self.output_dir = QtWidgets.QLineEdit(self)
        self.output_dir.setReadOnly(True)
        self.output_dir.setText(output_dir)
        self.button_browse_output_dir = QtWidgets.QPushButton(self)
        self.button_browse_output_dir.setText("Browse ...")
        self.hframe3.addWidget(self.output_dir_label)
        self.hframe3.addWidget(self.output_dir)
        self.hframe3.addWidget(self.button_browse_output_dir)

        # Create Input file layout
        self.hframe4 = QtWidgets.QHBoxLayout()
        self.input_file_label = QtWidgets.QLabel(self)
        self.input_file_label.setText("Input File (optional):")
        self.input_file = QtWidgets.QLineEdit(self)
        self.input_file.setReadOnly(True)
        self.button_browse_input_file = QtWidgets.QPushButton(self)
        self.button_browse_input_file.setText("Browse ...")
        self.hframe4.addWidget(self.input_file_label)
        self.hframe4.addWidget(self.input_file)
        self.hframe4.addWidget(self.button_browse_input_file)

        # Create Ligand file layout
        self.hframe5 = QtWidgets.QHBoxLayout()
        self.ligand_file_label = QtWidgets.QLabel(self)
        self.ligand_file_label.setText("Ligand File (optional):")
        self.ligand_file = QtWidgets.QLineEdit(self)
        self.ligand_file.setReadOnly(True)
        self.button_browse_ligand_file = QtWidgets.QPushButton(self)
        self.button_browse_ligand_file.setText("Browse ...")
        self.hframe5.addWidget(self.ligand_file_label)
        self.hframe5.addWidget(self.ligand_file)
        self.hframe5.addWidget(self.button_browse_ligand_file)

        # Create Vertical Spacer
        self.vspacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        # Create Dialog Button Box
        self.buttons = QtWidgets.QDialogButtonBox(self)
        ok = QtWidgets.QPushButton("&Add")
        ok.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogOkButton)
        )
        self.buttons.addButton(
            ok, QtWidgets.QDialogButtonBox.StandardButton.Apply
        )  # old: AcceptRole
        self.buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.buttons.setCenterButtons(True)

        # Add Widgets to layout
        self.verticalLayout.addWidget(self.header)
        self.verticalLayout.addLayout(self.hframe1)
        self.verticalLayout.addLayout(self.hframe2)
        self.verticalLayout.addLayout(self.hframe3)
        self.verticalLayout.addLayout(self.hframe4)
        self.verticalLayout.addLayout(self.hframe5)
        self.verticalLayout.addItem(self.vspacer)
        self.verticalLayout.addWidget(self.buttons)

        # Buttons Callback

        # hook up QDialog buttons callbacks
        self.button_browse_output_dir.clicked.connect(self.select_directory)
        self.button_browse_input_file.clicked.connect(
            lambda: self.select_file(self.input_file, "Choose Input PDB File")
        )
        self.button_browse_ligand_file.clicked.connect(
            lambda: self.select_file(self.ligand_file, "Choose Ligand PDB File")
        )
        self.buttons.accepted.connect(self.add_job_id)
        self.buttons.rejected.connect(self.close)

    def add_job_id(self) -> Optional[int]:
        """
        Checks information filled in the Form GUI.

        If there are missing information, return an error. Otherwise, accept data.
        """
        # Handle button click by user
        # Ok
        if (
            self.job_id.text()
            and os.path.isdir(self.output_dir.text())
            and self.base_name.text()
        ):
            return self.accept()
        # Cancel
        else:
            from PyQt6 import QtWidgets

            # Message to user
            if verbosity in [2, 3]:
                print(
                    "Fill required fields: Job ID, Output Base Name and/or Output Directory."
                )
            QtWidgets.QMessageBox.critical(
                self,
                "Job Submission",
                "Fill required fields: Job ID, Output Base Name and Output Directory.",
            )

            return None

    def get_data(self) -> Dict[str, Any]:
        """
        Retrieves data from Form GUI.

        Returns
        -------
        data: dict
            A Python dictionary containing information of the Form GUI (Job ID, base name, input file, ligand file, output directory)
        """
        # Prepara data from Form in Dict
        data = {
            "id": self.job_id.text(),
            "files": {
                "base_name": self.base_name.text(),
                "output": self.output_dir.text(),
                "pdb": self.input_file.text() if self.input_file.text() != "" else None,
                "ligand": self.ligand_file.text()
                if self.ligand_file.text() != ""
                else None,
            },
        }
        return data

    def select_directory(self) -> None:
        """
        Callback for the "Browse ..." button

        This method opens a QFileDialog to select a directory.
        """
        from PyQt6 import QtCore, QtWidgets

        fname = QtWidgets.QFileDialog.getExistingDirectory(
            caption="Choose Output Directory", directory=os.getcwd()
        )

        if fname:
            fname = QtCore.QDir.toNativeSeparators(fname)
            if os.path.isdir(fname):
                self.output_dir.setText(fname)

        return

    def select_file(self, entry: QtWidgets.QLineEdit, caption: str) -> None:
        """
        Callback for the "Browse ..." button

        This method opens a QFileDialog to select a file.
        """
        from PyQt6 import QtCore, QtWidgets

        # Get results file
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, caption=caption, directory=os.getcwd(), filter="PDB file (*.pdb)"
        )

        if fname:
            fname = QtCore.QDir.toNativeSeparators(fname)
            if os.path.exists(fname):
                entry.setText(fname)
        else:
            entry.clear()

        return


class Message(QtWidgets.QDialog):
    """
    Class that defines a custom QDialog that displays the Job ID, Job status and a notification of a Job submission.
    """

    def __init__(
        self,
        msg: str,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        notification: Optional[str] = None,
    ):
        super(Message, self).__init__()
        """
        Construct a Message GUI and fill its fields.

        Parameters
        ----------
        msg: str
            Message to be displayed on the Job Submission window
        job_id: str
            Job ID
        status: str
            Job status
        notification: str
            Notification from the KVFinder-web service
        """
        # Initialize Message GUI
        self.initialize_gui(msg, job_id, status, notification)

        # Set Values in Message GUI
        self.set_values(msg, job_id, status, notification)

    def set_values(self, msg, job_id, status, notification) -> None:
        """
        Fill the Message GUI with information from the job submitted

        Parameters
        ----------
        msg: str
            Message to be displayed on the Job Submission window
        job_id: str
            Job ID
        status: str
            Job status
        notification: str
            Notification from the KVFinder-web service
        """
        # Message
        self.msg.setText(msg)

        # Job ID
        if job_id:
            self.job_id.setText(job_id)

        # Status
        if status:
            self.status.setText(status.capitalize())
            if status == "queued" or status == "running":
                self.status.setStyleSheet("color: blue;")
            elif status == "completed":
                self.status.setStyleSheet("color: green;")

        # Notification
        if notification:
            self.notification.setText(notification)

    def initialize_gui(self, msg, job_id, status, notification) -> None:
        """
        Defines Message GUI with Qt interface and hook up button callbacks.

        Parameters
        ----------
        msg: str
            Message to be displayed on the Job Submission window
        job_id: str
            Job ID
        status: str
            Job status
        notification: str
            Notification from the KVFinder-web service
        """
        from PyQt6 import QtCore, QtGui, QtWidgets

        # Set Window Title
        self.setWindowTitle("Job Submission")

        # Set alignment of QDialog
        self.vframe = QtWidgets.QVBoxLayout(self)
        self.setFixedSize(425, 200)

        # Create message layout
        self.hframe1 = QtWidgets.QHBoxLayout(self)
        # Icon
        self.icon = QtWidgets.QLabel(self)
        pixmap = (
            self.style()
            .standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation)
            .pixmap(30, 30, QtGui.QIcon.Mode.Active, QtGui.QIcon.State.On)
        )
        self.icon.setPixmap(pixmap)
        self.icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.icon.setSizePolicy(
            QtWidgets.QSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed
            )
        )
        # Message
        self.msg = QtWidgets.QLabel(self)
        self.msg.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        # add to layout
        self.hframe1.addWidget(self.icon)
        self.hframe1.addWidget(self.msg)

        # Vertical spacer
        self.vspacer1 = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        # Create Job ID layout
        self.hframe2 = QtWidgets.QHBoxLayout(self)
        if job_id:
            # Job ID label
            self.job_id_label = QtWidgets.QLabel(self)
            self.job_id_label.setText("Job ID:")
            self.job_id_label.setSizePolicy(
                QtWidgets.QSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Fixed,
                    QtWidgets.QSizePolicy.Policy.Preferred,
                )
            )
            self.job_id_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            # Job ID entry
            self.job_id = QtWidgets.QLineEdit(self)
            self.job_id.setSizePolicy(
                QtWidgets.QSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Minimum,
                    QtWidgets.QSizePolicy.Policy.Fixed,
                )
            )
            self.job_id.setReadOnly(True)
            self.job_id.setFixedWidth(200)
            # add to layout
            self.hframe2.addWidget(self.job_id_label)
            self.hframe2.addWidget(self.job_id)
            self.hframe2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Create Status layout
        self.hframe3 = QtWidgets.QHBoxLayout(self)
        if status:
            # Job ID label
            self.status_label = QtWidgets.QLabel(self)
            self.status_label.setText("Status:")
            self.status_label.setSizePolicy(
                QtWidgets.QSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Fixed,
                    QtWidgets.QSizePolicy.Policy.Preferred,
                )
            )
            self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            # Job ID entry
            self.status = QtWidgets.QLineEdit(self)
            self.status.setSizePolicy(
                QtWidgets.QSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Minimum,
                    QtWidgets.QSizePolicy.Policy.Fixed,
                )
            )
            self.status.setReadOnly(True)
            font = QtGui.QFont()
            font.setBold(True)
            self.status.setFont(font)
            self.status.setFixedWidth(90)
            self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            # add to layout
            self.hframe3.addWidget(self.status_label)
            self.hframe3.addWidget(self.status)
            self.hframe3.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Create Notification layout
        self.hframe4 = QtWidgets.QHBoxLayout(self)
        if notification:
            # Notification entry
            self.notification = QtWidgets.QTextEdit(self)
            self.notification.setSizePolicy(
                QtWidgets.QSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Expanding,
                    QtWidgets.QSizePolicy.Policy.Expanding,
                )
            )
            self.notification.setReadOnly(True)
            self.notification.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            # add to layout
            self.hframe4.addWidget(self.notification)
            self.hframe4.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Vertical spacer
        self.vspacer2 = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        # Create Dialog Button Box
        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setCenterButtons(True)

        # Add Widgets to layout
        self.vframe.addLayout(self.hframe1)
        self.vframe.addItem(self.vspacer1)
        self.vframe.addLayout(self.hframe2)
        self.vframe.addLayout(self.hframe3)
        self.vframe.addLayout(self.hframe4)
        self.vframe.addItem(self.vspacer2)
        self.vframe.addWidget(self.buttonBox)

        # Buttons Callback

        # hook up QDialog buttons callbacks
        self.buttonBox.accepted.connect(self.accept)


def _check_server_status(server) -> bool:
    """
    Check server status before worker threads is started.

    Parameters
    ----------
    server: str
        KVFinder-web service address (Default: http://kvfinder-web.cnpem.br). Users may set this variable to a locally configured KVFinder-web service by changing 'server' global variable

    Returns
    -------
    status: bool
        Whether the server is Online or Offline
    """
    from PyQt6 import QtNetwork
    from PyQt6.QtCore import QUrl

    try:
        req = QtNetwork.QNetworkRequest(QUrl(server.replace("api", "")))
        newtork_manager = QtNetwork.QNetworkAccessManager()
        reply = newtork_manager.get(req)
        if reply.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
            return True
        else:
            return False
    except Exception:
        return False


def _get_jobs() -> list:
    """
    Gets jobs registered inside ~/.KVFinder-web directory.

    Returns
    -------
    jobs: list
        A Python list of Job IDs
    """
    # Get job dir
    d = os.path.join(os.path.expanduser("~"), ".KVFinder-web/")

    # Get jobs availables in dir
    jobs = os.listdir(d)

    return jobs


about_text = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
<html><head><meta name="qrichtext" content="1" /><style type="text/css"></style></head><body style=" font-family:'Sans Serif'; font-size:10pt; font-weight:400; font-style:normal;">
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">PyMOL KVFinder-web Tools integrates PyMOL (<a href="http://PyMOL.org/"><span style=" text-decoration: underline; color:#0000ff;">http://PyMOL.org/</span></a>) with KVFinder-web service.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">In the simplest case of running a job on KVFinder-web service:</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">1) Load a target biomolecular structure into PyMOL.</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">2) Start PyMOL KVFinder-web Tools plugin.</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">3) Select an input PDB on 'Main' tab.</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">4) Click on the 'Run KVFinder-web' button.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Jobs sent to KVFinder-web service are automatically checked by a worker thread when the plugin is activated, which downloads the results upon job completion. Further, jobs are available on the web service up to {} day{} after completion.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Job IDs are available on 'Results' tab under 'Jobs' tab, where users can check their status and input file, ligand file, output directory and parameters file locations. In addition, after the job is complete, the results can be visualiazed by clicking on 'Show' button with a job ID selected. Also, the results can be loaded directly from a results file (<span style=" font-style:italic;">.KVFinder.results.toml</span>) on the 'Results Visualization' tab. Furthermore, users can also add job IDs to PyMOL KVFinder-web Tools by clicking on 'Add ID' and providing a valid job ID to the form.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">In addition to whole structure cavity detection, there are two search space adjustments: Box and Ligand adjustments.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">The 'Box adjustment' mode creates a custom search box around a selection of interest by clicking on 'Draw Box' button, which can be adapted by changing one box parameter (minimum and maximum XYZ, padding and angles) at a time by clicking on 'Redraw Box'. For more information, there is a help button in 'Box adjustment' group.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">The 'Ligand adjustment' keeps cavity points around a target ligand PDB within a radius defined by the 'Ligand Cutoff' parameter.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">parKVFinder, KVFinder-web service and PyMOL KVFinder-web Tools were developed by:</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">- João Victor da Silva Guerra</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">- Helder Veras Filho</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">- Leandro Oliveira Bortot</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">- Rodrigo Vargas Honorato</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">- José Geraldo de Carvalho Pereira</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">- Paulo Sergio Lopes de Oliveira (paulo.oliveira@lnbio.cnpem.br)</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Brazilian Center for Research in Energy and Materials - CNPEM</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Brazilian Biosciences National Laboratory - LNBio</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Please refer and cite the parKVFinder paper if you use it in a publication.</p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-weight:600; text-decoration: underline;">Citations</span></p>
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Sans Serif';"><br /></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-family:'Sans Serif';">If you use </span><span style=" font-family:'Sans Serif'; text-decoration: underline;">KVFinder-web </span><span style=" font-family:'Sans Serif';">(</span><span style=" font-family:'Sans Serif'; text-decoration: underline;">KVFinder-web service, KVFinder-web portal or PyMOL </span><span style=" font-family:'Sans Serif'; text-decoration: underline;">KVFinder-web Tools</span><span style=" font-family:'Sans Serif';">), please cite:</span></p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-family:'Sans Serif';">&lt;paper&gt;</span></p>
<p style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">If you use <span style=" text-decoration: underline;">parKVFinder</span>, please cite:</p>
<p style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">João Victor da Silva Guerra, Helder Veras Ribeiro Filho, Leandro Oliveira Bortot, Rodrigo Vargas Honorato, José Geraldo de Carvalho Pereira, Paulo Sergio Lopes de Oliveira. ParKVFinder: A thread-level parallel approach in biomolecular cavity detection. SoftwareX (2020). <a href="https://doi.org/10.1016/j.softx.2020.100606"><span style=" text-decoration: underline; color:#0000ff;">https://doi.org/10.1016/j.softx.2020.100606</span></a>.</p>
<p style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">If you use <span style=" text-decoration: underline;">depth and hydropathy characterization</span>, please also cite:</p>
<p style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Guerra, J.V.d., Ribeiro-Filho, H.V., Jara, G.E. et al. pyKVFinder: an efficient and integrable Python package for biomolecular cavity detection and characterization in data science. BMC Bioinformatics 22, 607 (2021). <a href="https://doi.org/10.1186/s12859-021-04519-4"><span style=" text-decoration: underline; color:#0000ff;">https://doi.org/10.1186/s12859-021-04519-4</span></a>.</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">PyMOL citation may be found here:</p>
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><a href="http://pymol.sourceforge.net/faq.html#CITE"><span style=" text-decoration: underline; color:#0000ff;">https://pymol.org/2/support.html?</span></a></p></body></html>
""".format(
    days_job_expire, "s" if days_job_expire > 1 else ""
)
