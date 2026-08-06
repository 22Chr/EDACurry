from pathlib import Path
from pydantic.v1 import BaseModel


class EngineConfig(BaseModel):
    model_path: Path
    port: str = "8080"
    n_gpu_layers: str = "-1" # Exec everything on GPU
    context_size: str = "16384"


class ProcessManager():
    def __init__(self, process, mode, port):
        self.process = process
        self.mode = mode
        self.port = port
