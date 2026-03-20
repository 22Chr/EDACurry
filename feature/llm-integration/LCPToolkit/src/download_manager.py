import re
import sys
import requests
from huggingface_hub import hf_hub_download, snapshot_download
from pydantic.v1 import BaseModel
from .storage_manager import StorageManager


# GitHub token to access unlimited downloads
token = "" # <-- INSERT YOUR PERSONAL GITHUB TOKEN
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


class DownloadManager(BaseModel):

    _storage_manager = StorageManager()

    # Download the Qwen model from Hugging Face
    def download_llm_model(self, short_model_name, full_model_name, quantization):

        path = None

        if quantization != "FP16":
            try:
                path = hf_hub_download(
                    repo_id=f"Qwen/{short_model_name}",
                    filename=full_model_name,
                    local_dir=self._storage_manager.get_models_path()
                )
            except Exception as e:
                print(f"An error occurred while downloading the model: {e}\n")
                sys.exit(1)
        else:
            try:
                path = snapshot_download(
                    repo_id = f"Qwen/{short_model_name}",
                    allow_patterns = ["*.safetensors", "config.json", "*.model"],
                    local_dir =self._storage_manager.get_models_path()
                )
            except Exception as e:
                print(f"An error occurred while downloading the model: {e}\n")

        return path


    # Download llama.cpp
    def download_llama_cpp(self, gpu_technology, os):
        url, asset_name = self._get_latest_llama_release(gpu_technology, os)

        # download the file
        response = requests.get(url, stream = True, headers = headers)
        # Launch an error in case of bad status
        response.raise_for_status()

        engine_path = f"{self._storage_manager.get_local_inference_engine_path()}{asset_name}"
        try:
            with open(engine_path, "wb") as engine_file:
                for chunk in response.iter_content(chunk_size = 8192):
                    engine_file.write(chunk)
        except FileNotFoundError:
            print(f"ERROR: An error occurred while downloading the llama.cpp inference engine.\n")
            sys.exit(1)

        return engine_path


    # Get the latest version of llama.cpp
    @staticmethod
    def _get_latest_llama_release(gpu_technology, os):

        # Download the latest pre-compiled release of llama.cpp from GitHub
        api_url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"

        # Defining download suffix
        suffix = None
        if gpu_technology == "AppleSilicon":
            suffix = "macos-arm64"
        elif gpu_technology == "ROCm":
            if os == "win32":
                suffix = "win-vulkan-x64"
            elif os == "Darwin":
                suffix = "macos-x64"
            elif os == "linux":
                suffix = "ubuntu-rocm-x64"
        elif gpu_technology == "CUDA":
            if os == "win32":
                suffix = r"win-cuda-[\d.]+-x64"
            elif os == "linux":
                suffix = r"ubuntu-[\d.]+-cuda-x64"

        if suffix is None:
            print("ERROR: An error occurred while defining the llama.cpp version to be downloaded.\n")
            sys.exit(1)


        try:
            response = requests.get(api_url, headers = headers)
            # Launch an error in case of bad response
            response.raise_for_status()
            data = response.json()

            tag = data.get("tag_name")
            assets = data.get("assets", [])

            # Search for the asset with the defined suffix
            cuda_assets = []
            asset_name = None
            download_url = None
            for asset in assets:
                asset_name = asset.get("name")
                if gpu_technology == "CUDA":
                    if re.search(suffix, asset_name) and asset_name.startswith("llama"):
                        cuda_assets.append(asset)
                else:
                    if suffix in asset_name:
                        download_url = asset.get("browser_download_url")
                        break

            if cuda_assets:
                # Sort the assets to get the most recent version
                version_number = []
                for cuda_asset in cuda_assets:
                    cuda_asset_name = cuda_asset.get("name")
                    index = 0
                    version = ""
                    starting_index = None
                    while index < len(cuda_asset_name):
                        if starting_index is None and cuda_asset_name[index].isdigit() and cuda_asset_name[index - 1] == "-":
                            starting_index = index
                        if starting_index is not None and index >= starting_index:
                            if cuda_asset_name[index] != "-":
                                version += cuda_asset_name[index]
                            else:
                                break
                        index += 1
                    version_number.append(float(version))

                latest_version = max(version_number)
                best_asset = None
                cuda_asset_name = None
                for cuda_asset in cuda_assets:
                    cuda_asset_name = cuda_asset.get("name")
                    if str(latest_version) in cuda_asset_name:
                        if cuda_asset.get("name") == cuda_asset_name:
                            best_asset = cuda_asset
                print(f"[GitHub API] Found release {tag}: {cuda_asset_name}")
                return best_asset["browser_download_url"], cuda_asset_name
            else:
                if download_url is not None:
                    print(f"[GitHub API] Found release {tag}: {asset_name}")
                    return download_url, asset_name

            raise FileNotFoundError(f"[GitHub API] ERROR: Unable to find any asset with suffix {suffix}")
        except Exception as e:
            print(f"[GitHub API] ERROR: An error occurred while getting the latest release: {e}\n")
            sys.exit(1)



    # Download Nomic Text Embedder
    def download_nomic_text_embedder(self, embedder_name):
        repo_id = "nomic-ai/nomic-embed-text-v1.5-GGUF"
        try:
            embedder_path = hf_hub_download(
                repo_id = repo_id,
                filename = embedder_name,
                local_dir = self._storage_manager.get_models_path()
            )
        except Exception as e:
            print(f"ERROR: An error occurred while downloading Nomic Text Embedder: {e}\n")
            sys.exit(1)

        return embedder_path
