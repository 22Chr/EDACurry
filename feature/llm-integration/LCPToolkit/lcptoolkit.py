import importlib.util
import os
import sys
from pathlib import Path

# ANSII escape code
BLUE = "\033[94m"
RED = "\033[31m"
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


print(f"\n{BLUE}{BOLD}Welcome to LCPToolkit, the tool that makes EDACurry interaction easier{RESET}\n\n")



 # Check dependencies
dep_list = [
            "huggingface_hub",
            "psutil",
            "pydantic",
            "torch",
            "wmi",
            "amdsmi",
            "langchain_text_splitters",
            "pymupdf",
            "pymupdf4llm",
            "chromadb"
        ]

print("Checking dependencies...")

missing_dep = []
for dep in dep_list:
    if importlib.util.find_spec(dep) is None:
            missing_dep.append(dep)

if missing_dep:
    print(f"\n{RED}{BOLD}The following dependencies are not installed:{RESET}\n")

    # Create missing dependencies file
    try:
        _ROOT_DIR = Path(__file__).resolve().parent
        _missing_dependencies_path = Path(f"{_ROOT_DIR}/dependencies/")
        os.makedirs(_missing_dependencies_path, exist_ok=True)
        with open(_missing_dependencies_path / "missing_dependencies.txt", "w") as file:
            for dep in missing_dep:
                print(f"> {dep}")
                file.write(f"{dep}\n")
            file.close()

        print("\n\nThe full missing dependencies list can be found here: LCPToolkit/dependencies/missing_dependencies.txt")
        print("\n\n")
        sys.exit(78)  # POSIX code for configuration error
    except FileNotFoundError as e:
        print(f"An error has occurred while saving missing dependencies: {e}")
        sys.exit(1)

print("Done\n\n")

print("Loading dependencies...")
import threading
import time
from src import CoreSystem
from src import InferenceEngine
from src import EngineConfig
from src import StorageManager
import atexit
print("Done\n\n")


# Display the 90s style wizard spinner
def wizard_spinner_task(stop_event):
    chars = ['|', '/', '-', '\\']
    i = 0
    sys.stdout.write(f"\n{HIDE_CURSOR}{YELLOW}The wizard will now generate your response...{RESET}\n")
    while not stop_event.is_set():
        sys.stdout.write(f"{YELLOW}{BOLD}{chars[i]}{RESET}")
        sys.stdout.flush()
        sys.stdout.write('\b')
        sys.stdout.flush()
        i = (i + 1) % len(chars)
        time.sleep(0.1)
    # Clear the spinner character before finishing
    sys.stdout.write(f"{RESET} \n\n")
    sys.stdout.flush()



# Boot Core System
core = None
try:
    core = CoreSystem()
except Exception as e:
    print(f"ERROR: An error occurred while booting CoreSystem: {e}")
    sys.exit(1)

if core is None:
    print("ERROR: An error occurred while booting CoreSystem")
    sys.exit(1)


# Start the Chat server
llm_model_path = core.get_models_path().get("chat_model")
config = EngineConfig(model_path = llm_model_path, port = "8888")
mode = "chat"
inferenceEngine = InferenceEngine()

# Check the Chat server status and decide if proceed
if not inferenceEngine.start_server(mode, config):
    print("\nERROR: Unable to proceed. The Chat Server is required to run")
    sys.exit(1)

# Set a function that has to be executed every time LCPToolkit is closed (useful in case of crashes)
atexit.register(inferenceEngine.stop_all_servers)

print("\n\n")

# Start conversation
while True:
    user_input = input(
        f"{GREEN}{BOLD}Enter a prompt or 'exit' to close LCPToolkit: {RESET}"
    )
    if user_input.lower() == "exit":
        inferenceEngine.stop_server(mode, config.port)
        sys.exit(0)

    # Get embedder
    embedder = core.get_models_path().get("embedder")

    # Wizard spinner to enjoy the wait
    stop_spinner = threading.Event()
    spinner_thread = threading.Thread(target=wizard_spinner_task, args=(stop_spinner,))
    spinner_thread.start()

    try:
        # Process user request
        result = inferenceEngine.process_user_request(user_input, embedder, config.port)
    finally:
        stop_spinner.set()
        spinner_thread.join()
        sys.stdout.write(f"{SHOW_CURSOR}")


    if result is None:
        print(f"{RED}{BOLD}LCPToolkit is not able to process this request. Try to enter a more specific prompt related to EDACurry.{RESET}\n\n")
    elif result == "Internal error":
        sys.exit(1)
    else:
        print(result, "\n\n")

        # If the user asks for a Python script, automatically export the result as a .py script
        filename = ""
        if "```python" in result and not "##example##" in result:
            # Extract filename provided by the LLM model
            _filename_starting_index = result.find("##filename")
            _filename_ending_index = result.find(".py")

            if _filename_starting_index == -1 or _filename_ending_index == -1 or _filename_ending_index <= _filename_starting_index:

                print("ERROR: Unable to extract a proper filename for the generated script")

            else:

                filename = result[_filename_starting_index:(_filename_ending_index + 3)]
                filename = filename.replace("##filename: ", "")

                # Consider only the Python code
                _useless_str_index = result.find("```python")
                if _useless_str_index != -1:
                    result = result.replace(result[0:_useless_str_index], "")

                result = result.replace("```python", "")
                _filename_index_in_result = result.find("##filename: " + filename)
                result = result.replace(result[_filename_index_in_result:], "")
                result = result.replace("```", "")

                try:
                    storage_manager = StorageManager()
                    with open(storage_manager.get_output_scripts_path() / filename, "w") as file:
                        file.write(result)
                        file.close()
                        print(f"{YELLOW}{storage_manager.get_output_scripts_path() / filename} has been automatically created.{RESET}\n\n")
                except FileNotFoundError as e:
                    print(f"ERROR: An error occurred while trying to save the the response to {filename}: {e}")

