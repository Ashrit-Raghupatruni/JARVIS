"""
JARVIS AI OS — Semantic Document Memory (RAG).

Manages document parsing (PDF, DOCX, PPTX, Code, Text), chunking,
ChromaDB vector indexing, fallback TF-IDF search, and citation grounding.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.config import get_settings
from backend.services.rag_service import RAGService


class SemanticMemory:
    """
    Semantic Memory manages external and local document knowledge:
    - Document parsing, chunking, and metadata extraction.
    - ChromaDB 'rag_documents' collection vector search.
    - Local TF-IDF search fallback.
    - Citation tracking and file manifests.
    """

    def __init__(self, data_dir: Optional[Path] = None, chroma_client: Any = None):
        settings = get_settings()
        self.data_dir = data_dir or (settings.data_path / "rag")
        self.chroma_client = chroma_client
        self._rag = RAGService(data_dir=str(self.data_dir), chroma_client=chroma_client)
        logger.info("SemanticMemory initialized.")

    def set_chroma_client(self, chroma_client: Any) -> None:
        self.chroma_client = chroma_client
        self._rag.chroma_client = chroma_client
        self._rag._init_vector_db()

    def add_document(self, file_path: str) -> Dict[str, Any]:
        """Index a single document file."""
        return self._rag.add_file(file_path)

    def scan_directory(self, dir_path: str) -> Dict[str, Any]:
        """Index all documents in a directory."""
        return self._rag.scan_and_index_directory(dir_path)

    def search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Search documents using vector similarity or TF-IDF fallback."""
        return self._rag.search(query, top_k=top_k)

    def get_manifest(self) -> Dict[str, Any]:
        return self._rag._manifest

    def parse_document(self, path: Path) -> str:
        return self._rag.parse_file(path)
