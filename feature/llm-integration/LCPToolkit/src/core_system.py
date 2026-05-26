import hashlib
import platform
import sys
import threading
import time
import uuid
from .hardware_manager import HardwareManager
from .storage_manager import StorageManager
from .download_manager import DownloadManager
from .rag_manager import RagManager



class CoreSystem():

    _lock = threading.Lock()
    _instance = None

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CoreSystem, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    _SECONDS_IN_30_DAYS = 30 * 24 * 60 * 60
    _hw_manager: HardwareManager = None
    _storage_manager: StorageManager = StorageManager()
    _sys_info: dict = None

    _chat_llm_model_path = None
    _embedder_path = None

    def __init__(self, **data):

        if getattr(self, "_initialized", False):
            return

        super().__init__(**data)
        self._initialized = True

        # Check if the hardware fingerprint correspond to the saved one (if the system manifest is present)
        data = self._storage_manager.get_hw_manifest()
        # If no data is available the tool will scan the system
        if data is None:
            print("Retrieving system information...")
            self._hw_manager = HardwareManager().detect_system()
            _sys_info = self._hw_manager.get_system_info()
            self._generate_system_manifest()
            print("Done\n\n")
        else:
            # Verify if the script is executed on a different machine or if the cache is expired
            if data.get("hw_fingerprint") != self._generate_hw_fingerprint() or self._is_cache_expired(data.get("timestamp")):
                self._hw_manager = HardwareManager().detect_system()
                _sys_info = self._hw_manager.get_system_info()
                self._generate_system_manifest()
            else:
                _sys_info = data

        # Check data integrity
        if _sys_info is None:
            raise ValueError("An error has occurred while retrieving system information.\n")


        print("Checking system requirements...")
        # Check minimum requirements
        _MIN_VRAM_THRESHOLD: float = 12.0
        # VRAM
        vram = _sys_info.get("total_vram")
        if vram < _MIN_VRAM_THRESHOLD:
            print(f"ERROR: System VRAM ({vram} GB) doesn't meet the minimum 12 GB requirements.\n")
            sys.exit(1)
        # processor cores
        _MIN_CPU_CORES_THRESHOLD: int = 6
        _cpu_core = _sys_info.get("processor_cores")
        if _cpu_core < _MIN_CPU_CORES_THRESHOLD:
            print(f"ERROR: CPU ({_cpu_core} core) doesn't meet the minimum 6 core requirements.\n")
            sys.exit(1)

        _cpu_arch = _sys_info.get("processor_arch")
        _model_specs_and_sys_requirements = self._get_model_specs_and_minimum_requirements(vram, _cpu_arch)
        # RAM
        if _cpu_arch != "arm64":
            _MIN_RAM_THRESHOLD_BASED_ON_COMPATIBLE_MODEL = _model_specs_and_sys_requirements[2]
            ram = _sys_info.get("available_ram")
            if ram < _MIN_RAM_THRESHOLD_BASED_ON_COMPATIBLE_MODEL:
                print(f"ERROR: System RAM ({ram} GB) doesn't meet the minimum {_MIN_RAM_THRESHOLD_BASED_ON_COMPATIBLE_MODEL} GB requirements.\n")
                sys.exit(1)

        # disk_space
        _MIN_AVAILABLE_DISK_SPACE_BASED_ON_COMPATIBLE_MODEL = _model_specs_and_sys_requirements[3]
        _available_disk_space = _sys_info.get("available_disk_space")
        if _available_disk_space < _MIN_AVAILABLE_DISK_SPACE_BASED_ON_COMPATIBLE_MODEL:
            print(f"ERROR: System available disk space ({_available_disk_space} GB) doesn't meet the minimum {_MIN_AVAILABLE_DISK_SPACE_BASED_ON_COMPATIBLE_MODEL} GB requirements.\n")
            sys.exit(1)

        print("Done\n\n")


        print("Checking required modules presence...")
        # DOWNLOAD THE MODEL (if not present yet)
        # Defining model name for the downloading URL
        _download_manager: DownloadManager = DownloadManager()
        _model = _model_specs_and_sys_requirements[0]
        _quantization = _model_specs_and_sys_requirements[1]
        if _quantization != "FP16":
            short_model_name = f"Qwen2.5-Coder-{_model}-Instruct-GGUF"
            full_model_name = f"qwen2.5-coder-{_model.lower()}-instruct-{_quantization.lower()}.gguf"
        else:
            short_model_name = f"Qwen2.5-Coder-{_model}-Instruct"
            full_model_name = f"qwen2.5-coder-{_model.lower()}-instruct-{_quantization.lower()}.safetensors"

        # Verify if model has been already downloaded
        if not self._storage_manager.is_component_present(self._storage_manager.get_models_path(), full_model_name):
            print("Downloading Qwen2.5 Coder model...")
            self._chat_llm_model_path = _download_manager.download_llm_model(short_model_name, full_model_name, _quantization)
            if self._chat_llm_model_path is None:
                raise ValueError("ERROR: An error has occurred while downloading the Qwen2.5 Coder model.\n")
            print("Model successfully downloaded\n\n")
            self._storage_manager.clean_cache(f"{self._storage_manager.get_models_path()}.cache")
        else:
            self._chat_llm_model_path = self._storage_manager.get_models_path() + full_model_name


        # DOWNLOAD THE INFERENCE ENGINE (llama.cpp)
        _llama_path = self._storage_manager.get_llama_path()
        if _llama_path is None:
            print("Downloading llama.cpp inference engine...")
            _gpu_technology = _sys_info.get("gpu_technology")
            _os = _sys_info.get("operating_system")
            # Download the model
            _engine_path = _download_manager.download_llama_cpp(_gpu_technology, _os)
            print("Inference engine successfully downloaded\n\n")
            # Extract the downloaded model
            self._storage_manager.extract_archive(_engine_path)
            llama_path = self._storage_manager.get_llama_path()


        # DOWNLOAD NOMIC EMBEDDER
        _embedder_name = "nomic-embed-text-v1.5.f16.gguf"
        if not self._storage_manager.is_component_present(self._storage_manager.get_models_path(), _embedder_name):
            print("Downloading Nomic Text Embedder...")
            self._embedder_path = _download_manager.download_nomic_text_embedder(_embedder_name)
            if self._embedder_path is None:
                raise ValueError("ERROR: An error has occurred while downloading  Nomic Text Embedder.\n")
            print("Embedder successfully downloaded\n\n")
            self._storage_manager.clean_cache(f"{self._storage_manager.get_models_path()}.cache")
        else:
            self._embedder_path = self._storage_manager.get_models_path() + _embedder_name

        print("Done\n\n")


        # CONFIGURING THE RAG
        print("Checking RAG database configuration...")
        _rag_manager: RagManager = RagManager(str(self._embedder_path))
        print("Database is ready\n\n")






    # Generate hw_fingerprint used as machine identifier to check if the tool is executed on the latest used machine
    @staticmethod
    def _generate_hw_fingerprint():
        # Generate the fingerprint from motherboard UUID, machine's name and processor model
        fingerprint = f"{platform.node()}-{platform.processor()}-{uuid.getnode()}"
        return hashlib.sha256(fingerprint.encode()).hexdigest()


    # Generate the system manifest file
    def _generate_system_manifest(self):
       if self._hw_manager is None:
           raise ValueError("[CoreSystem] ERROR: Unable to call the Hardware Manager module to retrieve system information.")

       hw_data = self._hw_manager.dict()
       hw_data['hw_fingerprint'] = self._generate_hw_fingerprint()
       hw_data['timestamp'] = int(time.time())

       # Call the storage manager module to save the manifest
       self._storage_manager.save_manifest(hw_data)


    # Check cache validity by checking the saved timestamp
    # Cache has 30 days validity
    @staticmethod
    def _is_cache_expired(saved_timestamp):
        current_timestamp = int(time.time())
        return (current_timestamp - saved_timestamp) >= CoreSystem._SECONDS_IN_30_DAYS


    # Check which model is executable by the system and the consequent system minimum requirements
    @staticmethod
    def _get_model_specs_and_minimum_requirements(vram, cpu_arch):
        required_ram = None

        # Define model specifications and system requirements according to available VRAM
        if 12.0 <= vram < 24.0:
            model = "14B"
            quantization = "Q4_K_M"
            required_disk_space = 50.0
            if cpu_arch != "arm64":
                required_ram = 4.0
        elif 24 <= vram < 48.0:
            model = "32B"
            quantization = "Q4_K_M"
            required_disk_space = 85.0
            if cpu_arch != "arm64":
                required_ram = 8.0
        elif 48 <= vram < 70:
            model = "32B"
            quantization = "Q8_K_M"
            required_disk_space = 120.0
            if cpu_arch != "arm64":
                required_ram = 12.0
        else:
            model = "32B"
            quantization = "FP16"
            required_disk_space = 200.0
            if cpu_arch != "arm64":
                required_ram = 16.0

        result = (model, quantization, required_ram, required_disk_space)
        return result



    # Get LLM models path
    def get_models_path(self):
        return {
            "chat_model": self._chat_llm_model_path,
            "embedder": self._embedder_path,
        }
