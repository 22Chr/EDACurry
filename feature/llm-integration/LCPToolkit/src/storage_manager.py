import json
import os
import shutil
import threading
from pathlib import Path
import chromadb
import sys


class StorageManager():

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(StorageManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        super().__init__()
        self._initialized = True

    # Build the file path
    _CURRENT_DIR = Path(__file__).resolve().parent
    _ROOT_DIR = _CURRENT_DIR.parent

    _manifest_path = f"{_ROOT_DIR}/storage/system_manifest/"
    _models_path = f"{_ROOT_DIR}/storage/models/"
    _engine_path = f"{_ROOT_DIR}/storage/engine/"
    _vector_path = f"{_ROOT_DIR}/storage/vector_db/"
    _knowledge_doc_path = f"{_ROOT_DIR}/storage/knowledge_docs/"
    _chroma_database_path = f"{_ROOT_DIR}/storage/vector_db/chroma_database/"
    _output_scripts_path = f"{_ROOT_DIR}/output_scripts/"


    # Save the system_manifest file
    def save_manifest(self, dictionary):
        try:
            os.makedirs(self._manifest_path, exist_ok = True)
            filename = f"{self._manifest_path}system_manifest.json"
            with open(filename, "w") as f:
                json.dump(dictionary, f, indent = 4, sort_keys = True)
        except FileNotFoundError:
            raise FileNotFoundError("[StorageManager] ERROR: Unable to save system manifest file")


    # Get hw_manifest
    def get_hw_manifest(self) :
        try:
            filename = f"{self._manifest_path}system_manifest.json"
            with open(filename, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None



    # Check the presence of the required component
    @staticmethod
    def is_component_present(path, filename):
        model_path = Path(path) / filename
        return model_path.is_file() or model_path.is_dir()



    # Get system's llm model path
    def get_models_path(self):
        os.makedirs(self._models_path, exist_ok = True)
        return self._models_path


    # Clean download cache files
    @staticmethod
    def clean_cache(path):
        path = Path(path)
        if path.is_dir():
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                print("ERROR: An error occurred while cleaning download cache.\n")
                sys.exit(1)
        else:
            try:
                os.remove(path)
            except FileNotFoundError:
                print("ERROR: An error occurred while cleaning download cache.\n")
                sys.exit(1)


    # Get system's inference engine path
    def get_local_inference_engine_path(self):
        os.makedirs(self._engine_path, exist_ok = True)
        return self._engine_path


    # Extract the downloaded llama.cpp engine and set the permissions
    def extract_archive(self, archive_path):
        destination = self._engine_path
        print(f"Extracting archive {archive_path} to {destination}")

        try:
            shutil.unpack_archive(archive_path, destination)
            # Remove the archive
            self.clean_cache(archive_path)
            print("Archive extracted successfully")
        except Exception:
            print(f"ERROR: An error occurred while extracting archive {archive_path} to {destination}")
            sys.exit(1)


    # Get llama.cpp path
    def get_llama_path(self):
        os.makedirs(self._engine_path, exist_ok = True)
        directories = (os.listdir(self._engine_path))
        for directory in directories:
            if "llama" in str(directory):
                return Path(self._engine_path) / directory

        return None


    # Get chroma-db local path
    def get_vector_db_local_path(self):
        os.makedirs(self._vector_path, exist_ok = True)
        return Path(self._vector_path)


    # Get local knowledge documents path used for RAG
    def get_knowledge_doc_path(self):
        os.makedirs(self._knowledge_doc_path, exist_ok = True)
        return Path(self._knowledge_doc_path)


    # Get llama-server location
    def get_llama_server_path(self):
        return Path(self.get_llama_path()/"llama-server")


    # Get chroma_databse path
    def get_chroma_database_path(self):
        os.makedirs(self._chroma_database_path, exist_ok = True)
        return Path(self._chroma_database_path)


    # Configure chroma-db persistent database
    def configure_chroma_database(self):
        # Create db directory if it doesn't already exist
        os.makedirs(self._chroma_database_path, exist_ok = True)

        # Set up the client
        client = chromadb.PersistentClient(self._chroma_database_path, settings=chromadb.Settings(anonymized_telemetry=False))

        # Define the collection
        collection = client.get_or_create_collection("edacurry_RAG")
        return collection


    # Get output scripts directory path
    def get_output_scripts_path(self):
        os.makedirs(self._output_scripts_path, exist_ok = True)
        return Path(self._output_scripts_path)
