"""Parse session cookie set by ``pods/login_pod`` after successful login."""

from __future__ import annotations

from http.cookies import SimpleCookie

from solutions_service.auth.email_format import is_valid_email


def extract_email_from_cookie_header(
    cookie_header: str,
    *,
    cookie_name: str,
) -> str | None:
    if not cookie_header.strip():
        return None
    jar = SimpleCookie()
    jar.load(cookie_header)
    morsel = jar.get(cookie_name)
    if morsel is None:
        return None
    email = morsel.value.strip()
    if not is_valid_email(email):
        return None
    return email
