import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src import DefectModel, ShortModel, OpenModel, OpenGateModel, ParametricModel, DetectionStatus

current_dir = Path(__file__).resolve().parent
eldo_cir_dir = current_dir.parent.parent.parent/"sources"/"test"/"eldo"/"circ_base"

import edacurry

# OPEN MODEL
# name param can be None as OpenModel automatically initialize it as 'open_model'
open_model = OpenModel("D0", "OPAMP1.xcc01", None, None, 0.75, 0, 0, None, "net12", "out")

# Get model info
print("Open model info:\n")

om_info = open_model.get_info()
for info in om_info:
    print(info, " : ", om_info[info])
print("\n\n")


# Modify defect record data
print("Modify open model defect record detection status:\n")

om_defect_record = open_model.get_record()
om_defect_record.set_detection_status(DetectionStatus.DETECTED)
om_dr_info = om_defect_record.get_info()
for info in om_dr_info:
    print(info, " : ", om_dr_info[info])
print("\n\n")

# Subckt generation
print("Subckt info:\n")
subckt = open_model.generate_subckt()
print(subckt)
print("\n\n")

# defect injection
circuit = edacurry.parse_eldo(f"{eldo_cir_dir}/opamp.cir")
print(edacurry.write_eldo(circuit))
print("\n\n")
open_model.inject(circuit)
print(edacurry.write_eldo(circuit))
print("\n\n")


print("testing Short Model:\n")
short_model = ShortModel("D1", "OPAMP1.xcc01", None, None, 0.75, 0, 0, None, "net12", "out")
print(short_model.get_info())
print("\n\n")

#Subckt generation
print("Subckt info:\n")
subckt = short_model.generate_subckt()
print(subckt)
print("\n\n")

# Defect injection
circuit = edacurry.parse_eldo(f"{eldo_cir_dir}/opamp.cir")
print(edacurry.write_eldo(circuit))
print("\n\n")
short_model.inject(circuit)
print(edacurry.write_eldo(circuit))
print("\n\n")


# OPEN GATE MODEL
print("Testing Open Gate Model:\n")

open_gate_model = OpenGateModel("D2", "OPAMP1.mn001", None, 1, 0.75, None, None, None, "out", "net13", "vssa", "net13_open")
print(open_gate_model.get_info())
print("\n\n")

# Subckt generation
print("Subckt info:\n")
subckt = open_gate_model.generate_subckt()
print(subckt)
print("\n\n")

# Injection test
circuit = edacurry.parse_eldo(f"{eldo_cir_dir}/opamp.cir")
print(edacurry.write_eldo(circuit))
print("\n\n")
open_gate_model.inject(circuit)
print(edacurry.write_eldo(circuit))
print("\n\n")


# PARAMETRIC MODEL
print("Testing Parametric Model:\n")
parametric_model = ParametricModel("DP3", "OPAMP1.mn001", "MIN", None, 1, None, None, None, "W", 50e-6, 33e-6)
print(parametric_model.get_info())
print("\n\n")

# Injection test
print("Injection test:\n")
circuit = edacurry.parse_eldo(f"{eldo_cir_dir}/opamp.cir")
print(edacurry.write_eldo(circuit))
print("\n\n")
parametric_model.inject(circuit)
print(edacurry.write_eldo(circuit))
print("\n\n")
