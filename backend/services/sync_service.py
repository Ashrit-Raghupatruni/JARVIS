"""
Cross-Device Synchronization & Remote Presence Service for JARVIS.
Handles local UDP network discovery, peer registration, encryption, and state package syncs.
"""

import sys
import socket
import json
import time
import threading
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet

from backend.config import get_settings
from backend.utils.logger import logger


def get_local_ip() -> str:
    """Helper to determine the primary active local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually initiate a connection, just queries routing tables
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


class SyncService:
    """Discovers and synchronizes state context across local network JARVIS instances."""

    def __init__(self, app_state=None) -> None:
        self.app_state = app_state
        self.settings = get_settings()
        
        # State
        self.peers: Dict[str, Dict[str, Any]] = {}  # IP -> metadata
        self._fernet: Optional[Fernet] = None
        self._stop_event = threading.Event()
        self._broadcast_thread: Optional[threading.Thread] = None
        self._listener_thread: Optional[threading.Thread] = None
        
        self._init_encryption()

    def _init_encryption(self) -> None:
        """Initialize Symmetric Fernet Key."""
        try:
            key = self.settings.SYNC_KEY.encode("utf-8")
            self._fernet = Fernet(key)
        except Exception as e:
            logger.error("Failed to initialize sync encryption key: {}. Fernet requires 32-byte base64 key.", e)
            self._fernet = None

    def start(self) -> None:
        """Start UDP broadcast peer discovery tasks."""
        if not self.settings.SYNC_ENABLED:
            logger.info("Cross-device synchronization is disabled.")
            return

        if not self._fernet:
            logger.error("Sync is enabled but encryption key is invalid. Aborting startup.")
            return

        self._stop_event.clear()
        
        # Start UDP listener
        self._listener_thread = threading.Thread(target=self._run_listener, name="SyncListener", daemon=True)
        self._listener_thread.start()

        # Start UDP broadcaster
        self._broadcast_thread = threading.Thread(target=self._run_broadcaster, name="SyncBroadcaster", daemon=True)
        self._broadcast_thread.start()
        
        logger.info("✓ SyncService peer discovery threads started.")

    def stop(self) -> None:
        """Shutdown UDP synchronization threads."""
        self._stop_event.set()
        
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
        if self._broadcast_thread:
            self._broadcast_thread.join(timeout=1.0)
            
        logger.info("SyncService background worker stopped.")

    # ── UDP Discovery loop ──────────────────────────────────────────────────

    def _run_broadcaster(self) -> None:
        """Broadcasts presence packet to port every 10 seconds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        port = self.settings.SYNC_PORT
        
        logger.debug("Starting UDP Broadcast heartbeat on port {}", port)

        while not self._stop_event.is_set():
            try:
                local_ip = get_local_ip()
                payload = {
                    "device": self.settings.FRIENDLY_DEVICE_NAME,
                    "ip": local_ip,
                    "port": self.settings.SERVER_PORT,
                    "timestamp": time.time()
                }
                
                # Encrypt broadcast packet
                data = json.dumps(payload).encode("utf-8")
                encrypted = self._fernet.encrypt(data)
                
                # Broadcast on network
                sock.sendto(encrypted, ('<broadcast>', port))
            except Exception as e:
                logger.debug("Sync broadcast error: {}", e)
                
            # Sleep 10s or until interrupted
            self._stop_event.wait(10.0)
            
        sock.close()

    def _run_listener(self) -> None:
        """Listens for UDP broadast packets and updates active peer registry."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port = self.settings.SYNC_PORT
        
        try:
            # Bind to all interfaces
            sock.bind(('', port))
            sock.settimeout(2.0)
            logger.debug("UDP Broadcast listener bound to port {}", port)
        except Exception as e:
            logger.error("Failed to bind UDP listener to port {}: {}", port, e)
            sock.close()
            return

        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(2048)
                peer_ip = addr[0]
                
                # Filter out own broadcasts
                if peer_ip == get_local_ip():
                    continue

                # Decrypt
                decrypted = self._fernet.decrypt(data)
                payload = json.loads(decrypted.decode("utf-8"))
                
                # Update peer info
                payload["last_seen"] = time.time()
                if peer_ip not in self.peers:
                    logger.info("✓ Discovered new JARVIS peer: {} at {}:{}", payload.get("device"), peer_ip, payload.get("port"))
                self.peers[peer_ip] = payload
            except socket.timeout:
                continue
            except Exception as e:
                # Decrypt errors (different keys etc.)
                pass

        sock.close()

    # ── Encryption Helpers ─────────────────────────────────────────────────

    def encrypt_data(self, payload: Dict[str, Any]) -> str:
        """Encrypts data package returning base64 string."""
        if not self._fernet:
            raise ValueError("Encryption not initialized")
        raw = json.dumps(payload).encode("utf-8")
        return self._fernet.encrypt(raw).decode("utf-8")

    def decrypt_data(self, token_str: str) -> Dict[str, Any]:
        """Decrypts data package returning dict."""
        if not self._fernet:
            raise ValueError("Encryption not initialized")
        decrypted = self._fernet.decrypt(token_str.encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))

    # ── Sync Operations ────────────────────────────────────────────────────

    def get_sync_payload(self) -> Dict[str, Any]:
        """Gathers active context and database items for serialization."""
        payload = {
            "device": self.settings.FRIENDLY_DEVICE_NAME,
            "timestamp": time.time(),
            "context": {}
        }

        # Gather active context if ContextSkill is registered
        if self.app_state:
            planner = getattr(self.app_state, "planner_agent", None)
            if planner and hasattr(planner, "skills_registry"):
                context_skill = planner.skills_registry.skills.get("ContextSkill")
                if context_skill:
                    payload["context"] = context_skill.active_context
                    
        return payload

    def apply_sync_payload(self, payload: Dict[str, Any]) -> None:
        """Merges incoming peer context state into memory."""
        peer_device = payload.get("device", "Unknown Peer")
        peer_context = payload.get("context", {})
        
        logger.info("Applying sync state from peer: '{}'", peer_device)
        
        # Log context merge details
        if peer_context and "window_title" in peer_context:
            logger.debug("Peer Context: {} ({}) -> Project: {}", 
                         peer_context.get("window_title", ""), 
                         peer_context.get("process_name", ""),
                         peer_context.get("inferred_project", ""))
            
            # Can save this state to memory database for context querying
            if self.app_state and hasattr(self.app_state, "memory_service") and self.app_state.memory_service:
                import asyncio
                mem = self.app_state.memory_service
                asyncio.create_task(mem.store_memory(
                    content=f"Peer device '{peer_device}' active window: {peer_context.get('window_title')} ({peer_context.get('process_name')}) working on project: {peer_context.get('inferred_project')}",
                    metadata={"type": "peer_sync", "device": peer_device}
                ))
