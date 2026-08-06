import os
import sys
import threading
import hashlib
from time import sleep

from .storage_manager import StorageManager
from .inference_engine import InferenceEngine
from .engine_config import EngineConfig
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
import pymupdf4llm


class RagManager():
    _instance = None
    _lock = threading.Lock()
    _storage_manager = StorageManager()
    _inference_engine = InferenceEngine()
    _db = None

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RagManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, embedder_path):

        if getattr(self, "_initialized", False):
            return

        super().__init__()
        self._initialized = True

        # Configure the RAG DB
        self._db = self._storage_manager.configure_chroma_database()

        # Wait 3 seconds to be sure the DB is ready
        sleep(3)

        # Check any error
        if self._db is None:
            print("[RagManager] ERROR: An error occurred while connecting to the RAG database.\n")
            sys.exit(1)

        # Check if db is empty
        _empy_db = self._db.count() == 0

        # Get knowledge documents and verify that any raw document has been processed into Markdown in the vector_db directory
        for file in os.listdir(self._storage_manager.get_knowledge_doc_path()):

            # Filter hidden files add by the OS
            if not file.startswith(".") and not file.endswith(".ini") and not file.endswith(".db"):

                # Get file format by checking the extension
                _file_extension = file.split(".")[-1]
                # Define partial filename to check if file is already present in vector_db directory
                _filename = f"text_{file.replace(_file_extension, 'md')}"

                # Process file if it hasn't been processed before or if the db is empty
                if not self._storage_manager.is_component_present(self._storage_manager.get_vector_db_local_path(), _filename) or _empy_db:
                    # Define output filename (the name that will be used in the vector_db directory)
                    _output_filename = str(self._storage_manager.get_vector_db_local_path()) + "/text_" + file.replace(_file_extension, "md")

                    print("\nProcessing file: " + file + " into Markdown\n[This might take several minutes]\n\n")

                    _file = str(self._storage_manager.get_knowledge_doc_path()) + "/" + file
                    self._markdownify(_file, _output_filename)

                # Embed the file and save it into the database if it isn't already present
                # Check metadata
                _limit = 1  # improve performance by limiting the research to the first match found
                _results = self._db.get(
                    where = {"source": _filename},
                    limit = _limit
                )
                if len(_results['ids']) == 0:
                    # Document is not present and must be processed
                    print(f"Embedding file {_filename}\n[This might take several minutes]\n\n")

                    # File embedding
                    self._embed_document(_filename, embedder_path, self._db)




    @ staticmethod
    def _ocr_function(page, dpi = 300):
        tessdata_path = "/opt/homebrew/share/tessdata"
        return page.get_textpage_ocr(tessdata=tessdata_path, dpi=dpi)


    # Process documents as markdown using pymupdf4llm
    def _markdownify(self, filename, output_file):
        if filename.endswith(".pdf"):
            md_doc = pymupdf4llm.to_markdown(filename, use_oc = True)
        else:
            md_doc = pymupdf4llm.to_markdown(filename)

        try:
            with open(output_file, "w", encoding = "utf-8") as f:
                f.write(md_doc)
                f.close()
        except FileNotFoundError:
            print(f"[RagManager] ERROR: {output_file} not found.\n")
            sys.exit(1)




    # Document chunking
    def _embed_document(self, filename, embedder, db):
        # Define document
        document = str(self._storage_manager.get_vector_db_local_path() / filename)

        # Open the document
        print(f"Chunking document {document}")
        try:
            with open(document, "r") as md_file:
                md_text = md_file.readlines()
        except FileNotFoundError:
            print(f"[RagManager] ERROR: {document} not found.\n")
            sys.exit(1)

        # Start chunking
        # Markdown headers based splitting
        splitting_headers = [
            ("#", "Main title"),
            ("##", "Section"),
            ("###", "Subsection"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on = splitting_headers)
        semantic_chunks = markdown_splitter.split_text("".join(md_text))

        # length based splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=["\n\n", "\n", ".", " ", ""]  # Preferential cut order
        )

        final_chunks = text_splitter.split_documents(semantic_chunks)

        # Specifying filename as chunk source
        for chunk in final_chunks:
            chunk.metadata["source"] = filename


        # Embedding
        # Start embedding server
        _embedding_config = EngineConfig(model_path = embedder)
        self._inference_engine.start_server("embedding", _embedding_config)
        # Embed chunks
        prog_number = 0
        for chunk in final_chunks:
            # Define the numerical vector
            vector = self._inference_engine.embed_text(chunk, _embedding_config.port, prog_number)
            if vector is None:
                print(f"[RagManager] ERROR: no vector has been generated for chunk {prog_number}\n")
                sys.exit(1)
            # Get chunk text
            text = chunk.page_content
            # Get chunk metadata
            metadata = chunk.metadata
            # Define ID
            id = hashlib.sha256((filename + str(prog_number)).encode()).hexdigest()

            # Save the record on db
            if db is not None:
                db.add(
                    documents = [text],
                    embeddings = vector,
                    metadatas = [metadata],
                    ids = [id]
                )
                print(f"Chunk {prog_number} has been successfully saved.\n")
            else:
                print(f"[RagManager] ERROR: Un error has occurred while storing chunk {prog_number}.\n]")
                sys.exit(1)

            prog_number += 1
        self._inference_engine.stop_server("embedding", _embedding_config.port)



    # Get RAG context fitting user request
    def get_context(self, user_request, embedder):
        # Start embedding server
        config = EngineConfig(model_path = embedder)
        self._inference_engine.start_server("embedding", config)

        # Vectorize user request
        vectorized_user_request = self._inference_engine.embed_text(user_request, config.port, 0)

        # Stop embedding server
        self._inference_engine.stop_server("embedding", config.port)

        # Search a correspondence in the DB
        query_results = self._db.query(
            query_embeddings = vectorized_user_request,
            n_results = 10,  # Get the top 5 matching elements
            include = ["documents", "metadatas", "distances"]
        )

        results_doc = query_results.get("documents", [[]])[0]
        results_distances = query_results.get("distances", [[]])[0]


        # Filter the results according to a threshold based on the computed distances
        threshold = 0.8
        filtered_docs = []
        for doc, dist in zip(results_doc, results_distances):
            if dist <= threshold:
                filtered_docs.append(doc)

        # check if no documents have been found
        if not filtered_docs:
            return None

        return "".join(filtered_docs)
