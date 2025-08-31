import socket
from typing import Optional

import aiohttp
import ssl as sslmod


def ipv4_connector(ssl: Optional[bool | aiohttp.Fingerprint | sslmod.SSLContext] = None):
    """
    Create an aiohttp TCPConnector that restricts address family to IPv4.

    The `ssl` parameter mirrors aiohttp.TCPConnector's `ssl` argument.
    """
    return aiohttp.TCPConnector(family=socket.AF_INET, ssl=ssl)


def create_session(
    *,
    force_ipv4: bool,
    timeout: Optional[aiohttp.ClientTimeout] = None,
    trust_env: bool = True,
    ssl: Optional[bool | aiohttp.Fingerprint | sslmod.SSLContext] = None,
) -> aiohttp.ClientSession:
    """
    Return an aiohttp.ClientSession. If `force_ipv4` is True, the session uses an
    IPv4-only TCPConnector; otherwise it uses the default connector.
    """
    connector = ipv4_connector(ssl=ssl) if force_ipv4 else None
    return aiohttp.ClientSession(timeout=timeout, trust_env=trust_env, connector=connector)
