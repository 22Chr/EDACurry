# @author: Christian Checchetti (chris22checchetti@gmail.com)
# Injector is the module responsible to perform defect injection and ngspice compatible netlist generation

from .utility import Reverter
from .models import DefectModel

import sys
from pathlib import Path
edacurry_exec_path = Path(__file__).resolve().parent.parent.parent.parent/"build"
sys.path.append(str(edacurry_exec_path))
import edacurry

from typing import List


class Injector:

    _reverter : Reverter
    _ngspice_data : (str, List[str]) = None

    def __init__(self, reverter : Reverter):
        self._reverter = reverter
        if self._reverter is None:
            raise ValueError("[Injector] Initialization error: no reverter has been provided\n")


    def inject_defect(self, defect : DefectModel):
        # AST restore
        self._reverter.revert_ast()

        defect.inject(self._reverter)
        defected_circuit = defect.get_defected_circuit()
        if defected_circuit is None:
            raise ValueError("[Injector] Unable to retrieve defected circuit\n")

        self._ngspice_data = edacurry.write_ngspice(defected_circuit)
        if self._ngspice_data is None:
            raise ValueError("[Injector] Unable to generate ngspice compatible netlist\n")

        return self._ngspice_data
