# @author: Christian Checchetti (chris22checchetti@gmail.com)
# Injector is the module responsible to perform defect injection and ngspice compatible netlist generation

from .models import DefectModel

import sys
from pathlib import Path
edacurry_exec_path = Path(__file__).resolve().parent.parent.parent.parent/"build"
sys.path.append(str(edacurry_exec_path))
import edacurry

from typing import List


class Injector:

    _ngspice_data : (str, List[str]) = None
    _circuit_path : Path | str = None

    def __init__(self, circuit_path : Path | str):
        if circuit_path is None:
            raise ValueError("[Injector] Initialization error: no circuit file has been provided\n")
        self._circuit_path = circuit_path


    def inject_defect(self, defect : DefectModel):
        defected_circuit = defect.inject(self._circuit_path)
        if defected_circuit is None:
            raise ValueError("[Injector] Unable to retrieve defected circuit\n")

        self._ngspice_data = edacurry.write_ngspice(defected_circuit)
        if self._ngspice_data is None:
            raise ValueError("[Injector] Unable to generate ngspice compatible netlist\n")

        return self._ngspice_data
