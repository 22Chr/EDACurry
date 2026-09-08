# @author Christian Checchetti (chris22checchetti@gmail.com)
# Defines a Python wrapper for ngspice C functions and manage defect simulation

import os
import ctypes
from pathlib import Path

# ======================================================================================================================
# NGSPICE PYTHON WRAPPER (according to the ngspice manual)
# ======================================================================================================================

# SendChar receives ngspice output directed to the console
# Arguments: (char* output_line, int output_id, void* user_data)
SendCharCallback = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)

# ControlledExit is called when ngspice encounters a fatal error
# Arguments: (int exit_status, bool immediate_unloading, bool quit_requested, int exit_code, void* user_data)
ControlledExitCallback = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

class SimulatorEngine:

    _ngspice = None                                     # Shared dynamic library
    _out_log = []                                       # Output buffer to save simulation results
    _sendchar_callback = None
    _exit_callback = None

    def __init__(self, lib_path : Path | str):
        print("\n[SimulatorEngine] Simulator initialization...")
        try:
            self._ngspice = ctypes.CDLL(str(lib_path))
        except OSError as e:
            raise ImportError(f"[SimulatorEngine] Failed to load ngspice dynamic shared library: {e}")

        # ngspice C API configuration
        self._setup_c_api()

        # callback functions registration
        self._sendchar_callback = SendCharCallback(self._sendchar_handler)
        self._exit_callback = ControlledExitCallback(self._exit_handler)

        # Simulator initialization
        self._initialize()
        print("[SimulatorEngine] Simulator is ready")





    def _setup_c_api(self):
        # Define arguments type and return type for libngspice functions

        # ngSpice_Init is used to initialize ngspice
        # ngSpice_Init(SendChar*, SendStat*, ControlledExit*, SendData*, RespondToShared*, BGThreadRunning*, void*)
        self._ngspice.ngSpice_Init.argtypes = [
            SendCharCallback,                           # printf callback
            ctypes.c_void_p,                            # stat callback (null if unused)
            ControlledExitCallback,                     # exit callback
            ctypes.c_void_p,                            # data callback (null if unused)
            ctypes.c_void_p,                            # thread callback (null if unused)
            ctypes.c_void_p,                            # background running callback (null if unused)
            ctypes.c_void_p                             # user data pointer
        ]
        self._ngspice.ngSpice_Init.restype = ctypes.c_int

        # Send commands to the interactive interpreter
        # ngSpice_Command(char* command)
        self._ngspice.ngSpice_Command.argtypes = [ctypes.c_char_p]
        self._ngspice.ngSpice_Command.restype = ctypes.c_int

        # Netlist in-memory loading
        # ngSpice_Circ(char** circuit_lines)
        self._ngspice.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        self._ngspice.ngSpice_Circ.restype = ctypes.c_int


    def _initialize(self):
        # Initialize ngspice by passing callback functions
        if self._ngspice.ngSpice_Init(self._sendchar_callback, None, self._exit_callback, None, None, None, None) != 0:
            raise RuntimeError("[SimulatorEngine] Failed to initialize ngspice dynamic library")


    def _sendchar_handler(self, output_line, output_id, user_data) -> int:
        # Intercepts ngline output to stdout and saves it in the local output buffer
        if output_line:
            # Decoding C output
            line = output_line.decode("utf-8", errors="ignore")
            if line:
                self._out_log.append(line)
        return 0


    def _exit_handler(self, status, immediate, quit_req, exit_code, user_data) -> int:
        # Capture ngspice crashes and forced exits
        self._out_log.append(f"FATAL ERROR: ngspice encountered an error and exited with code {exit_code}")
        return 0


    # Orchestrate the simulation
    def simulate(self, netlist : str, testbench : str) -> str:
        # Clear output log for a new simulation
        self._out_log.clear()

        # Remove .end directive from netlist
        netlist = netlist.replace(".end\n", "\n\n* Testbench\n")

        # Merging netlist and testbench
        netlist_and_tb = netlist + testbench

        # Netlist and tb preparation as NULL terminating strings array
        raw_netlist_and_tb = netlist_and_tb.splitlines()

        # Reproducing the netlist as a list of C-like strings
        c_netlist_and_tb = [ctypes.c_char_p(line.encode("utf-8")) for line in raw_netlist_and_tb]
        c_netlist_and_tb.append(None) # NULL terminator

        # Creating a ctypes array
        ctypes_array = ctypes.c_char_p * len(c_netlist_and_tb)
        c_array = ctypes_array(*c_netlist_and_tb)

        # Loading the circuit in memory
        self._ngspice.ngSpice_Circ(c_array)

        # Run simulation
        self._ngspice.ngSpice_Command(b"run")

        # Cleaning memory to prevet leaks during the next simulation
        self._ngspice.ngSpice_Command(b"destroy all")

        # Return simulation log produced by ngspice
        return "\n".join(self._out_log)
