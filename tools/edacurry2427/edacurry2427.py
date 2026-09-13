# @author: Christian Checchetti (chris22checchetti@gmail.com)

import json
from pathlib import Path
import sys
import os

# Get EDACurry
edacurry_build_dir = Path(__file__).parent.parent.parent.resolve()/"build"
sys.path.append(str(edacurry_build_dir))
import edacurry

# argparse
import argparse

# Import modules
from src import Optimizer, DefectEngine, DependencyManager, CampaignDirector


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="IEEE 2427 compliant tool to perform fault injection")
    parser.add_argument("-dut", "--dut", required=True, help="Name of the design under test on which to perform the analysis")
    parser.add_argument("-i", "--input", required=True, help="Entry point file for simulation")
    parser.add_argument("-m", "--manifest", required=True, help="Json manifest file used to configure the system")
    parser.add_argument("-t", "--timeout", required=True, help="Timeout limit in seconds for each simulation")
    args = parser.parse_args()

    # Check dependencies : ngspice
    print("[EDACURRY2427] Checking ngspice dependency...")
    dependency_manager = DependencyManager()
    ngspice_path = dependency_manager.get_ngspice_path()
    print("[EDACURRY2427] Found ngspice\n")


    print("[EDACURRY2427] Initializing...")
    dut = args.dut
    entry_point = args.input
    manifest_data = None
    try:
        with Path(args.manifest).open('r', encoding='utf-8') as f:
            manifest_data = json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Unable to load manifest file: {e}")
    if manifest_data is None:
        raise ValueError("Unable to extract manifest data")
    print("[EDACURRY2427] Manifest has been correctly processed\n")

    # Retrieving timeout
    timeout = None
    try:
        timeout = float(args.timeout)
    except Exception as e:
        raise Exception(f"[EDACURRY2427] Unable to parse timeout value: {e}")
    if timeout is None:
        raise ValueError("[EDACURRY2427] Unable to parse timeout value")
    print(f"[EDACURRY2427] Simulation timeout set to {timeout} seconds\n")


    # Acess DUT directory inside the worskpace dir
    print("[EDACURRY2427] Retrieving DUT data...")
    workspace_dir = Path(__file__).parent.resolve()/"workspace"
    avilable_duts = os.listdir(workspace_dir)
    dut_dir = None
    for _dut in avilable_duts:
        if _dut == dut:
            dut_dir = Path(_dut)
            break
    if not dut_dir:
        raise ValueError("Unable to find the specified DUT in the workspace")
    content_dir = workspace_dir/dut_dir

    # Add temp dir for log files produced during the analysis
    print("[EDACURRY2427] Creating temporary directory for logs produced by divergent simulations...")
    tmp_log_dir = content_dir/"tmp_logs"
    os.makedirs(tmp_log_dir, exist_ok=True)
    print("[EDACURRY2427] Logs dir created")

    content = os.listdir(content_dir)
    entry_point_filename = None
    raw_circuit_filename = f"tb_{dut}"
    found_circuit_filename = False
    found_entry_point_filename = False
    for element in content:
        if not entry_point_filename and element == entry_point:
            entry_point_filename = element
            found_entry_point_filename = True
        if element.split(".")[0] == raw_circuit_filename:
            raw_circuit_filename = element
            found_circuit_filename = True

    if not found_circuit_filename:
        raise ValueError("Unable to find the specified entry point file for circuit analysis")
    if not found_entry_point_filename:
        raise ValueError("Unable to find the specified entry point file for circuit analysis")
    print("[EDACURRY2427] Data retrieved\n")

    # Add full path to circuit filename
    circuit_filename = str(content_dir/raw_circuit_filename)
    entry_point_filename = str(content_dir/entry_point_filename)

    # Load circuit as AST
    print("[EDACURRY2427] Loading circuit...")
    circuit = None
    try:
        circuit = edacurry.parse_eldo(circuit_filename)
    except ValueError as e:
        raise ValueError(f"Unable to parse circuit file: {e}")
    if circuit is None:
        raise ValueError("Unable to parse circuit file")
    print("[EDACURRY2427] Done\n")

    # Run optimizer to merge parallel equivalent components
    print("[EDACURRY2427] Running optimizer...")
    optimizer = Optimizer(circuit, circuit_filename, manifest_data)
    optimizer.optimize_merge()
    print("[EDACURRY2427] Done\n")

    # Defect universe generation
    print("[EDACURRY2427] Initializing defect universe...")
    defect_engine = DefectEngine(circuit, circuit_filename, manifest_data)
    print("[EDACURRY2427] Done\n")
    print("[EDACURRY2427] Retrieving defect universe details...")
    defect_universe_details = defect_engine.get_universe_details()
    print("[EDACURRY2427] Done\n")
    print("[EDACURRY2427] Retrieving defect universe...")
    defect_universe = defect_engine.generate_defect_universe()
    print("[EDACURRY2427] Done\n\n")
    
    # Running simulation
    print("[EDACURRY2427] Retrieving defect simulation report...")
    campaign_director = CampaignDirector(defect_universe, ngspice_path, circuit_filename, raw_circuit_filename, entry_point_filename, tmp_log_dir)
    campaign_report = campaign_director.run_campaign(timeout)
    print("[EDACURRY2427] Report acquired\n")

    print("\n\nTesting analyses reports - Debug only")
    for report in campaign_report:
        print(report, "\n")