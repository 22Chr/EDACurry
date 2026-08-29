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
from src import Optimizer, Reverter, DefectEngine, Injector, DependencyManager


parser = argparse.ArgumentParser(description="IEEE 2427 compliant tool to perform fault injection")
parser.add_argument("-c", "--circuit", required=True, help="Circuit netlist file. Accept only .cir files")
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

# Loading reverter
print("[EDACURRY2427] Loading Reverter...")
reverter = Reverter(circuit)
print("[EDACURRY2427] Done\n")

# Loading injector
print("[EDACURRY2427] Starting Injector...")
injector = Injector(reverter)
print("[EDACURRY2427] Done\n")

print("[EDACURRY2427] Starting campaign...")
# TODO: Integrare CampaignDirector che istanzia n sottoprocessi sulla base del numero di core della CPU \
#  Si associa dinamicamente ad ogni processo un difetto e si esegue la simulazione sfruttando SimulatorManager (un'istanza per processo). \
#  SimulatorManager deve caricare la libreria dinamica ngspice e implementare il wrapper Python mediante ctypes delle funzioni richieste \
#  da ngspice (in modalità interattiva)
