# @author: Christian Checchetti (chris22checchetti@gmail.com)

import json
from pathlib import Path
import sys

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
    parser.add_argument("-c", "--circuit", required=True, help="Circuit netlist file. Accept only .cir files")
    parser.add_argument("-tb", "--testbench", required=True, help="Testbench for the circuit")
    parser.add_argument("-m", "--manifest", required=True, help="Json manifest file used to configure the system")
    args = parser.parse_args()

    # Check dependencies : ngspice
    print("[EDACURRY2427] Checking ngspice dependency...")
    dependency_manager = DependencyManager()
    ngspice_path = dependency_manager.get_ngspice_path()
    print("[EDACURRY2427] Found ngspice\n")


    print("[EDACURRY2427] Initializing...")
    circuit_filename = args.circuit
    manifest_data = None
    try:
        with Path(args.manifest).open('r', encoding='utf-8') as f:
            manifest_data = json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Unable to load manifest file: {e}")
    if manifest_data is None:
        raise ValueError("Unable to extract manifest data")

    # Load circuit as AST
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

    # Parsing the testbanch file with the ngspice edacurry's backend
    print("[EDACURRY2427] Preparing testbench...")
    testbench_filename = args.testbench
    testbench = None
    try:
        testbench = edacurry.parse_eldo(testbench_filename)
    except ValueError as e:
        raise ValueError(f"Unable to parse testbench file: {e}")
    if testbench is None:
        raise ValueError("Unable to parse testbench file")
    ng_testbench, tb_warnings = edacurry.write_ngspice(testbench)
    print("[EDACURRY2427] Testbench is ready\n")


    print("[EDACURRY2427] Retrieving defect simulation report...")
    campaign_director = CampaignDirector(defect_universe, ngspice_path, ng_testbench, circuit_filename)
    campaign_report = campaign_director.run_campaign()
    print("[EDACURRY2427] Report acquired\n")
    print("\n\nTesting analyses reports - Debug only")
    for report in campaign_report:
        print(report, "\n")