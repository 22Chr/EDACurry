# @author: Christian Checchetti (chris22checchetti@gmail.com)
# This module is responsible to drive the whole campaign. It analyses the system to find the number of CPU cores and \
# create a pool of process corresponding to that specific count.
# Every process instantiates a simulator engine and it takes a defect from the universe, performs the injection and run \
# the simulation, parallelizing the whole work

from .simulator_engine import SimulatorEngine
from .injector import Injector
from .models import DefectModel
from .utility import Reverter
import os
import sys
import signal
import atexit
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List


# Top-level worker function to avoid pickling/spawn issues with instance methods
def _execute_simulation(defect : DefectModel, ngspice_path: Path | str, testbench: str, reverter: Reverter):
    injector = Injector(reverter)
    simulator_engine = SimulatorEngine(ngspice_path)

    ngspice_netlist, warnings = injector.inject_defect(defect)
    try:
        simulation_result = simulator_engine.simulate(ngspice_netlist, testbench)

        # TODO: call the reporter to examine simulation result and return the updated defect record
        return "success"
    except Exception as e:
        # TODO: call the reporter to examine simulation result and return the updated defect record
        return "failed"


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
    _testbench : str
    _reverter : Reverter
    _cpu_count : int
    _pool : ProcessPoolExecutor

    def __init__(self, defect_universe : List[DefectModel], ngspice_path : Path | str, testbench : str, reverter : Reverter):
        print("[CampaignDirector] Initializing campaign director...")
        self._defect_universe = defect_universe
        if self._defect_universe is None:
            raise ValueError("[CampaignDirector] Initialization error: no defect universe has been provided")
        self._ngspice_path = ngspice_path
        if ngspice_path is None:
            raise ValueError("[CampaignDirector] Initialization error: no path for ngspice library has been provided")
        self._testbench = testbench
        if self._testbench is None:
            raise ValueError("[CampaignDirector] Initialization error: no testbench has been provided")
        self._reverter = reverter
        if self._reverter is None:
            raise ValueError("[CampaignDirector] Initialization error: no reverter has been provided")
        self._cpu_count = SystemScanner().get_cpu_count()
        if self._cpu_count is None:
            raise ValueError("[CampaignDirector] Initialization error: unable to initialize process pool")
        self._pool = None

    def _cleanup(self):
        # Shutdown executor and terminate all running child processes immediately
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)

    def _signal_handler(self, signum, frame):
        # Handle termination signals and force shutdown
        print(f"\n[CampaignDirector] Interrupted by signal {signum}. Terminating processes...")
        self._cleanup()
        sys.exit(1)

    def run_campaign(self):
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

        self._pool = ProcessPoolExecutor(max_workers=self._cpu_count)

        try:
            tasks = {
                self._pool.submit(
                    _execute_simulation, defect, self._ngspice_path, self._testbench, self._reverter
                ): defect
                for defect in self._defect_universe
            }

            completed_count = 0
            defect_count = len(self._defect_universe)
            for future in concurrent.futures.as_completed(tasks):
                defect = tasks[future]
                completed_count += 1

                try:
                    report.append(future.result())
                    print(f"[CampaignDirector::run_campaign] Campaign status: {completed_count}/{defect_count} processed")
                except Exception as e:
                    print(f"[CampaignDirector::run_campaign] Un error occurred @{defect.get_info()['defect_record']['id']}: {e}")

        except KeyboardInterrupt:
            print("\n[CampaignDirector::run_campaign] Execution interrupted by user.")
            self._cleanup()
            raise
        finally:
            self._cleanup()

        print("[CampaignDirector::run_campaign] Campaign completed")
        return report



# TODO: SOLVE PICKLE ISSUE RELATED TO EDACURRY.CIRCUIT OBJECTS
