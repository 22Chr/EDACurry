import base64
import sys
import threading
import time
import subprocess
import requests
from .storage_manager import StorageManager
from .engine_config import ProcessManager

class InferenceEngine():
    # Implementing the class using Singleton pattern
    _instance = None
    _lock = threading.Lock()
    _storage_manager = StorageManager()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InferenceEngine, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance


    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        super().__init__()
        self._initialized = True
        self._active_process_list = []

    # Verify if server is running
    def is_server_running(self, mode, port):
        # Multiple server can run only in different mode or, in case they have the same mode, if their port is different
        for server in self._active_process_list:
            if server.mode == mode and server.port == port:
                return server.process is not None and server.process.poll() is None

        return False


    # Stop the server
    def stop_server(self, mode, port):
        if self.is_server_running(mode, port):
            # Get server
            process = None
            selected_server = None
            for server in self._active_process_list:
                if server.mode == mode and server.port == port:
                    process = server.process
                    selected_server = server
                    break

            if process is not None:
                print(f"Shutting down {mode.capitalize()} server...")
                process.terminate()
                process.wait()
                self._active_process_list.remove(selected_server)
            print("Done\n\n")


    # Stop all running servers
    def stop_all_servers(self):
        for server in self._active_process_list:
            self.stop_server(server.mode, server.port)


    # Start the server with the specified modality and configuration
    def start_server(self, mode, config):
        llama_server_executable = self._storage_manager.get_llama_server_path()
        if mode != "embedding" and mode != "chat":
            raise ValueError(f"{mode} is not a valid server mode.\n")

        if not config:
            raise ValueError("No valid configuration has been provided.\n")

        # Check if another server with the same mode and port is already running
        if self.is_server_running(mode, config.port):
            print("Another server is already running. Operation aborted\n")
            sys.exit(1)

        print(f"Starting {mode.capitalize()} server...\n[This could take a while]\n")
        cmd = [
            llama_server_executable,
            "-m", str(config.model_path),
            "--port", str(config.port),
            "--n-gpu-layers", str(config.n_gpu_layers),
            "-c", str(config.context_size)
        ]
        if mode == "embedding":
            cmd.append("--embedding")


        # Start a new server as a background process
        process = ProcessManager(
            process = subprocess.Popen(
            args=cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
            ),
            mode = mode,
            port = config.port
        )
        self._active_process_list.append(process)

        # Check server status
        start = time.time()
        timeout = 20
        server_url = f"http://localhost:{config.port}/health"
        while time.time() - start < timeout:
            try:
                if requests.get(server_url).status_code == 200:
                    print(f"[InferenceEngine] {mode.capitalize()} server is ready\n\n")
                    return True
            except:
                pass
            time.sleep(1)
        # stop the server in case of bad response or no response
        self.stop_server(mode, config.port)
        return False


    # Text embedder
    def embed_text(self, chunk, port, prog_number):
        print(f"[InferenceEngine] Embedding chunk {prog_number}...")
        server_url = f"http://localhost:{port}/embedding"

        # Get chunk text
        if type(chunk) != str:
            text = chunk.page_content
        else:
            text = chunk

        payload = {"content": text}

        try:
            response = requests.post(
                server_url,
                json = payload,
                timeout = 120
            )

            if response.status_code == 200:
                result = response.json()[0].get("embedding")
                print("[InferenceEngine] Embedding is ready\n\n")
                return result
            else:
                return None
        except Exception as e:
            print(f"[InferenceEngine] ERROR: An error has occurred while generating the embedding vector for chunk {prog_number}: {e}")
            self.stop_server("embedding", port)
            return None


    # Chat request processing
    def process_user_request(self, user_request, embedder, port):
        from .rag_manager import RagManager

        # Get context from RAG to fulfil user request
        rag_manager = RagManager(embedder)
        context = rag_manager.get_context(user_request, embedder)

        # Early return in case there's no matching with the user request
        if context is None:
            return None

        # Define the LLM prompt to be processed
        prompt = f"""
                    <|im_start|>system
                    You are an expert technical assistant specializing in EDACurry and its APIs. 
                    Your sole task is to answer user questions using EXCLUSIVELY the information provided in the context below.

                    STRICT OPERATIONAL RULES:
                    1. If the provided context does not contain the answer, explicitly state: "I cannot find sufficient information in the technical documentation to answer this question."
                    2. Maintain a strictly technical and professional tone. 
                    3. Do not use conversational filler or introductory phrases (e.g., "Based on the text...", "Sure!"). Go straight to the point.
                    4. If providing code snippets, they must strictly adhere to the EDACurry API syntax as defined in the context.
                    5. If the user ask to write a Python code and EDACurry has a method to fulfill the required task, use it.
                    6. If and only if the user doesn't explicitly ask you to write code and you want to make an example, start the example with the notation "##example##".
                    7. Always use argparse library for parsing input file in Python code using -i and --i flags.
                    8. When you generate a python code, define an appropriate name for it and include it at the end of the response using the notation "##filename: "<|im_end|>
                    <|im_start|>user
                    RECOVERED TECHNICAL CONTEXT:
                    {context}

                    USER QUESTION:
                    {user_request}<|im_end|>
                    <|im_start|>assistant
                """

        # Call the LLM
        server_url = f"http://localhost:{port}/completion"
        payload = {
            "prompt": prompt,
            "n_predict": 32768,
            "temperature": 0.1,
            "stop": ["<|im_end|>", "<|im_start|>"],
            "stream": False,
            "repeat_penalty": 1.15
        }

        try:
            response = requests.post(
                server_url,
                json = payload,
                timeout = 300
            )

            if response.status_code == 200:
                return response.json().get("content").strip()
            else:
                return f"LLM server status code: {response.status_code}"
        except Exception as e:
            print(f"[InferenceEngine] ERROR: An error has occurred while getting response from the LLM: {e}")
            self.stop_server("chat", port)
            return "Internal error"
