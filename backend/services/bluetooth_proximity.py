"""
Bluetooth RSSI Proximity Auto-Lock & Biometric Wake Service.

Monitors real-time Bluetooth Low Energy (BLE) RSSI signal strength from the user's
paired mobile device. Implements EMA signal smoothing and temporal debouncing to
prevent false-positive locks, executes native Win32 LockWorkStation on departure,
and triggers FaceAuth biometric liveness verification on return.
"""

import os
import time
import ctypes
import asyncio
from typing import Dict, Any, Optional, List, Callable
from collections import deque
from loguru import logger

try:
    from bleak import BleakScanner
    from bleak.exc import BleakError, BleakBluetoothNotAvailableError
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

from backend.services.manager import ServiceManager


class ProximityState:
    UNKNOWN = "UNKNOWN"
    IN_RANGE = "IN_RANGE"
    DEPARTING = "DEPARTING"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    LOCKED = "LOCKED"


class BluetoothProximityService:
    """
    Continuous BLE RSSI proximity engine for Windows workstation auto-locking
    and multi-factor biometric wake on user return.
    """

    def __init__(
        self,
        target_device_name: str = "JARVIS Companion",
        target_device_address: Optional[str] = None,
        rssi_lock_threshold: int = -82,      # dBm: weaker than this triggers departure evaluation
        rssi_wake_threshold: int = -65,      # dBm: stronger than this triggers biometric wake
        debounce_seconds: float = 7.0,       # Sustained signal loss before locking
        smoothing_alpha: float = 0.35,       # Exponential Moving Average factor
        auto_lock_enabled: bool = True,
        biometric_wake_enabled: bool = True
    ):
        self.target_device_name = target_device_name
        self.target_device_address = target_device_address.upper() if target_device_address else None
        self.rssi_lock_threshold = rssi_lock_threshold
        self.rssi_wake_threshold = rssi_wake_threshold
        self.debounce_seconds = debounce_seconds
        self.smoothing_alpha = smoothing_alpha
        self.auto_lock_enabled = auto_lock_enabled
        self.biometric_wake_enabled = biometric_wake_enabled

        # Telemetry and state tracking
        self.state: str = ProximityState.UNKNOWN
        self.radio_available: bool = True
        self.is_monitoring: bool = False
        self.raw_rssi: Optional[int] = None
        self.smoothed_rssi: Optional[float] = None
        self.last_seen_timestamp: float = 0.0
        self.departure_start_timestamp: Optional[float] = None
        self.recent_rssi_history: deque = deque(maxlen=20)
        self._scanner: Optional[Any] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._on_lock_callbacks: List[Callable] = []
        self._on_wake_callbacks: List[Callable] = []

        logger.info(
            f"BluetoothProximityService initialized (Target: '{self.target_device_name}', "
            f"Lock Threshold: {self.rssi_lock_threshold} dBm, Debounce: {self.debounce_seconds}s)"
        )

    # ── Configuration & Target Pairing ────────────────────────────────────────

    def set_target_device(self, name_or_address: str) -> None:
        """Set paired phone's Bluetooth broadcast name or MAC/UUID address."""
        if ":" in name_or_address or "-" in name_or_address:
            self.target_device_address = name_or_address.upper()
            logger.info(f"Proximity target address updated to: {self.target_device_address}")
        else:
            self.target_device_name = name_or_address
            logger.info(f"Proximity target name updated to: '{self.target_device_name}'")

    def configure_thresholds(
        self,
        lock_threshold: Optional[int] = None,
        wake_threshold: Optional[int] = None,
        debounce_seconds: Optional[float] = None,
        auto_lock_enabled: Optional[bool] = None,
        biometric_wake_enabled: Optional[bool] = None
    ) -> None:
        """Update proximity calibration thresholds in real-time."""
        if lock_threshold is not None:
            self.rssi_lock_threshold = max(-100, min(-40, lock_threshold))
        if wake_threshold is not None:
            self.rssi_wake_threshold = max(-80, min(-30, wake_threshold))
        if debounce_seconds is not None:
            self.debounce_seconds = max(2.0, min(30.0, debounce_seconds))
        if auto_lock_enabled is not None:
            self.auto_lock_enabled = auto_lock_enabled
        if biometric_wake_enabled is not None:
            self.biometric_wake_enabled = biometric_wake_enabled

        logger.info(
            f"Proximity config updated: LockThreshold={self.rssi_lock_threshold}dBm, "
            f"WakeThreshold={self.rssi_wake_threshold}dBm, Debounce={self.debounce_seconds}s, "
            f"AutoLock={self.auto_lock_enabled}, BiometricWake={self.biometric_wake_enabled}"
        )

    # ── Signal Filtering & Debounced State Machine ────────────────────────────

    def process_rssi_sample(self, rssi: int, device_address: str, device_name: str) -> Dict[str, Any]:
        """
        Ingest a raw RSSI reading, apply Exponential Moving Average (EMA) smoothing,
        and evaluate the debounced departure/return state machine.
        """
        now = time.time()
        self.raw_rssi = rssi
        self.last_seen_timestamp = now
        self.recent_rssi_history.append((now, rssi))

        # Exponential Moving Average smoothing
        if self.smoothed_rssi is None:
            self.smoothed_rssi = float(rssi)
        else:
            self.smoothed_rssi = (self.smoothing_alpha * rssi) + ((1.0 - self.smoothing_alpha) * self.smoothed_rssi)

        current_smooth = self.smoothed_rssi

        # ── State Evaluation ──
        if current_smooth >= self.rssi_wake_threshold:
            # User is in close proximity
            if self.state in (ProximityState.OUT_OF_RANGE, ProximityState.LOCKED, ProximityState.DEPARTING):
                logger.info(f"📱 User returned to workstation (Smoothed RSSI: {current_smooth:.1f} dBm).")
                self._trigger_biometric_wake()
            self.state = ProximityState.IN_RANGE
            self.departure_start_timestamp = None

        elif current_smooth <= self.rssi_lock_threshold:
            # Signal is weak -> Evaluate debounced departure
            if self.state == ProximityState.IN_RANGE:
                self.state = ProximityState.DEPARTING
                self.departure_start_timestamp = now
                logger.info(f"⚠️ Proximity signal weakened ({current_smooth:.1f} dBm). Starting {self.debounce_seconds}s debounce timer...")

            elif self.state == ProximityState.DEPARTING and self.departure_start_timestamp:
                elapsed_departing = now - self.departure_start_timestamp
                if elapsed_departing >= self.debounce_seconds:
                    logger.warning(f"🔒 Departure confirmed ({elapsed_departing:.1f}s sustained weak signal). Triggering auto-lock.")
                    self.state = ProximityState.OUT_OF_RANGE
                    self._trigger_auto_lock()

        else:
            # Intermediate zone (-65 to -82 dBm) - keep current state, reset departing timer if was departing
            if self.state == ProximityState.DEPARTING and self.departure_start_timestamp:
                if (now - self.departure_start_timestamp) < self.debounce_seconds:
                    # Marginal signal, cancel transient departure
                    self.state = ProximityState.IN_RANGE
                    self.departure_start_timestamp = None

        return self.get_telemetry()

    def evaluate_heartbeat_timeout(self) -> None:
        """Called periodically when no BLE packets are detected (complete signal loss)."""
        if not self.last_seen_timestamp:
            return

        now = time.time()
        time_since_seen = now - self.last_seen_timestamp

        if time_since_seen >= self.debounce_seconds and self.state in (ProximityState.IN_RANGE, ProximityState.DEPARTING):
            logger.warning(f"🔒 BLE signal completely lost for {time_since_seen:.1f}s. Triggering workstation auto-lock.")
            self.state = ProximityState.OUT_OF_RANGE
            self._trigger_auto_lock()

    # ── Auto-Lock Execution & Biometric Wake Security Model ───────────────────

    def _trigger_auto_lock(self) -> None:
        """
        Execute Win32 LockWorkStation native system lock.
        """
        self.state = ProximityState.LOCKED
        if self.auto_lock_enabled:
            try:
                logger.info("Executing native Windows LockWorkStation()...")
                result = ctypes.windll.user32.LockWorkStation()
                logger.info(f"✓ Workstation locked successfully (Win32 result: {result}).")
            except Exception as e:
                logger.error(f"Failed to execute LockWorkStation: {e}")
        else:
            logger.info("Auto-lock is disabled in settings or test mode; skipped physical LockWorkStation call.")

        # Notify registered callbacks / websocket broadcast
        for cb in self._on_lock_callbacks:
            try:
                cb(self.get_telemetry())
            except Exception as ex:
                logger.warning(f"Lock callback error: {ex}")

    def _trigger_biometric_wake(self) -> None:
        """
        SECURITY MODEL DECISION:
        We deliberately do NOT auto-unlock Windows based purely on Bluetooth RSSI.
        BLE signals penetrate doors/windows and can be easily spoofed or amplified over range.
        
        Instead, proximity acts as a 'Biometric Wake' trigger:
        When the paired phone returns to range, JARVIS immediately activates the
        FaceAuthEngine with live Eye-Aspect-Ratio (EAR) blink + head movement liveness verification.
        Only when the authorized user's face is verified with positive liveness does the system unlock.
        """
        logger.info("👁️ Proximity Biometric Wake triggered: Activating FaceAuthEngine with liveness check...")
        
        face_auth = ServiceManager.get_instance("face_auth_engine")
        if face_auth and self.biometric_wake_enabled:
            try:
                # Signal face auth engine to begin scanning
                if hasattr(face_auth, "trigger_proximity_wake"):
                    face_auth.trigger_proximity_wake()
                logger.info("✓ FaceAuthEngine biometric verification armed for user return.")
            except Exception as e:
                logger.warning(f"Failed to arm FaceAuthEngine: {e}")

        for cb in self._on_wake_callbacks:
            try:
                cb(self.get_telemetry())
            except Exception as ex:
                logger.warning(f"Wake callback error: {ex}")

    # ── Continuous Scanner Loop ───────────────────────────────────────────────

    async def start_monitoring(self) -> None:
        """Start asynchronous continuous BLE advertisement scanner."""
        if not HAS_BLEAK:
            logger.warning("Bleak library not available. Proximity monitoring will run in fallback simulation mode.")
            self.radio_available = False
            return

        self.is_monitoring = True
        self._monitor_task = asyncio.create_task(self._scanner_loop())
        logger.info("✓ Bluetooth proximity background monitoring task launched.")

    async def stop_monitoring(self) -> None:
        """Stop BLE scanner loop."""
        self.is_monitoring = False
        if self._scanner:
            try:
                await self._scanner.stop()
            except Exception:
                pass
            self._scanner = None
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("Bluetooth proximity monitoring stopped.")

    async def _scanner_loop(self) -> None:
        """Background continuous scanner loop catching BLE advertisements."""
        def _detection_callback(device, advertisement_data):
            name = device.name or advertisement_data.local_name or ""
            addr = device.address.upper()
            rssi = advertisement_data.rssi if hasattr(advertisement_data, "rssi") else device.rssi

            # Check matching target
            matched = False
            if self.target_device_address and addr == self.target_device_address:
                matched = True
            elif self.target_device_name and (self.target_device_name.lower() in name.lower()):
                matched = True

            if matched:
                self.process_rssi_sample(rssi, addr, name)

        while self.is_monitoring:
            try:
                self._scanner = BleakScanner(detection_callback=_detection_callback)
                await self._scanner.start()
                self.radio_available = True
                logger.info("✓ Real BLE hardware scanner active on Windows.")

                while self.is_monitoring:
                    await asyncio.sleep(1.0)
                    self.evaluate_heartbeat_timeout()

            except BleakBluetoothNotAvailableError as bne:
                self.radio_available = False
                logger.warning(f"Bluetooth radio offline/disabled: {bne}. Retrying in 10s...")
                await asyncio.sleep(10.0)
            except Exception as e:
                logger.warning(f"BLE scanner notice: {e}. Re-establishing in 5s...")
                await asyncio.sleep(5.0)
            finally:
                if self._scanner:
                    try:
                        await self._scanner.stop()
                    except Exception:
                        pass

    # ── Telemetry & Status ────────────────────────────────────────────────────

    def get_telemetry(self) -> Dict[str, Any]:
        """Return real-time RSSI proximity metrics."""
        return {
            "state": self.state,
            "target_device_name": self.target_device_name,
            "target_device_address": self.target_device_address,
            "radio_available": self.radio_available,
            "is_monitoring": self.is_monitoring,
            "raw_rssi": self.raw_rssi,
            "smoothed_rssi": round(self.smoothed_rssi, 1) if self.smoothed_rssi is not None else None,
            "lock_threshold_dbm": self.rssi_lock_threshold,
            "wake_threshold_dbm": self.rssi_wake_threshold,
            "debounce_seconds": self.debounce_seconds,
            "auto_lock_enabled": self.auto_lock_enabled,
            "biometric_wake_enabled": self.biometric_wake_enabled,
            "seconds_since_last_seen": round(time.time() - self.last_seen_timestamp, 1) if self.last_seen_timestamp else None
        }


# Global singleton instance
bluetooth_proximity_service = BluetoothProximityService()
