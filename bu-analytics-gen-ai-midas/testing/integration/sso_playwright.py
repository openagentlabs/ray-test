"""Browser-based token extraction for MIDAS integration tests.

Three strategies (tried in order)
----------------------------------
1. CDP connect  — connects to your already-open Chrome/Edge (no login needed).
   Start Chrome with: --remote-debugging-port=9222
   Or use the helper script:  python testing/integration/launch_chrome_cdp.py

2. Interactive  — opens a new Chromium window, navigates to the SPA, and waits
   for you to log in manually.

3. Automated    — fills the SSO form automatically (requires sso_email + sso_password).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from testing.api_client.credentials import MidasSessionCredentials

logger = logging.getLogger("midas.integration.playwright_sso")

_CDP_PORT: int = 9222
_SPA_ORIGIN: str = "https://exldecision-ai-dev.exlservice.com"
_LS_TOKEN_KEY: str = "auth_token"
_LS_SESSION_KEY: str = "midas_session_id"


class PlaywrightSsoOptions(BaseModel):
    """Options for token acquisition via Playwright."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    spa_origin: str = Field(
        _SPA_ORIGIN,
        min_length=8,
        description="SPA origin, e.g. https://exldecision-ai-dev.exlservice.com",
    )
    interactive: bool = Field(
        True,
        description="Open a new browser window and wait for manual login.",
    )
    cdp_port: int = Field(
        _CDP_PORT,
        description="Chrome remote-debugging port (strategy 1).",
    )
    slow_mo_ms: int = Field(0, ge=0, le=5000)
    navigation_timeout_ms: int = Field(300_000, ge=5_000, le=600_000)
    sso_email: Optional[str] = Field(None)
    sso_password: Optional[str] = Field(None)


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------


def obtain_credentials_via_playwright(opts: PlaywrightSsoOptions) -> MidasSessionCredentials:
    """Try CDP connect first, then fall back to interactive browser login."""
    _assert_playwright_installed()

    # Strategy 1: read token from an already-open browser
    cdp_result = _try_cdp_connect(opts)
    if cdp_result is not None:
        return cdp_result

    # Strategy 2 / 3: open a new browser
    return _login_via_new_browser(opts)


# ------------------------------------------------------------------
# Strategy 1 — CDP connect to existing browser
# ------------------------------------------------------------------


def _try_cdp_connect(opts: PlaywrightSsoOptions) -> Optional[MidasSessionCredentials]:
    """
    Connect to an already-open Chrome/Edge browser via CDP remote debugging.

    Returns credentials if the MIDAS tab is found with a valid token,
    otherwise returns None so the caller can fall back to interactive mode.
    """
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(
                f"http://localhost:{opts.cdp_port}",
                timeout=3_000,
            )
            creds = _scan_browser_for_token(browser, opts.spa_origin)
            browser.close()
            if creds is not None:
                logger.info("Token found in existing browser via CDP.")
                return creds
            logger.info("CDP connected but no MIDAS token found — will open new browser.")
            return None
    except Exception as exc:
        logger.info("CDP connect failed (%s) — will open new browser.", exc)
        return None


def _scan_browser_for_token(
    browser: object,
    spa_origin: str,
) -> Optional[MidasSessionCredentials]:
    """Scan all open tabs for a MIDAS auth_token in localStorage."""
    from playwright.sync_api import Browser

    assert isinstance(browser, Browser)
    for context in browser.contexts:
        for page in context.pages:
            try:
                if not page.url.startswith(spa_origin):
                    continue
                token = page.evaluate(f"() => localStorage.getItem('{_LS_TOKEN_KEY}')")
                if not isinstance(token, str) or len(token) < 20:
                    continue
                sid = page.evaluate(f"() => localStorage.getItem('{_LS_SESSION_KEY}')")
                cookies_raw = context.cookies()
                cookies: list[dict[str, object]] = [dict(c) for c in cookies_raw]
                cookie_header = MidasSessionCredentials.cookie_header_from_playwright_cookies(cookies)
                return MidasSessionCredentials(
                    access_token=token,
                    session_id=sid if isinstance(sid, str) and sid else None,
                    cookie_header_value=cookie_header if cookie_header else None,
                )
            except Exception:
                continue
    return None


# ------------------------------------------------------------------
# Strategy 2 / 3 — new browser window
# ------------------------------------------------------------------


def _login_via_new_browser(opts: PlaywrightSsoOptions) -> MidasSessionCredentials:
    """Open a new Chromium window and either wait for manual login or auto-fill."""
    from playwright.sync_api import sync_playwright

    origin = opts.spa_origin.strip().rstrip("/")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            slow_mo=opts.slow_mo_ms,
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(opts.navigation_timeout_ms)

        logger.info("Opening browser at %s", origin)
        page.goto(f"{origin}/", wait_until="domcontentloaded")

        if opts.sso_email and opts.sso_password:
            _run_automated_mode(page, opts)
        else:
            _run_interactive_mode(page, opts.navigation_timeout_ms, origin)

        token = page.evaluate(f"() => localStorage.getItem('{_LS_TOKEN_KEY}')")
        sid = page.evaluate(f"() => localStorage.getItem('{_LS_SESSION_KEY}')")

        if not isinstance(token, str) or len(token) < 20:
            browser.close()
            raise RuntimeError(
                "auth_token missing or too short after login. "
                "Make sure you completed the SSO flow and the MIDAS dashboard loaded."
            )

        cookies_raw = context.cookies()
        cookies = [dict(c) for c in cookies_raw]
        cookie_header = MidasSessionCredentials.cookie_header_from_playwright_cookies(cookies)
        context.close()
        browser.close()

    logger.info("Login successful — token acquired.")
    return MidasSessionCredentials(
        access_token=token,
        session_id=sid if isinstance(sid, str) and sid else None,
        cookie_header_value=cookie_header if cookie_header else None,
    )


# ------------------------------------------------------------------
# Interactive mode
# ------------------------------------------------------------------


def _run_interactive_mode(page: object, timeout_ms: int, spa_origin: str) -> None:
    """Click Sign In on the SPA, print a prompt, then poll for the token."""
    from playwright.sync_api import Page

    assert isinstance(page, Page)

    try:
        sign_in_btn = page.get_by_role("button", name=re.compile(r"sign\s*in", re.I))
        sign_in_btn.first.wait_for(state="visible", timeout=15_000)
        sign_in_btn.first.click()
        logger.info("Clicked Sign In button")
    except Exception:
        logger.info("Sign In button not found — waiting for manual navigation")

    print(
        "\n"
        "╔══════════════════════════════════════════════════════════╗\n"
        "║         MIDAS — Complete your SSO Login                  ║\n"
        "╠══════════════════════════════════════════════════════════╣\n"
        "║  A browser window has opened.                            ║\n"
        "║                                                          ║\n"
        "║  Log in with your corporate SSO credentials.             ║\n"
        "║  Wait until the MIDAS dashboard fully loads.             ║\n"
        "║                                                          ║\n"
        "║  pytest continues automatically once you are logged in.  ║\n"
        f"║  (timeout: {timeout_ms // 1000}s)                                     ║\n"
        "╚══════════════════════════════════════════════════════════╝\n",
        flush=True,
    )

    _poll_for_auth_token(page, spa_origin, timeout_ms)
    print("  ✓ Login detected — closing browser and starting tests...\n", flush=True)


# ------------------------------------------------------------------
# Automated mode
# ------------------------------------------------------------------


def _run_automated_mode(page: object, opts: PlaywrightSsoOptions) -> None:
    """Click Sign In and auto-fill the Microsoft login form."""
    from playwright.sync_api import Page

    assert isinstance(page, Page)

    deadline = time.monotonic() + opts.navigation_timeout_ms / 1000.0

    page.get_by_role("button", name=re.compile(r"sign\s*in", re.I)).click()
    _wait_for_microsoft_or_cognito(page, deadline)

    email_box = page.locator('input[type="email"], input[name="loginfmt"], #i0116').first
    email_box.wait_for(state="visible", timeout=_remaining_ms(deadline))
    email_box.fill(opts.sso_email or "")

    for label in ("Next", "Sign in"):
        btn = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
        if btn.count() > 0:
            btn.first.click()
            break

    password_box = page.locator('input[type="password"], input[name="passwd"], #i0118').first
    password_box.wait_for(state="visible", timeout=_remaining_ms(deadline))
    password_box.fill(opts.sso_password or "")

    sign_btn = page.get_by_role("button", name=re.compile(r"sign\s*in", re.I))
    if sign_btn.count() > 0:
        sign_btn.first.click()
    else:
        page.locator('input[type="submit"], #idSIButton9').first.click()

    _dismiss_stay_signed_in(page)
    _poll_for_auth_token(page, opts.spa_origin.strip().rstrip("/"), _remaining_ms(deadline))


# ------------------------------------------------------------------
# Token polling (robust across cross-origin redirects)
# ------------------------------------------------------------------


def _poll_for_auth_token(page: object, spa_origin: str, timeout_ms: int) -> None:
    """Poll every second until auth_token appears in localStorage on the SPA page."""
    from playwright.sync_api import Page

    assert isinstance(page, Page)
    deadline = time.monotonic() + timeout_ms / 1000.0

    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            if spa_origin and not page.url.startswith(spa_origin):
                continue
            token = page.evaluate(f"() => localStorage.getItem('{_LS_TOKEN_KEY}')")
            if isinstance(token, str) and len(token) >= 20:
                return
        except Exception:
            continue

    raise RuntimeError(
        f"Timed out after {timeout_ms // 1000}s waiting for auth_token. "
        "Make sure you completed the SSO flow and the MIDAS dashboard loaded."
    )


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _assert_playwright_installed() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. "
            "Run: pip install -r testing/requirements-integration.txt "
            "&& python -m playwright install chromium"
        ) from exc


def _wait_for_microsoft_or_cognito(page: object, deadline: float) -> None:
    from playwright.sync_api import Page

    assert isinstance(page, Page)
    page.wait_for_function(
        "() => { const h = location.hostname; "
        "return h.includes('amazonaws.com') || h.includes('microsoft') || h.includes('login.'); }",
        timeout=_remaining_ms(deadline),
    )


def _dismiss_stay_signed_in(page: object) -> None:
    from playwright.sync_api import Page

    assert isinstance(page, Page)
    try:
        yes = page.get_by_role("button", name=re.compile(r"yes|accept", re.I))
        if yes.count() > 0:
            yes.first.click(timeout=8_000)
            return
    except Exception:
        pass
    try:
        page.locator("#idSIButton9").first.click(timeout=5_000)
    except Exception:
        pass


def _remaining_ms(deadline: float) -> int:
    return max(5_000, int((deadline - time.monotonic()) * 1000))
