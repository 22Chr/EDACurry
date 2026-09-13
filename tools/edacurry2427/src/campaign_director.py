# @author: Christian Checchetti (chris22checchetti@gmail.com)
# This module is responsible to drive the whole campaign. It analyses the system to find the number of CPU cores and \
# create a pool of process corresponding to that specific count.
# Every process instantiates a simulator engine and it takes a defect from the universe, performs the injection and run \
# the simulation, parallelizing the whole work

from .simulator_engine import SimulatorEngine
from .injector import Injector
from .models import DefectModel
import os
import sys
import signal
import atexit
import multiprocessing as mp
from pathlib import Path
from typing import List

""" TODO: Valutare l'utilizzo della libreria textual per suddividere la finestra in cpu_count riquadri.
          In questo modo ogni processo mostra ordinatamente cosa stia facendo
"""


# Top-level worker function to avoid pickling/spawn issues with instance methods
def _execute_simulation(defect : DefectModel, ngspice_path: Path | str, circuit_path : str | Path, raw_circuit_filename : Path | str, entry_point_filename : str | Path, tmp_log_dir : Path | str, timeout : float) -> List:

    # Set working directory for the wroker process
    working_path = Path(entry_point_filename).parent.resolve()
    os.chdir(working_path)

    defect_id = defect.get_info()["defect_record"]["id"]
    tmp_log_file = f"{tmp_log_dir}/{defect_id}_log.txt"

    injector = Injector(circuit_path)
    simulator_engine = SimulatorEngine(ngspice_path, tmp_log_file, timeout)

    ngspice_netlist, warnings = injector.inject_defect(defect)
    if not ngspice_netlist:
        raise Exception("[CampaignDirector::execute_simulation] Unable to generate defected ngspice compatible netlist")

    # Save the defected netlist alongside the original one to perform injection
    path_name = circuit_path
    defected_netlist = path_name.replace(raw_circuit_filename, f"@{defect_id}_{raw_circuit_filename}")
    try:
        with open (defected_netlist, "w") as file:
            print(f"[CampaignDirector::execute_simulation] Writing {defected_netlist}...")
            file.write(ngspice_netlist)
            print(f"[CampaignDirector::execute_simulation] Defected netlist has been successfully saved")
    except Exception as e:
        raise Exception(f"[CampaignDirector::execute_simulation] Unable to write defected ngspice compatible netlist: {e}")

    # Change entry point file by generating a new one (temp file) and including the defected file generated below
    entry_point_content = None
    try:
        with open(entry_point_filename, "r") as file:
            entry_point_content = file.readlines()
    except Exception as e:
        raise Exception(f"[CampaignDirector::execute_simulation] Unable to read {entry_point_filename}: {e}")
    if not entry_point_content:
        raise Exception(f"[CampaignDirector::execute_simulation] Unable to access entry point file content")

    index = 0
    while index < len(entry_point_content):
        line = "".join(entry_point_content[index].split())
        if f'.include"{raw_circuit_filename}"' in line or f'.inc"{raw_circuit_filename}"' in line:
            line = f'.include "{defected_netlist}"'
            entry_point_content[index] = line
        index += 1

    defected_entry_point_filename = entry_point_filename
    raw_ep_filename = entry_point_filename.split("/")[-1].split(".")[0]
    defected_entry_point_filename = defected_entry_point_filename.replace(raw_ep_filename, f"@{defect_id}_{raw_ep_filename}")
    try:
        with open (defected_entry_point_filename, "w") as file:
            file.writelines(entry_point_content)
    except Exception as e:
        raise Exception(f"[CampaignDirector::execute_simulation] Unable write the new entry point for the simulation: {e}")


    if warnings:
        print("[CampaignDirector::execute_simulation] Warnings from EDACurry ngspice backend:\n")
        for warning in warnings:
            print(warning)
        print("\n")

    try:
        simulation_result = simulator_engine.simulate(defected_entry_point_filename)

        # TODO: call the reporter to examine simulation result and return the updated defect record
        return ngspice_netlist + "\n" + simulation_result
    except Exception as e:
        # TODO: call the reporter to examine simulation result and return the updated defect record
        print(f"\n\nDebug: exception in simulation: {e}\n\n")
        return f"[SIMULATION ERROR] Unable to execute simulation @{defect_id}: {e}"

    """
    finally:
        # Remove temp netlist file
        try:
            print(f"[CampaignDirector::execute_simulation] Deleting {defected_netlist}...")
            os.remove(defected_netlist)
            print("[CampaignDirector::execute_simulation] Temporary defected netlist successfully removed")

            print(f"[CampaignDirector::execute_simulation] Deleting {defected_entry_point_filename}...")
            os.remove(defected_entry_point_filename)
            print("[CampaignDirector::execute_simulation] Temporary entry point file successfully removed")
        except Exception as e:
            raise Exception(f"[CampaignDirector::execute_simulation] Unable to remove {defected_netlist}: {e}")
    """

class SystemScanner:
    _cpu_count : int = None                 # CPU cores

    def __init__(self):
        self._cpu_count = os.cpu_count()
        if self._cpu_count is None:
            raise ValueError("[SystemScanner] Initialization error: unable to determine the number of CPU cores")

    def get_cpu_count(self):
        return self._cpu_count


class CampaignDirector:
    _defect_universe : List[DefectModel]
    _ngspice_path : Path | str
    _circuit_path : str | Path
    _raw_circuit_filename : Path | str
    _entry_point_filename : Path | str
    _tmp_log_dir : Path | str
    _cpu_count : int
    _pool : mp.Pool

    def __init__(self, defect_universe : List[DefectModel], ngspice_path : Path | str, circuit_path : str | Path, raw_circuit_filename : Path | str, entry_point_filename : Path | str, tmp_log_dir : Path | str):
        print("[CampaignDirector] Initializing campaign director...")
        if defect_universe is None:
            raise ValueError("[CampaignDirector] Initialization error: no defect universe has been provided")
        self._defect_universe = defect_universe
        if ngspice_path is None:
            raise ValueError("[CampaignDirector] Initialization error: no path for ngspice library has been provided")
        self._ngspice_path = ngspice_path
        if circuit_path is None:
            raise ValueError("[CampaignDirector] Initialization error: no netlist has been provided")
        self._circuit_path = circuit_path
        if raw_circuit_filename is None:
            raise ValueError("[CampaignDirector] Initialization error: no netlist filename has been provided")
        self._raw_circuit_filename = raw_circuit_filename
        if entry_point_filename is None:
            raise ValueError("[CampaignDirector] Initialization error: no entry point filename has been provided")
        self._entry_point_filename = entry_point_filename
        if tmp_log_dir is None:
            raise ValueError("[CampaignDirector] Initialization error: no log directory for divergent simulations has been provided")
        self._tmp_log_dir = tmp_log_dir
        self._cpu_count = SystemScanner().get_cpu_count()
        if self._cpu_count is None:
            raise ValueError("[CampaignDirector] Initialization error: unable to initialize process pool")
        self._pool = None


    def _clean_tmp_files(self):
        # Cleaning tmp files generated during the analysis
        # Every tmp file starts with @
        print("[CampaignDirector::clean_tmp_files] Cleaning up temporary files...")
        dut_dir = Path(self._tmp_log_dir).parent
        for content in os.scandir(dut_dir):
            if content.is_file() and content.name.startswith("@"):
                try:
                    os.remove(content)
                    print(f"[CampaignDirector::clean_tmp_files] {content.name} successfully removed")
                except Exception as e:
                    print(f"[CampaignDirector::clean_tmp_files] Unable to remove {content.name}: {e}\n")
        print("[CampaignDirector::clean_tmp_files] Temporary files have been removed\n")

    def _cleanup(self):
        # Shutdown executor and terminate all running child processes immediately
        if self._pool is not None:
            self._pool.terminate()
            self._pool.join()
        # Clean tmp files
        self._clean_tmp_files()

    def _signal_handler(self, signum, frame):
        # Handle termination signals and force shutdown
        print(f"\n[CampaignDirector] Interrupted by signal {signum}. Terminating processes...")
        self._cleanup()
        sys.exit(1)

    def run_campaign(self, timeout):
        print("[CampaignDirector::run_campaign] Running campaign...")
        report = []

        # Register cleanup and signal handlers in the main execution flow
        atexit.register(self._cleanup)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            # Avoid crashing if invoked in a sub-thread
            pass

        ctx = mp.get_context("spawn")
        self._pool = ctx.Pool(self._cpu_count)

        task_args = [
            (defect, self._ngspice_path, self._circuit_path, self._raw_circuit_filename, self._entry_point_filename, self._tmp_log_dir, timeout)
            for defect in self._defect_universe
        ]

        async_results = [
            (
                defect,
                self._pool.apply_async(
                    _execute_simulation,
                    (
                        defect,
                        self._ngspice_path,
                        self._circuit_path,
                        self._raw_circuit_filename,
                        self._entry_point_filename,
                        self._tmp_log_dir,
                        timeout
                    ),
                ),
            )
            for defect in self._defect_universe
        ]

        total_defects = len(self._defect_universe)
        completed_count = 0

        for defect, result in async_results:
            defect_id = defect.get_info()["defect_record"]["id"]
            try:
                # Wait for single simulation completion
                res = {
                    "defect_id" : defect_id,
                    "simulation_result" : result.get(timeout)
                }
                report.append(res)
            except Exception:
                tmp_log = Path(self._tmp_log_dir) / f"{defect_id}_log.txt"
                if tmp_log.exists():
                    try:
                        with open(tmp_log, "r", encoding="utf-8", errors="ignore") as f:
                            result = f.read()
                            res = {
                                "defect_id" : defect_id,
                                "simulation_result" : result
                            }
                            report.append(res)
                    except BaseException as e:
                        raise Exception(f"[CampaignDirector::run_campaign] An error occurred @{defect_id}: {e}")
                else:
                    print(f"[CampaignDirector::run_campaign] FATAL ERROR: tmp log for defect {defect_id} not found. Campaign aborted\n")
                    exit(1)
            finally:
                completed_count += 1
                print(f"[CampaignDirector::run_campaign] Campaign status: {completed_count}/{total_defects} processed")
                sys.stdout.flush()

        self._pool.terminate()
        self._pool.join()

        print("[CampaignDirector::run_campaign] Campaign completed\n")

        self._clean_tmp_files()

        return report
