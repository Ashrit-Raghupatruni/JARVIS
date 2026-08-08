"""
JARVIS AI Desktop Assistant — Double Clap Listener Service.

Listens to the default microphone for a double clap (two loud transients
spaced close together) and executes a welcome sequence (playing a track,
opening site monitoring views on multiple displays, synthesizing welcome greeting).
"""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
import webbrowser
from pathlib import Path
from typing import Optional, Tuple, Set

import numpy as np
import sounddevice as sd

from backend.config import get_settings
from backend.utils.logger import logger


class ClapService:
    """
    Managed service that runs a background thread listening for a double-clap
    and triggers a customizable welcome flow.
    """

    def __init__(self, on_clap_detected=None) -> None:
        self.settings = get_settings()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stream: Optional[sd.InputStream] = None
        self.welcome_sequence_done = False
        self.on_clap_detected = on_clap_detected

        # State tracking
        self.last_logged_double: float = 0.0
        self.first_clap_time: Optional[float] = None
        self.spike_armed: bool = True
        self.noise_floor: float = 1e-4

    # ── Startup & Shutdown ───────────────────────────────────────────────

    def start(self) -> None:
        """Start the background clap listener thread."""
        if not self.settings.CLAP_ENABLED:
            logger.info("Clap listener is disabled in settings.")
            return

        if self._thread and self._thread.is_alive():
            logger.warning("Clap service is already running.")
            return

        self._stop_event.clear()
        self.welcome_sequence_done = False
        self._thread = threading.Thread(target=self._run_loop, name="ClapListener", daemon=True)
        self._thread.start()
        logger.info("✓ Clap listener background thread started (mode={}).", self.settings.CLAP_MODE)

    def stop(self) -> None:
        """Stop the background clap listener thread and release audio devices."""
        self._stop_event.set()
        if self._stream:
            try:
                self._stream.close()
            except Exception as e:
                logger.error("Error closing clap audio stream: {}", e)
            self._stream = None

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Clap listener background thread stopped.")

    # ── Background Listen Loop ───────────────────────────────────────────

    def _block_samples(self) -> int:
        n = int(self.settings.CLAP_SAMPLE_RATE * self.settings.CLAP_BLOCK_MS / 1000)
        return max(n, 1)

    def _rms_mono(self, block: np.ndarray) -> float:
        if block.ndim > 1:
            block = np.mean(block.astype(np.float64), axis=1)
        else:
            block = block.astype(np.float64)
        if block.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(block**2)))

    def _is_sharp_clap_impulse(self, block: np.ndarray, level: float) -> bool:
        """Filter out speech, background noise, and music. Returns True ONLY for sharp acoustic clap impulses."""
        if block is None or block.size <= 2 or level < 0.035:  # Minimum energy and sample gate
            return False
        
        flat = block.flatten()
        if flat.size <= 2:
            return False

        # Peak-to-Average Power Ratio (PAPR) check
        peak = float(np.max(np.abs(flat)))
        papr = peak / (level + 1e-6)
        if papr < 3.2:  # Speech vowels have PAPR < 3.0, sharp claps have PAPR > 3.2
            return False

        # Transient step height check (max first derivative spike)
        diff = np.diff(flat.astype(np.float64))
        if diff.size == 0:
            return False

        max_diff = float(np.max(np.abs(diff)))
        if max_diff < peak * 0.5:
            return False

        return True

    def _is_speaker_active(self) -> bool:
        """Return True if TTS audio or system audio playback is active to prevent self-triggering."""
        try:
            from backend.services.manager import ServiceManager
            tts = ServiceManager.get_instance("tts_service")
            if tts and hasattr(tts, "is_speaking") and tts.is_speaking():
                return True
        except Exception:
            pass
        return False

    def _run_loop(self) -> None:
        blocksize = self._block_samples()
        self.noise_floor = 1e-4
        self.last_logged_double = 0.0
        self.first_clap_time = None
        self.spike_armed = True

        mode = getattr(self.settings, "CLAP_MODE", "double").lower()
        sensitivity = getattr(self.settings, "CLAP_SENSITIVITY", 0.7)
        spike_ratio = max(3.5, self.settings.CLAP_SPIKE_RATIO * (1.3 - sensitivity * 0.5))

        logger.info(
            "Clap listener active (mode={}, spike_ratio={:.2f}, gap={}–{}s).",
            mode,
            spike_ratio,
            self.settings.CLAP_MIN_DOUBLE_GAP_S,
            self.settings.CLAP_MAX_DOUBLE_GAP_S,
        )

        start_time = time.monotonic()

        try:
            with sd.InputStream(
                samplerate=self.settings.CLAP_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
            ) as stream:
                self._stream = stream
                while not self._stop_event.is_set():
                    data, overflowed = stream.read(blocksize)
                    if overflowed:
                        logger.warning("Clap listener input overflow; try increasing CLAP_BLOCK_MS")

                    # Skip processing during startup transient calibration period or when speaker is active
                    if time.monotonic() - start_time < 2.0 or self._is_speaker_active():
                        continue

                    level = self._rms_mono(data)

                    # Update noise floor during quiet periods
                    quiet_gate = self.noise_floor * self.settings.CLAP_QUIET_GATE_MULT
                    if level < quiet_gate:
                        self.noise_floor = self.settings.CLAP_NOISE_FLOOR_ALPHA * self.noise_floor + (
                            1.0 - self.settings.CLAP_NOISE_FLOOR_ALPHA
                        ) * level
                        self.noise_floor = max(self.noise_floor, 1e-7)

                    threshold = max(self.noise_floor * spike_ratio, self.settings.CLAP_MIN_RMS)
                    now = time.monotonic()
                    retrigger_level = threshold * self.settings.CLAP_RETRIGGER_RATIO

                    if level < retrigger_level:
                        self.spike_armed = True

                    # Enforce strict PAPR sharp impulse verification
                    if (
                        self.spike_armed
                        and level >= threshold
                        and self._is_sharp_clap_impulse(data, level)
                        and (now - self.last_logged_double) >= self.settings.CLAP_COOLDOWN_S
                    ):
                        self.spike_armed = False
                        current_mode = getattr(self.settings, "CLAP_MODE", "double").lower()

                        if current_mode == "single":
                            self.last_logged_double = now
                            logger.info("Single clap detected! (rms={:.5f}, threshold={:.5f})", level, threshold)
                            if self.on_clap_detected:
                                try:
                                    self.on_clap_detected("single")
                                except Exception as cb_err:
                                    logger.error(f"Error in clap callback: {cb_err}")
                            if not self.welcome_sequence_done:
                                self.welcome_sequence_done = True
                                threading.Thread(target=self._run_actions, name="ClapActions", daemon=True).start()

                        else:  # Double clap mode
                            if self.first_clap_time is None:
                                self.first_clap_time = now
                            else:
                                gap = now - self.first_clap_time
                                if gap < self.settings.CLAP_MIN_DOUBLE_GAP_S:
                                    pass
                                elif gap <= self.settings.CLAP_MAX_DOUBLE_GAP_S:
                                    self.first_clap_time = None
                                    self.last_logged_double = now
                                    logger.info("Double clap detected! (gap={:.3f}s, rms={:.5f})", gap, level)
                                    if self.on_clap_detected:
                                        try:
                                            self.on_clap_detected("double")
                                        except Exception as cb_err:
                                            logger.error(f"Error in clap callback: {cb_err}")
                                    if not self.welcome_sequence_done:
                                        self.welcome_sequence_done = True
                                        threading.Thread(target=self._run_actions, name="ClapActions", daemon=True).start()
                                else:
                                    self.first_clap_time = now

        except Exception as e:
            if self._stop_event.is_set():
                logger.debug("Clap stream loop caught exception after stop: {}", e)
            else:
                logger.error("Error in clap listener loop: {}", e)

    # ── Actions Execution ────────────────────────────────────────────────

    def _run_actions(self) -> None:
        """Run all welcome sequence actions."""
        self.play_song(self.settings.CLAP_SONG_URI)
        self.open_claude_in_chrome()
        self.open_binance_btc_in_chrome()

        if self.settings.CLAP_WELCOME_ENABLED and self.settings.CLAP_WELCOME_PHRASE.strip():
            delay = max(0.0, self.settings.CLAP_WELCOME_DELAY_S)
            if delay > 0:
                time.sleep(delay)
            # Run ElevenLabs TTS in a separate background thread
            threading.Thread(target=self.say_jarvis_welcome, name="ClapTTS", daemon=True).start()

        self.open_cursor_window()

    # ── Action Implementation details ────────────────────────────────────

    def play_song(self, uri: str) -> None:
        u = uri.strip()
        if not u:
            return
        logger.info("Opening song track: {}", u)
        try:
            if sys.platform == "win32":
                os.startfile(u)
            else:
                webbrowser.open(u)
        except Exception as e:
            logger.warning("Could not open SONG_URI: {}", e)

    def _chrome_executable(self) -> Optional[str]:
        if sys.platform == "win32":
            for base in (
                os.environ.get("ProgramFiles", r"C:\Program Files"),
                os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                os.environ.get("LOCALAPPDATA", ""),
            ):
                if not base:
                    continue
                p = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
                if os.path.isfile(p):
                    return p
        return shutil.which("google-chrome") or shutil.which("chrome")

    def _win32_sorted_monitor_rects(self) -> list[Tuple[int, int, int, int]]:
        if sys.platform != "win32":
            return []
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        collected: list[Tuple[int, int, int, int]] = []

        @ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        def _cb(_hm, _hdc, lprc, _lp):
            r = lprc.contents
            collected.append((int(r.left), int(r.top), int(r.right), int(r.bottom)))
            return True

        ctypes.windll.user32.EnumDisplayMonitors(None, None, _cb, 0)
        collected.sort(key=lambda t: (t[0], t[1]))
        return collected

    def _chrome_monitor_bounds(self, one_based_index: int) -> Tuple[int, int, int, int]:
        rects = self._win32_sorted_monitor_rects()
        if not rects:
            return (0, 0, 1920, 1080)
        idx = one_based_index - 1
        if idx < 0:
            idx = 0
        if idx >= len(rects):
            logger.warning(
                "Monitor {} requested but only {} found; using last monitor.",
                one_based_index, len(rects)
            )
            idx = len(rects) - 1
        return rects[idx]

    def _chrome_monitor_top_left(self, one_based_index: int) -> Tuple[int, int]:
        l, t, _, _ = self._chrome_monitor_bounds(one_based_index)
        return (l, t)

    def _chrome_monitor_pixel_size(self, one_based_index: int) -> Tuple[int, int]:
        l, t, r, b = self._chrome_monitor_bounds(one_based_index)
        return (max(320, r - l), max(240, b - t))

    def _chrome_window_size(self) -> Tuple[int, int]:
        w = int(os.environ.get("CHROME_WINDOW_WIDTH", "1400").strip())
        h = int(os.environ.get("CHROME_WINDOW_HEIGHT", "900").strip())
        return (max(400, w), max(300, h))

    def _chrome_site_user_data_dir(self, site_key: str) -> str:
        p = Path(tempfile.gettempdir()) / "clap-trigger-chrome" / site_key
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _chrome_new_window_wait_timeout_s(self) -> float:
        try:
            return max(3.0, float(os.environ.get("CHROME_NEW_WINDOW_WAIT_S", "25").strip()))
        except ValueError:
            return 25.0

    def _chrome_top_level_browser_hwnds_win32(self) -> Set[int]:
        if sys.platform != "win32":
            return set()
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        GW_OWNER = 4
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        found: Set[int] = set()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd: wintypes.HWND, _lp: wintypes.LPARAM) -> bool:
            if user32.GetWindow(hwnd, GW_OWNER):
                return True
            if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            if not user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return True
            hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not hproc:
                return True
            try:
                buf = ctypes.create_unicode_buffer(4096)
                sz = wintypes.DWORD(len(buf))
                if not kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(sz)):
                    return True
                exe_path = buf.value
            finally:
                kernel32.CloseHandle(hproc)
            if os.path.basename(exe_path).lower() != "chrome.exe":
                return True
            r = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
                return True
            w, h = r.right - r.left, r.bottom - r.top
            if w < 80 or h < 80:
                return True
            found.add(int(hwnd))
            return True

        user32.EnumWindows(_enum, 0)
        return found

    def _wait_new_chrome_hwnd_win32(self, before: Set[int], timeout: float) -> Optional[int]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.12)
            now = self._chrome_top_level_browser_hwnds_win32()
            new = now - before
            if not new:
                continue
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            best: Optional[int] = None
            best_area = 0
            for h in new:
                r = wintypes.RECT()
                if user32.GetWindowRect(h, ctypes.byref(r)):
                    a = max(0, r.right - r.left) * max(0, r.bottom - r.top)
                    if a > best_area:
                        best_area = a
                        best = h
            if best is not None:
                return best
        return None

    def _chrome_snap_window_to_monitor_win32(
        self,
        hwnd: int,
        one_based_monitor: int,
        *,
        fullscreen: bool,
        windowed_size: Optional[Tuple[int, int]],
    ) -> None:
        import ctypes

        ml, mt, mr, mb = self._chrome_monitor_bounds(one_based_monitor)
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        SW_SHOWMAXIMIZED = 3
        HWND_TOP = 0
        SWP_SHOWWINDOW = 0x0040
        SWP_FRAMECHANGED = 0x0020
        flags = SWP_SHOWWINDOW | SWP_FRAMECHANGED

        user32.ShowWindow(hwnd, SW_RESTORE)
        if fullscreen:
            w, h = mr - ml, mb - mt
            x, y = ml, mt
        else:
            ww, wh = windowed_size or self._chrome_window_size()
            w, h = ww, wh
            x = ml + max(0, (mr - ml - w) // 2)
            y = mt + max(0, (mb - mt - h) // 2)
        user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, flags)

        if fullscreen:
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
            KEYEVENTF_KEYUP = 0x0002
            VK_F11 = 0x7A
            fg = user32.GetForegroundWindow()
            tid_tgt = user32.GetWindowThreadProcessId(hwnd, None)
            tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
            if tid_fg and tid_tgt:
                user32.AttachThreadInput(tid_fg, tid_tgt, True)
            user32.SetForegroundWindow(hwnd)
            if tid_fg and tid_tgt:
                user32.AttachThreadInput(tid_fg, tid_tgt, False)
            user32.keybd_event(VK_F11, 0, 0, 0)
            user32.keybd_event(VK_F11, 0, KEYEVENTF_KEYUP, 0)

    def _open_url_in_chrome(
        self,
        url: str,
        *,
        new_window: bool = True,
        label: str = "URL",
        window_position: Optional[Tuple[int, int]] = None,
        window_size: Optional[Tuple[int, int]] = None,
        fullscreen: bool = False,
        win32_post_fullscreen_monitor: Optional[int] = None,
        user_data_dir: Optional[str] = None,
    ) -> None:
        u = url.strip()
        if not u:
            return
        chrome = self._chrome_executable()
        try:
            if chrome:
                args = [chrome]
                if user_data_dir:
                    args.append(f"--user-data-dir={user_data_dir}")
                    args.append("--no-first-run")
                if new_window:
                    args.append("--new-window")
                if window_position is not None:
                    x, y = window_position
                    args.append(f"--window-position={x},{y}")
                if window_size:
                    args.append(f"--window-size={window_size[0]},{window_size[1]}")
                if fullscreen and not (
                    sys.platform == "win32" and win32_post_fullscreen_monitor is not None
                ):
                    args.append("--start-fullscreen")
                args.append(u)
                popen_kw: dict = {
                    "args": args,
                    "stdin": subprocess.DEVNULL,
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                }
                if sys.platform == "win32":
                    popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
                before: Optional[Set[int]] = None
                if sys.platform == "win32" and win32_post_fullscreen_monitor is not None:
                    before = self._chrome_top_level_browser_hwnds_win32()
                subprocess.Popen(**popen_kw)
                if sys.platform == "win32" and win32_post_fullscreen_monitor is not None:
                    mon = win32_post_fullscreen_monitor
                    hwnd = self._wait_new_chrome_hwnd_win32(before, self._chrome_new_window_wait_timeout_s())
                    if hwnd is not None:
                        self._chrome_snap_window_to_monitor_win32(
                            hwnd,
                            mon,
                            fullscreen=fullscreen,
                            windowed_size=window_size if not fullscreen else None,
                        )
                    else:
                        logger.warning(
                            "Chrome: timed out waiting for new window ({}); check settings or close Chrome.",
                            label,
                        )
            else:
                logger.warning("Chrome not found; opening {} in default browser.", label)
                webbrowser.open(u)
        except Exception as e:
            logger.error("Could not open {} in Chrome: {}", label, e)

    def open_claude_in_chrome(self) -> None:
        if not self.settings.CLAP_OPEN_CLAUDE_CHROME:
            return
        url = os.environ.get("CLAUDE_CODE_URL", "https://claude.ai/new").strip()
        pos: Optional[Tuple[int, int]] = None
        size: Optional[Tuple[int, int]] = None
        fs = self.settings.CLAP_CHROME_FULLSCREEN
        post_mon: Optional[int] = None
        user_data: Optional[str] = None
        if sys.platform == "win32":
            post_mon = self.settings.CLAP_CLAUDE_MONITOR
            pos = self._chrome_monitor_top_left(self.settings.CLAP_CLAUDE_MONITOR)
            if fs:
                size = self._chrome_monitor_pixel_size(self.settings.CLAP_CLAUDE_MONITOR)
            else:
                size = self._chrome_window_size()
            if self.settings.CLAP_CHROME_SEPARATE_PROFILES:
                user_data = self._chrome_site_user_data_dir("claude")
        elif not fs:
            size = self._chrome_window_size()
        self._open_url_in_chrome(
            url,
            new_window=True,
            label="Claude",
            window_position=pos,
            window_size=size,
            fullscreen=fs,
            win32_post_fullscreen_monitor=post_mon,
            user_data_dir=user_data,
        )

    def open_binance_btc_in_chrome(self) -> None:
        if not self.settings.CLAP_OPEN_BINANCE_CHROME:
            return
        url = os.environ.get("BINANCE_BTC_URL", "https://www.binance.com/en/trade/BTC_USDT").strip()
        pos: Optional[Tuple[int, int]] = None
        size: Optional[Tuple[int, int]] = None
        fs = self.settings.CLAP_CHROME_FULLSCREEN
        post_mon: Optional[int] = None
        user_data: Optional[str] = None
        if sys.platform == "win32":
            post_mon = self.settings.CLAP_BINANCE_MONITOR
            pos = self._chrome_monitor_top_left(self.settings.CLAP_BINANCE_MONITOR)
            if fs:
                size = self._chrome_monitor_pixel_size(self.settings.CLAP_BINANCE_MONITOR)
            else:
                size = self._chrome_window_size()
            if self.settings.CLAP_CHROME_SEPARATE_PROFILES:
                user_data = self._chrome_site_user_data_dir("binance")
        elif not fs:
            size = self._chrome_window_size()
        self._open_url_in_chrome(
            url,
            new_window=True,
            label="Binance BTC",
            window_position=pos,
            window_size=size,
            fullscreen=fs,
            win32_post_fullscreen_monitor=post_mon,
            user_data_dir=user_data,
        )

    # ── ElevenLabs TTS Welcome Greeting ──────────────────────────────────

    def _elevenlabs_pcm_sample_rate(self, output_format: str) -> int:
        if self.settings.ELEVENLABS_PCM_SAMPLE_RATE:
            return self.settings.ELEVENLABS_PCM_SAMPLE_RATE
        if output_format.startswith("pcm_"):
            try:
                return int(output_format.split("_", maxsplit=1)[1])
            except (ValueError, IndexError):
                pass
        return 24000

    def _jarvis_welcome_cache_dir(self) -> Path:
        if self.settings.CLAP_WELCOME_CACHE_DIR:
            return Path(self.settings.CLAP_WELCOME_CACHE_DIR).expanduser().resolve()
        return Path(self.settings.DATA_DIR) / "jarvis_welcome"

    def _jarvis_welcome_cache_path(
        self, text: str, voice_id: str, model_id: str, output_format: str
    ) -> Path:
        key = f"{text}|{voice_id}|{model_id}|{output_format}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()[:24]
        return self._jarvis_welcome_cache_dir() / f"{digest}.wav"

    def _play_pcm_wav_file(self, path: Path) -> bool:
        try:
            with wave.open(str(path), "rb") as wf:
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                rate = wf.getframerate()
                if ch != 1 or sw != 2:
                    logger.warning("Unsupported cached WAV (channels={}, width={}).", ch, sw)
                    return False
                raw = wf.readframes(wf.getnframes())
        except Exception as e:
            logger.warning("Could not read cached welcome audio: {}", e)
            return False

        if not raw:
            return False
        pcm_i16 = np.frombuffer(raw, dtype=np.int16)
        pcm_f = pcm_i16.astype(np.float32) / 32768.0
        try:
            sd.play(pcm_f, rate)
            sd.wait()
            return True
        except Exception as e:
            logger.warning("Could not play cached welcome audio: {}", e)
            return False

    def _save_pcm_wav_file(self, path: Path, pcm_bytes: bytes, sample_rate: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with wave.open(str(tmp), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_bytes)
            tmp.replace(path)
        except OSError:
            if tmp.is_file():
                tmp.unlink(missing_ok=True)
            raise

    def say_jarvis_welcome(self) -> None:
        if not self.settings.CLAP_WELCOME_ENABLED or not self.settings.CLAP_WELCOME_PHRASE.strip():
            return
        text = self.settings.CLAP_WELCOME_PHRASE.strip()
        vid = self.settings.ELEVENLABS_VOICE_ID
        model_id = self.settings.ELEVENLABS_MODEL_ID
        output_format = self.settings.ELEVENLABS_OUTPUT_FORMAT
        pcm_rate = self._elevenlabs_pcm_sample_rate(output_format)

        if not vid:
            logger.warning("Set ELEVENLABS_VOICE_ID in the environment or .env for ElevenLabs TTS.")
            return

        cache_path = self._jarvis_welcome_cache_path(text, vid, model_id, output_format)
        if self.settings.CLAP_WELCOME_CACHE_ENABLED and cache_path.is_file():
            logger.info("Playing welcome from cache: {}", cache_path)
            if self._play_pcm_wav_file(cache_path):
                return
            logger.warning("Cache play failed; fetching fresh from ElevenLabs API.")

        api_key = self.settings.ELEVENLABS_API_KEY
        if not api_key:
            logger.warning("Set ELEVENLABS_API_KEY in the environment or .env for ElevenLabs TTS.")
            return

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            logger.warning("ElevenLabs SDK not installed. Skip welcome voice.")
            return

        try:
            client = ElevenLabs(api_key=api_key)
            chunks = client.text_to_speech.convert(
                voice_id=vid,
                text=text,
                model_id=model_id,
                output_format=output_format,
            )
            raw = b"".join(chunks)
        except Exception as e:
            logger.error("ElevenLabs TTS conversion failed: {}", e)
            return

        if not raw:
            logger.warning("ElevenLabs API returned empty audio.")
            return

        if self.settings.CLAP_WELCOME_CACHE_ENABLED:
            try:
                self._save_pcm_wav_file(cache_path, raw, pcm_rate)
                logger.info("Saved welcome audio to cache: {}", cache_path)
            except Exception as e:
                logger.warning("Could not save welcome audio to cache: {}", e)

        pcm_i16 = np.frombuffer(raw, dtype=np.int16)
        pcm_f = pcm_i16.astype(np.float32) / 32768.0
        try:
            sd.play(pcm_f, pcm_rate)
            sd.wait()
        except Exception as e:
            logger.error("Could not play ElevenLabs audio stream: {}", e)

    # ── Cursor window Focus / Start ──────────────────────────────────────

    def _cursor_executable(self) -> Optional[str]:
        if sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA", "")
            for sub in ("Programs\\cursor\\Cursor.exe", "Programs\\Cursor\\Cursor.exe"):
                if local:
                    p = os.path.join(local, *sub.split("\\"))
                    if os.path.isfile(p):
                        return p
        return shutil.which("cursor")

    def _cursor_largest_main_hwnd_win32(self) -> Optional[int]:
        if sys.platform != "win32":
            return None
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        GW_OWNER = 4
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        candidates: list[Tuple[int, wintypes.HWND]] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd: wintypes.HWND, _lp: wintypes.LPARAM) -> bool:
            if user32.GetWindow(hwnd, GW_OWNER):
                return True
            if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            if not user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return True
            hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not hproc:
                return True
            try:
                buf = ctypes.create_unicode_buffer(4096)
                sz = wintypes.DWORD(len(buf))
                if not kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(sz)):
                    return True
                exe_path = buf.value
            finally:
                kernel32.CloseHandle(hproc)
            if os.path.basename(exe_path).lower() != "cursor.exe":
                return True
            r = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
                return True
            w, h = r.right - r.left, r.bottom - r.top
            if w < 200 or h < 200:
                return True
            candidates.append((w * h, hwnd))
            return True

        user32.EnumWindows(_enum, 0)
        if not candidates:
            return None
        return int(max(candidates, key=lambda t: t[0])[1])

    def _cursor_foreground_hwnd_win32(self, hwnd: int) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        fg = user32.GetForegroundWindow()
        tid_tgt = user32.GetWindowThreadProcessId(hwnd, None)
        tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        if tid_fg and tid_tgt:
            user32.AttachThreadInput(tid_fg, tid_tgt, True)
        user32.SetForegroundWindow(hwnd)
        if tid_fg and tid_tgt:
            user32.AttachThreadInput(tid_fg, tid_tgt, False)

    def _cursor_send_f11_fullscreen_win32(self, hwnd: int) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        VK_F11 = 0x7A
        self._cursor_foreground_hwnd_win32(hwnd)
        user32.keybd_event(VK_F11, 0, 0, 0)
        user32.keybd_event(VK_F11, 0, KEYEVENTF_KEYUP, 0)

    def _focus_existing_cursor_window_win32(self) -> bool:
        if sys.platform != "win32":
            return False
        hwnd = self._cursor_largest_main_hwnd_win32()
        if hwnd is None:
            return False
        self._cursor_foreground_hwnd_win32(hwnd)
        return True

    def open_cursor_window(self) -> None:
        if not self.settings.CLAP_FOCUS_EXISTING_CURSOR and not self.settings.CLAP_OPEN_NEW_CURSOR:
            return
        exe = self._cursor_executable()
        if not exe:
            logger.warning("Could not find Cursor executable on path or LOCALAPPDATA.")
            return

        popen_kw: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            if self.settings.CLAP_FOCUS_EXISTING_CURSOR:
                focused = sys.platform == "win32" and self._focus_existing_cursor_window_win32()
                if not focused:
                    logger.info("Cursor not currently running, launching fresh instance.")
                    subprocess.Popen([exe], **popen_kw)
            if self.settings.CLAP_OPEN_NEW_CURSOR:
                subprocess.Popen([exe, "-n"], **popen_kw)
        except Exception as e:
            logger.error("Could not launch or focus Cursor: {}", e)
            return

        if sys.platform == "win32" and self.settings.CLAP_CURSOR_FULLSCREEN:
            time.sleep(0.6)
            hwnd = self._cursor_largest_main_hwnd_win32()
            if hwnd is not None:
                self._cursor_send_f11_fullscreen_win32(hwnd)
            else:
                logger.warning("Cursor fullscreen: no main window hwnd found to target F11.")
