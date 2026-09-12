"""
mDNS / Zeroconf Local Network Auto-Discovery Service.
Advertises JARVIS AI OS on the local network as '_jarvis._tcp.local.' so mobile
companions and Flutter clients discover the desktop IP without manual configuration.
"""

import socket
import asyncio
from typing import Dict, Any, Optional
from loguru import logger


class ZeroConfDiscoveryService:
    """Manages local network mDNS / DNS-SD broadcast for JARVIS Desktop."""

    SERVICE_TYPE = "_jarvis._tcp.local."

    def __init__(self, port: int = 8000, name: str = "JARVIS AI OS") -> None:
        self.port = port
        self.name = name
        self._azc: Optional[Any] = None
        self._service_info: Optional[Any] = None
        self._is_active = False

    def _get_local_ip(self) -> str:
        """Finds the primary local LAN IP address."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    async def start_async(self) -> bool:
        """Asynchronously starts mDNS broadcasting on the local subnet."""
        if self._is_active:
            return True

        try:
            try:
                from zeroconf import ServiceInfo
                from zeroconf.asyncio import AsyncZeroconf
            except ImportError:
                logger.warning("zeroconf package not installed — local mDNS discovery disabled.")
                return False

            local_ip = self._get_local_ip()
            hostname = socket.gethostname()
            service_name = f"{self.name} ({hostname}).{self.SERVICE_TYPE}"

            properties = {
                "version": "2.0.0",
                "api_base": "/api/v1",
                "ws_endpoint": "/api/v1/mobile/ws",
                "hostname": hostname,
                "platform": "windows",
            }

            self._service_info = ServiceInfo(
                type_=self.SERVICE_TYPE,
                name=service_name,
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties=properties,
                server=f"{hostname.lower()}.local.",
            )

            self._azc = AsyncZeroconf()
            await self._azc.async_register_service(self._service_info)
            self._is_active = True
            logger.info("✓ Zeroconf: Advertising '{}' at {}:{} on local LAN", service_name, local_ip, self.port)
            return True

        except Exception as e:
            logger.error("✗ Zeroconf advertisement failed: {}", e)
            self._is_active = False
            return False

    async def stop_async(self) -> None:
        """Asynchronously stops mDNS broadcasting and unregisters service cleanly."""
        if not self._is_active or not self._azc:
            return

        try:
            if self._service_info:
                await self._azc.async_unregister_service(self._service_info)
            await self._azc.async_close()
            self._azc = None
            self._service_info = None
            self._is_active = False
            logger.info("Zeroconf: Service advertisement unregistered and stopped.")
        except Exception as e:
            logger.warning("Zeroconf stop warning: {}", e)

    def start(self) -> bool:
        """Synchronous wrapper for starting mDNS advertisement."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = loop.create_task(self.start_async())
                self._is_active = True
                return True
            else:
                return loop.run_until_complete(self.start_async())
        except Exception as e:
            logger.error("Zeroconf start failed: {}", e)
            return False

    def stop(self) -> None:
        """Synchronous wrapper for stopping mDNS advertisement."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.stop_async())
            else:
                loop.run_until_complete(self.stop_async())
        except Exception as e:
            logger.warning("Zeroconf stop failed: {}", e)

    @property
    def is_advertising(self) -> bool:
        return self._is_active

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self._is_active,
            "service_type": self.SERVICE_TYPE,
            "port": self.port,
            "local_ip": self._get_local_ip() if self._is_active else None,
        }


zeroconf_service = ZeroConfDiscoveryService()
