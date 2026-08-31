import os
import json
import uuid
import zipfile
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

# Try to use pypdf for PDF extraction
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

class RAGService:
    """Handles incremental document parsing, local TF-IDF or ChromaDB semantic indexing, and citations."""
    
    def __init__(self, data_dir: str = "data/rag", chroma_client: Any = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.data_dir / "index_manifest.json"
        self.chroma_client = chroma_client
        self.collection = None
        self._manifest = self._load_manifest()
        
        # Simple local TF-IDF dictionary for fallback vector searches
        self.fallback_index: Dict[str, Dict[str, Any]] = {}  # chunk_id -> {text, path, tf}
        self.fallback_db_path = self.data_dir / "fallback_index.json"
        self._load_fallback_db()
        self._init_vector_db()

    def _load_manifest(self) -> Dict[str, Any]:
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"files": {}}
        
    def _save_manifest(self) -> None:
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save RAG manifest: {e}")

    def _load_fallback_db(self) -> None:
        if self.fallback_db_path.exists():
            try:
                with open(self.fallback_db_path, "r", encoding="utf-8") as f:
                    self.fallback_index = json.load(f)
            except Exception:
                pass

    def _save_fallback_db(self) -> None:
        try:
            with open(self.fallback_db_path, "w", encoding="utf-8") as f:
                json.dump(self.fallback_index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save fallback DB: {e}")

    def _init_vector_db(self) -> None:
        if self.chroma_client:
            try:
                self.collection = self.chroma_client.get_or_create_collection(
                    name="rag_documents",
                    metadata={"description": "RAG document index"}
                )
                logger.info("✓ ChromaDB collection 'rag_documents' ready for RAG")
            except Exception as e:
                logger.error(f"ChromaDB RAG collection setup failed: {e}")

    def parse_docx(self, path: Path) -> str:
        """Natively parse DOCX paragraph text from XML ZIP archive."""
        try:
            with zipfile.ZipFile(path) as docx:
                xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            paragraphs = []
            for elem in root.iter():
                if elem.tag.endswith('t'):
                    if elem.text:
                        paragraphs.append(elem.text)
            return "\n".join(paragraphs)
        except Exception as e:
            logger.error(f"Error parsing DOCX natively: {e}")
            return ""

    def parse_pptx(self, path: Path) -> str:
        """Natively parse PPTX slide text from XML ZIP archive."""
        try:
            texts = []
            with zipfile.ZipFile(path) as pptx:
                slide_files = [f for f in pptx.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')]
                for slide_file in sorted(slide_files):
                    xml_content = pptx.read(slide_file)
                    root = ET.fromstring(xml_content)
                    for elem in root.iter():
                        if elem.tag.endswith('t'):
                            if elem.text:
                                texts.append(elem.text)
            return "\n".join(texts)
        except Exception as e:
            logger.error(f"Error parsing PPTX natively: {e}")
            return ""

    def parse_pdf(self, path: Path) -> str:
        """Parse PDF using pypdf if available, otherwise skip."""
        if HAS_PYPDF:
            try:
                pages = []
                with open(path, "rb") as f:
                    reader = pypdf.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            pages.append(text)
                return "\n".join(pages)
            except Exception as e:
                logger.error(f"Error parsing PDF: {e}")
        return "[PDF parsing unavailable or skipped]"

    def extract_text(self, file_path: Path) -> str:
        """Route file to appropriate text parser based on extension."""
        ext = file_path.suffix.lower()
        if ext in (".txt", ".md", ".py", ".json", ".xml", ".html", ".css", ".js"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading text file: {e}")
                return ""
        elif ext == ".docx":
            return self.parse_docx(file_path)
        elif ext == ".pptx":
            return self.parse_pptx(file_path)
        elif ext == ".pdf":
            return self.parse_pdf(file_path)
        return ""

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping word-level chunks."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += (chunk_size - overlap)
        return chunks

    def _compute_tf(self, text: str) -> Dict[str, float]:
        """Compute simple Term Frequency mapping for local TF-IDF search fallback."""
        words = re.findall(r'\w+', text.lower())
        tf = {}
        for w in words:
            tf[w] = tf.get(w, 0.0) + 1.0
        # Normalize
        total = len(words) or 1.0
        for w in tf:
            tf[w] = tf[w] / total
        return tf

    def _delete_file_from_indices(self, file_path_str: str, chunk_ids: List[str]) -> None:
        # Delete from ChromaDB
        if self.collection and chunk_ids:
            try:
                self.collection.delete(ids=chunk_ids)
            except Exception as e:
                logger.error(f"ChromaDB delete failed: {e}")
                
        # Delete from Fallback
        for cid in list(self.fallback_index.keys()):
            if self.fallback_index[cid]["path"] == file_path_str:
                self.fallback_index.pop(cid, None)
        self._save_fallback_db()

    def index_file(self, file_path: Path) -> bool:
        """Parse, chunk, index a file incrementally, tracking metadata."""
        file_path_str = str(file_path.resolve())
        mtime = os.path.getmtime(file_path)
        
        # Check if already indexed and unchanged
        file_entry = self._manifest["files"].get(file_path_str)
        if file_entry and file_entry["last_modified"] == mtime:
            return False  # Skip unchanged
            
        logger.info(f"RAG indexing file: {file_path.name}")
        
        # If it was previously indexed, delete old chunks first
        if file_entry:
            self._delete_file_from_indices(file_path_str, file_entry["chunk_ids"])
            
        text = self.extract_text(file_path)
        if not text.strip():
            return False
            
        chunks = self.chunk_text(text)
        chunk_ids = []
        
        for idx, chunk in enumerate(chunks):
            cid = f"rag_{uuid.uuid4()}"
            chunk_ids.append(cid)
            
            # Save in Fallback DB
            self.fallback_index[cid] = {
                "text": chunk,
                "path": file_path_str,
                "tf": self._compute_tf(chunk)
            }
            
            # Save in ChromaDB
            if self.collection:
                try:
                    self.collection.add(
                        ids=[cid],
                        documents=[chunk],
                        metadatas=[{"path": file_path_str, "chunk_idx": idx}]
                    )
                except Exception as e:
                    logger.error(f"ChromaDB add failed: {e}")
                    
        # Update manifest
        self._manifest["files"][file_path_str] = {
            "last_modified": mtime,
            "chunk_ids": chunk_ids
        }
        self._save_manifest()
        self._save_fallback_db()
        return True

    def index_folder(self, folder_path: Path) -> int:
        """Recursively scan and index folder. Cleans up stale entries."""
        if not folder_path.exists() or not folder_path.is_dir():
            logger.error(f"Folder '{folder_path}' does not exist")
            return 0
            
        indexed_count = 0
        scanned_files = set()
        
        target_suffixes = {
            ".txt", ".md", ".py", ".json", ".xml", ".html", ".css", ".js", 
            ".docx", ".pptx", ".pdf"
        }
        
        for root, _, files in os.walk(folder_path):
            # Skip virtual environments and git folders specifically by segment
            parts = Path(root).parts
            if any(p in parts for p in ("venv", ".git", "__pycache__", "node_modules", "chroma_data")):
                continue
            for file in files:
                f_path = Path(root) / file
                if f_path.suffix.lower() in target_suffixes:
                    scanned_files.add(str(f_path.resolve()))
                    try:
                        if self.index_file(f_path):
                            indexed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to index {file}: {e}")
                        
        # Clean up files in manifest that are no longer on disk
        manifest_files = list(self._manifest["files"].keys())
        for f_str in manifest_files:
            # If the file belongs to this folder but wasn't scanned, it was deleted
            if f_str.startswith(str(folder_path.resolve())) and f_str not in scanned_files:
                logger.info(f"Removing deleted file from RAG index: {Path(f_str).name}")
                entry = self._manifest["files"].pop(f_str, None)
                if entry:
                    self._delete_file_from_indices(f_str, entry["chunk_ids"])
                    
        self._save_manifest()
        return indexed_count

    def crawl_user_documents(self) -> int:
        """Scan and incrementally index standard user document folders (Documents, Downloads)."""
        total_indexed = 0
        user_dirs = [
            Path(os.path.expanduser("~\\Documents")),
            Path(os.path.expanduser("~\\Downloads"))
        ]
        for d in user_dirs:
            if d.exists():
                try:
                    total_indexed += self.scan_folder(d)
                except Exception as e:
                    logger.warning("Error indexing directory {}: {}", d, e)
        return total_indexed

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Perform semantic search using ChromaDB or fallback local TF-IDF matcher."""
        logger.info(f"RAG search query: '{query}'")
        
        # 1. Try ChromaDB
        if self.collection:
            try:
                res = self.collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                results = []
                if res and res["documents"] and res["documents"][0]:
                    docs = res["documents"][0]
                    metas = res["metadatas"][0]
                    distances = res["distances"][0] if "distances" in res else [0.0] * len(docs)
                    for doc, meta, dist in zip(docs, metas, distances):
                        results.append({
                            "text": doc,
                            "path": meta.get("path"),
                            "score": round(1.0 - dist, 4)  # Simple distance-to-similarity
                        })
                    return results
            except Exception as e:
                logger.error(f"ChromaDB query failed, falling back to TF-IDF: {e}")
                
        # 2. Local TF-IDF search fallback (Cosine-like simple matcher)
        query_words = re.findall(r'\w+', query.lower())
        if not query_words:
            return []
            
        scores = []
        for cid, entry in self.fallback_index.items():
            text = entry["text"]
            path = entry["path"]
            tf = entry["tf"]
            
            # Simple match score
            score = sum(tf.get(qw, 0.0) for qw in query_words)
            if score > 0:
                scores.append((score, text, path))
                
        # Sort and return top results
        scores.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": text, "path": path, "score": round(score, 4)} 
            for score, text, path in scores[:limit]
        ]
