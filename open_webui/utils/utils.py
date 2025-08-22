"""
Compatibility utility module.

This module re-exports auth-related helpers that some routers import from
`open_webui.utils.utils`. Upstream code in this repository keeps these
helpers in `open_webui.utils.auth`. Creating this shim avoids import errors
without touching multiple call sites.
"""

from open_webui.utils.auth import (
    decode_token,
    create_api_key,
    create_token,
    get_admin_user,
    get_verified_user,
    get_current_user,
    get_password_hash,
    get_http_authorization_cred,
)

__all__ = [
    "decode_token",
    "create_api_key",
    "create_token",
    "get_admin_user",
    "get_verified_user",
    "get_current_user",
    "get_password_hash",
    "get_http_authorization_cred",
]
