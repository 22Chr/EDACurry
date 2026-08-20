# Author: Christian Checchetti (chris22checchetti@gmail.com)
# schema defines the defect record structure and the associated enumerations

from enum import Enum
from typing import List, Optional


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
                    raise Exception("the reason behind a zero-weighted defect must be provided")
            else:
                self._0_weight_justification = zero_weight_justification
            self._detected = DetectionStatus.UNDETECTED
        except (Exception) as e:
            print("[DefectRecord] Initialization error: " + str(e))



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
            error_message = ("[DefectRecord] Unable to set the specified undetectability reason. "
                             + str(undet_type) + " is not a valid type")
            raise Exception(error_message)



    def set_detection_status(self, status):
        self._detected = status

    def get_detection_status(self):
        return self._detected


    def get_defect_record_info(self):
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

