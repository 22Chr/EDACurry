# @author: Christian Checchetti (chris22checchetti@gmail.com)
# schema defines the defect record structure and the associated enumerations

from enum import Enum
from typing import List, Optional
import hashlib

import sys
from pathlib import Path
edacurry_exec_path = Path(__file__).resolve().parent.parent.parent.parent/"build"
sys.path.append(str(edacurry_exec_path))
import edacurry

from collections import defaultdict


class DefectType (Enum):
    SHORT = "short"
    OPEN = "open"
    PARAMETRIC = "parametric"


class UndetectabilityReason (Enum):
    pass

class PotentiallyUndetectabilityReason (UndetectabilityReason):
    OPEN_IN_PARALLEL = "Open in one of N in parallel"
    SHORT_IN_SERIES = "Short in one of N in series"
    REDUNDANCY = "Defect in circuit that is redundant to improve yeld"
    TEST_ACCESS = "Detection is prevented by impact of test access"
    OTHER = "Other"

    @classmethod
    def from_str(cls, value_str : str):
        try:
            return cls(value_str)
        except ValueError:
            return cls.OTHER


class StructuralUndetectabilityReason (UndetectabilityReason):
    UNUSED_OUTPUT = "Open to an unused output"
    TIE_INPUT_SHORT = "Short across a resistor that ties an input to a rail"
    REDUNDANCY = "Defect in circuit that is redundant to improve yeld"
    EQUAL_POTENTIAL_SHORT = "Short between two nodes that are logically prevented from having different voltages"
    DISALLOWED_STIMULUS = "Could only be detected by a stimulus that is not allowed"
    OTHER = "Other"

    @classmethod
    def from_str(cls, value_str: str):
        try:
            return cls(value_str)
        except ValueError:
            return cls.OTHER


class DetectionStatus(Enum):
    UNDETECTED = "undetected"
    DETECTED = "detected"
    UNKNOWN = "unknown"


class DefectRecord:

    _id: str                                                        # defect id

    _type: DefectType                                               # defect type

    _instance_name: str                                             # component full name (e.g. X1.M1)

    _node_terminals: List[str]                                      # nodes affected by the defect

    _model_name: str                                                # defect's model name (e.g. open_model,
                                                                    # MAX/MIN for parametrics)

    _multiplier: Optional[int]                                      # multiplication parameter M used when parallel
                                                                    # elements are encountered

    _weight: float                                                  # statistical weight associated to the defect

    _collapsed: Optional[int]                                       # indicates the optional total number of a collapsed
                                                                    # group of equivalent defects

    _merged: Optional[int]                                          # indicates the optional number of parallel elements
                                                                    # merged before injection

    _undetectable: bool                                             # flag to verify if a defect is potentially
                                                                    # undetectable. Default is None (pre-simulation)

    _undetectability_reason: Optional[UndetectabilityReason]        # if undetectable = True a reason of undetectability
                                                                    # must be specified


    _0_weight_justification: Optional[str]                          # the reason behind a 0 weighed element must be
                                                                    # provided

    _detected: DetectionStatus                                     # defect detection status. Default is undetected




    def __init__ (self, id, type, instance_name, node_terminals, model_name, multiplier, weight, collapsed,
                  merged, zero_weight_justification):
        try:
            self._id = id
            self._type = type
            self._instance_name = instance_name
            self._node_terminals = node_terminals
            self._model_name = model_name
            if multiplier:
                self._multiplier = multiplier
            else:
                self._multiplier = None
            self._weight = weight
            self._weight = weight
            if collapsed:
                self._collapsed = collapsed
            else:
                self._collapsed = None
            if merged:
                self._merged = merged
            else:
                self._merged = None
            self._undetectable = None
            self._undetectability_reason = None
            if weight == 0:
                if zero_weight_justification:
                    self._0_weight_justification = zero_weight_justification
                else:
                    raise Exception("the reason behind a zero-weighted defect must be provided\n")
            else:
                self._0_weight_justification = zero_weight_justification
            self._detected = DetectionStatus.UNDETECTED
        except (Exception) as e:
            print(f"[DefectRecord] Initialization error: {e}\n")



    def set_undetectable(self, undetectable):
        self._undetectable = undetectable

    def get_undetectable(self):
        return self._undetectable


    def set_undetectability_reason(self, undet_type, reason):
        if undet_type == "PUR":
            self._undetectability_reason = PotentiallyUndetectabilityReason.from_str(reason)
        elif undet_type == "SUR":
            self._undetectability_reason = StructuralUndetectabilityReason.from_str(reason)
        else:
            error_message = (f"[DefectRecord] Unable to set the specified undetectability reason {str(undet_type)} is not a valid type\n")
            raise Exception(error_message)



    def set_detection_status(self, status):
        self._detected = status

    def get_detection_status(self):
        return self._detected


    def get_info(self):
        dr_dict = {
            "_id": self._id,
            "_type": self._type,
            "_instance_name": self._instance_name,
            "_node_terminals": self._node_terminals,
            "_weight": self._weight,
            "_collapsed": self._collapsed,
            "_merged": self._undetectable,
            "_undetectable": self._undetectable,
            "_undetectability_reason": self._undetectability_reason,
            "_0_weight_justification": self._0_weight_justification,
            "detected": self._detected
        }
        return dr_dict


class Actions(Enum):
    RENAME_NODE = "rename_node"
    ADD_SUBCKT = "add_subckt"
    ADD_INSTANCE = "add_instance"
    CHANGE_PARAM = "change_param"


class Reverter:

    _oplog : List[dict] = []                # Stack used to restore the original AST after injections
    _circuit : edacurry.Circuit             # AST
    _golden_hash = None                     # Original circuit hash, used to verify the AST integrity after every revert

    # Every operation is serialized as a dict in Json style


    def __init__(self, circuit: edacurry.Circuit):
        self._circuit = circuit
        if self._circuit is None:
            raise ValueError("[Reverter] Invalid circuit\n")
        self._golden_hash = hashlib.sha256(edacurry.write_eldo(self._circuit).encode()).hexdigest()


    def push(self, operation):

        if not operation["defect_type"] in DefectType:
            error = f"[Reverter] - Unable to push operation : 'defect_type' param must be one of the following:\n"
            for dt in DefectType:
                error += f"> {dt}\n"
            raise ValueError(error)

        if not operation["action"] in Actions:
            error = f"[Reverter] - Unable to push operation : 'action' param must be one of the following:\n]"
            for action in Actions:
                error += f"> {action}\n"
            raise ValueError(error)

        if operation["details"] is None:
            raise ValueError("[Reverter] - Unable to push operation : 'details' about the performed operation must be provided\n")

        self._oplog.append(operation)


    def pop(self):

        if len(self._oplog) > 0:
            operation = self._oplog[-1]
            action = operation["action"]
            details = operation["details"]

            if operation["defect_type"] == DefectType.SHORT or operation["defect_type"] == DefectType.OPEN:
                if action == Actions.RENAME_NODE:
                    # In details we have to find subckt (if present), component, old name and new name
                    subckt_name = details["subckt"]
                    component_name = details["component"]
                    subckt = edacurry.find_subckt(self._circuit, component_name)
                    if subckt is not None:
                        component = edacurry.find_component(subckt, component_name)
                    else:
                        component = edacurry.find_component(self._circuit, component_name)
                    if component is None:
                        raise ValueError(f"[Reverter] - Unable to find component '{component_name}'. AST corrupted\n")
                    # Restore old_name
                    old_name = details["old_name"]
                    new_name = details["new_name"]
                    edacurry.rename_node(component, new_name, old_name)

                if action == Actions.ADD_SUBCKT:
                    # In details we have to find subckt_name
                    subckt_name = details["subckt"]
                    subckt = edacurry.find_subckt(self._circuit, subckt_name)
                    if subckt is None:
                        raise ValueError(f"[Reverter] - Unable to find subckt '{subckt_name}'. AST corrupted\n")
                    self._circuit.content.remove(subckt)

                if action == Actions.ADD_INSTANCE:
                    # In details we must found the subckt name (if present) and the component name
                    subckt_name = details["subckt"]
                    component_name = details["component"]
                    subckt = edacurry.find_subckt(self._circuit, subckt_name)
                    component = None
                    if subckt is not None:
                        component = edacurry.find_component(subckt, component_name)
                        if component is None:
                            raise ValueError(f"[Reverter] - Unable to find component '{component_name}. AST corrupted'\n")
                        subckt.content.remove(component)
                    else:
                        component = edacurry.find_component(self._circuit, component_name)
                        if component is None:
                            raise ValueError(f"[Reverter] - Unable to find component '{component_name}. AST corrupted'\n")
                        self._circuit.content.remove(component)

            else:
                if action == Actions.CHANGE_PARAM:
                    # in details we must found subckt (if present), component, parameter and original value
                    subckt_name = details["subckt"]
                    component_name = details["component"]
                    subckt = edacurry.find_subckt(self._circuit, subckt_name)
                    component = None
                    if subckt is not None:
                        component = edacurry.find_component(subckt, component_name)
                    else:
                        component = edacurry.find_component(self._circuit, component_name)
                    if component is None:
                        raise ValueError(f"[Reverter] - Unable to find component '{component_name}. AST corrupted\n")
                    param_name = details["parameter"]
                    parameter = edacurry.find_parameter(component, param_name)
                    original_value = details["original_value"]
                    parameter.right = original_value

            self._oplog.remove(operation)


    def revert_ast(self):
        while (len(self._oplog) > 0):
            self.pop()
        reverted_hash = hashlib.sha256(edacurry.write_eldo(self._circuit).encode()).hexdigest()
        if reverted_hash != self._golden_hash:
            raise Exception(f"[Reverter] - AST restore failed.\n> Original circuit sha256 hash: {self._golden_hash}\n> Reverted circuit sha256 hash: {reverted_hash}\n")
        else:
            print("[Reverter] - AST restored\n")


    def get_status(self):
        for operation in self._oplog:
            for value in operation:
                print(value, operation[value])
            print("\n")



class Optimizer:

    _circuit : edacurry.Circuit
    _optimised_netlist : str                # Optimised netlist : equivalent components are merged into one
    _circuit_filename : Path | str          # Initial netlist filename
    _optim_target : List[str]               # List of components that can be optimized. Defined in the manifest

    def __init__(self, circuit: edacurry.Circuit, filename : Path | str, optim_target : List[str]):
        self._circuit = circuit
        if circuit is None:
            raise ValueError("[Optimizer] - Invalid circuit\n")
        self._circuit_filename = filename
        self._optim_target = optim_target


    def get_structure(self):

        structure = []

        for cont in self._circuit.content:

            signatures = []
            components = []

            # Get components
            for component in cont.content:
                # Get component master
                comp_master = component.master
                # Get nodes
                nodes = []
                for node in component.nodes:
                    nodes.append(node.name)
                nodes = tuple(nodes)
                # Get parameters
                parameters = []
                for parameter in component.parameters:
                    parameters.append((parameter.left.name, parameter.right.value))
                parameters = tuple(parameters)

                signatures.append((comp_master, nodes, parameters))
                components.append(component)
            structure.append((cont, components, signatures))

        return structure


    def optimize_merge(self) -> edacurry.Circuit:

        print("[Optimizer - optimize_merge] Optimizing circuit...")

        if self._optim_target is None or len(self._optim_target) == 0:
            print("[Optimizer - optimize_merge] - No optimization target has been specified. Nothing to do\n")
            return

        structure = self.get_structure()
        has_been_optimized = False

        for element in structure:
            equivalent_components = {}
            element_type, components, signatures = type(element[0]), element[1], element[2]

            if "edacurry.Subckt" in str(element_type):
                # Extract subckt name
                subckt_name = element[0].name
                if subckt_name is None:
                    raise ValueError("[Optimizer - optimize_merge] - Unable to retrieve subckt name\n")
                # Check if subckt name is present among the optimizable ones specified in the manifest
                ok_to_proceed = False
                for subckt_target_name in self._optim_target:
                    if subckt_name.lower() == subckt_target_name.lower():
                        ok_to_proceed = True
                        break
                if not ok_to_proceed:
                    print(f"[Optimizer - optimize_merge] - {subckt_name} not specified in optim target. Skipped\n")
                # Find subckt
                subckt = edacurry.find_subckt(self._circuit, subckt_name)
                if subckt is None:
                    raise ValueError(f"[Optimizer - optimize_merge] - Unable to find subckt {subckt_name}\n")

                # Find equivalent components that can be merged
                i = 0
                while i < len(components):
                    # Avoid duplicates
                    if signatures[i] in equivalent_components:
                        i += 1
                        continue

                    j = 0
                    while j < len(signatures):
                        if i != j and signatures[i] == signatures[j]:
                            if signatures[i] not in equivalent_components:
                                equivalent_components[signatures[i]] = [components[i]]
                            equivalent_components[signatures[i]].append(components[j])
                        j += 1
                    i += 1

                # If no components can be merged, skip
                if len(equivalent_components) > 0:
                    print(f"[Optimizer - optimize_merge] - Optimizing {subckt_name}...")
                    for signature in equivalent_components:
                        eq_comp = len(equivalent_components[signature])
                        i = 1
                        # Remove equivalent components
                        while i < len(equivalent_components[signature]):
                            subckt.content.remove(equivalent_components[signature][i])
                            i += 1
                        # Adjust M parameter to indicates how many components are merged
                        parameters = equivalent_components[signature][0].parameters
                        # Check the presence of M parameter
                        for parameter in parameters:
                            if parameter.type == edacurry.ParameterType.param_assign:
                                # parameter.left contains the name
                                if parameter.left.name.lower() == 'm':
                                    parameter.right = edacurry.Double(eq_comp)
                    has_been_optimized = True
                    print("[Optimizer - optimize_merge] - Done.\n")
            else:
                print(f"[Optimizer - optimize_merge] - Optimizer for {element_type} is under development\n")

        if has_been_optimized:
            # Save the optimized netlist file
            optimized_dir = Path(__file__).resolve().parent.parent/"optimized netlists"
            Path(optimized_dir).mkdir(parents=True, exist_ok=True)
            optimized_filename = self._circuit_filename.split("/")[-1]
            optimized_filename = f"{optimized_dir}/optimized_{optimized_filename}"
            with open(optimized_filename, "w") as f:
                f.write(edacurry.write_eldo(self._circuit))

            print(f"[Optimizer - optimize_merge] - Circuit has been optimized and the netlist file has been saved in {optimized_dir}.\n")

        else:
            print(f"[Optimizer - optimize_merge] - Nothing to do.\n")
