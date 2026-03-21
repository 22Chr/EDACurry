## this class is used to collect the hardware information needed to grant the automatic download of the appropriate model
import json
import shutil
import subprocess
from enum import Enum
import platform
from typing import Optional
import psutil
from pydantic.v1 import BaseModel



class ComputeSystemTechnology(str, Enum):
    APPLE_SILICON = "AppleSilicon"
    CUDA = "CUDA"
    ROCM = "ROCm"
    GENERIC = "GenericGPU"


class HardwareManager(BaseModel):

    processor_arch: Optional[str] = None
    processor_cores: Optional[int] = None
    operating_system: Optional[str] = None
    total_ram: Optional[float] = None
    available_ram: Optional[float] = None
    total_vram: Optional[float] = None
    total_disk_space: Optional[float] = None
    available_disk_space: Optional[float] = None
    gpu_technology: Optional[ComputeSystemTechnology] = None

    @classmethod
    def detect_system(cls):

        print("Collecting system information...")

        # Detecting OS
        os = platform.system()
        if os is None:
            raise ValueError("Unrecognized Operating System")
        if os != "Darwin" and os.lower() != "win32" and os.lower() != "linux":
            raise ValueError(f"Unsupported Operating System detected: {os}")


        # Detecting disk information
        disk_info = shutil.disk_usage("/")
        total_disk_space = round(disk_info.total / (1024 ** 3), 2)
        available_disk_space = round(disk_info.free / (1024 ** 3), 2)
        if total_disk_space is None or available_disk_space is None:
            raise ValueError("Unable to get disk information")


        # Detecting processor architecture
        processor_arch = platform.machine()
        if processor_arch is None:
            raise ValueError("Unable to get processor information")


        # Detecting the number of processor's cores
        processor_cores = psutil.cpu_count(logical = False)
        if processor_cores is None:
            raise ValueError("Unable to get the number of processor's cores")


        # Detecting RAM
        ram = psutil.virtual_memory()
        total_ram = ram.total / (1024 ** 3)
        available_ram = round(ram.available / (1024 ** 3), 2)
        if available_ram is None or total_ram is None:
            raise ValueError("Unable to get memory information")

        # Detecting GPU technology
        # Set to GENERIC by default
        gpu_technology = ComputeSystemTechnology.GENERIC

        if os == "Darwin" and processor_arch == "arm64":
            gpu_technology = ComputeSystemTechnology.APPLE_SILICON
        else:
            # Check the presence of an NVIDIA GPU using torch
            import torch
            is_cuda = False
            try:
                cuda_gpu = torch.cuda.get_device_name()
                if cuda_gpu is not None and len(cuda_gpu) > 0:
                    is_cuda = True
            except Exception:
                pass

            if is_cuda:
                gpu_technology = ComputeSystemTechnology.CUDA

            # Check the presence of an AMD GPU
            if not is_cuda:
                is_rocm = False
                # Windows
                if os == "win32":
                    try:
                        import wmi
                        system_info = wmi.WMI()
                        gpu = system_info.Win32_VideoController()[0]
                        caption = gpu.Caption
                        if "Advanced" or "AMD" in caption:
                            is_rocm = True
                    except Exception:
                        pass
                else:
                    # Linux
                    try:
                        import amdsmi
                        amdsmi.amdsmi_init()
                        gpu = amdsmi.amdsmi_get_processor_handles()[0]
                        gpu_type = amdsmi.amdsmi_get_processor_type(gpu)
                        if gpu_type == 1:
                            is_rocm = True
                    except Exception:
                        pass

                if is_rocm:
                    gpu_technology = ComputeSystemTechnology.ROCM



        # Detecting VRAM information
        total_vram = 0.0
        #available_vram = 0.0
        #ok_available_vram_to_0 = False

        if os == "Darwin":
            if gpu_technology is ComputeSystemTechnology.APPLE_SILICON:
                total_vram = total_ram * 0.75
                # macOS automatically allocate video memory to the needed process
                # ok_available_vram_to_0 = True
            else:
                cmd = ["system_profiler", "SPDisplaysDataType", "-json"]
                output = subprocess.check_output(cmd).decode("utf-8")
                data = json.loads(output)
                gpus = data.get("SPDisplaysDataType", [])
                # TODO: allow the script to make possible to choose the GPU in case more than one is present
                gpu = gpus[0]
                total_vram = gpu.get("VRAM (Total)")
                # ok_available_vram_to_0 = True
        elif os.lower() == "win32":
            try:
                import wmi
                system_info = wmi.WMI()
                # TODO: allow the script to make possible to choose the GPU in case more than one is present
                gpu = system_info.Win32_VideoController()[0]
                total_vram = gpu.AdapterRam / (1024 ** 3)
                # ok_available_vram_to_0 = True
            except Exception as e:
                print(f"An error occured while getting GPU VRAM information: {e}")
        else:
            # Linux is considered
            if gpu_technology is ComputeSystemTechnology.CUDA:
                import torch
                device = torch.device("cuda:0")
                total_cuda_memory = torch.cuda.get_device_properties(device).total_memory
                #allocated_cuda_memory = torch.cuda.memory_allocated(device)
                #reserved_cuda_memory = torch.cuda.memory_reserved(device)
                total_vram = total_cuda_memory / (1024 ** 3)
                #available_vram = (total_cuda_memory - allocated_cuda_memory - reserved_cuda_memory) / (1024 ** 3)
            elif gpu_technology is ComputeSystemTechnology.ROCM:
                try:
                    import amdsmi
                    amdsmi.amdsmi_init()
                    # Get the first GPU
                    gpu = amdsmi.amdismi_get_processor_handles()[0]
                    # Get total and used memory in MB
                    total_memory = amdsmi.amdsmi_get_gpu_vram_usage(gpu)
                    total_vram = total_memory / 1024
                    # available_vram = (total_memory - used_memory) / 1024
                except Exception as e:
                    print(f"An error occured while getting GPU VRAM information: {e}")


        if total_vram == 0.0:
            raise ValueError("Unable to get GPU VRAM information")



        instance = cls(
            processor_arch = processor_arch,
            processor_cores = processor_cores,
            total_disk_space = total_disk_space,
            available_disk_space = available_disk_space,
            gpu_technology = gpu_technology,
            total_ram = total_ram,
            available_ram = available_ram,
            total_vram = total_vram,
            operating_system = os
        )

        print("Information collected\n\n")

        return instance


    # Get system information as dictionary
    def get_system_info(self):
        return self.dict()
