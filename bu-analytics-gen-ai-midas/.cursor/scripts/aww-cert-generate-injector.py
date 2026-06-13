#!/usr/bin/env python3
"""ACM helper: generate/import TLS certs, list ACM certs, or delete by index.

See ``--help`` for full flag reference and examples (this string is kept short;
the CLI epilog documents behavior in detail).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Fixed cache filename (under the OS temp directory). Overwritten on each ``--list-certs``.
CERT_LIST_CACHE = Path(tempfile.gettempdir()) / "midas-acm-certificate-index.json"

# Force line-buffered stdout/stderr so output appears immediately.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

DEFAULT_REGION = "us-east-1"
DEFAULT_VALIDITY_DAYS = 365
DEFAULT_KEY_BITS = 4096

# Conservative FQDN check for TLS DNS names (labels: letters, digits, hyphen).
_FQDN_RE = re.compile(
    r"(?!-)"  # no leading hyphen in first label
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"  # labels + dots
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)


def _validate_fqdn_for_tls(name: str) -> None:
    """Reject empty or obviously invalid hostnames for DNS SAN."""
    n = name.strip().lower()
    if not n or len(n) > 253:
        sys.exit(f"ERROR: Invalid DNS name (length or empty): {name!r}\n")
    if n.startswith(".") or n.endswith(".") or ".." in n:
        sys.exit(f"ERROR: Invalid DNS name (dots): {name!r}\n")
    if not _FQDN_RE.match(n):
        sys.exit(
            f"ERROR: DNS name must look like a hostname (letters, digits, hyphens; "
            f"dots between labels): {name!r}\n"
        )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        k = x.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def _repo_root() -> Path:
    """Repository root (parent of ``deploy/``)."""
    return Path(__file__).resolve().parents[3]


def _default_cert_dir() -> Path:
    return _repo_root() / "deploy" / "certs"


def _prompt_profile() -> Optional[str]:
    """Same behavior as ``aws-ssm-port-forward-all._prompt_profile``."""
    if not sys.stdin.isatty():
        return os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or None

    print("\nSelect an AWS CLI profile:")
    print("  1) midas-dev")
    print("  2) default  (AWS default credential chain)")
    print("  3) Enter your own profile name")
    print()

    while True:
        try:
            raw = input("Choice [1/2/3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit("Aborted.\n")

        if raw == "1":
            print("  Using profile: midas-dev\n")
            return "midas-dev"
        if raw == "2":
            print("  Using profile: default (AWS default credential chain)\n")
            return "default"
        if raw == "3":
            try:
                custom = input("  Profile name: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit("Aborted.\n")
            if not custom:
                print("  Profile name cannot be empty. Try again.")
                continue
            print(f"  Using profile: {custom}\n")
            return custom
        print("  Invalid choice – please enter 1, 2, or 3.")


def _prompt_line(label: str, default: str) -> str:
    """Return user input or ``default`` when the user presses Enter."""
    if not sys.stdin.isatty():
        return default
    try:
        raw = input(f"{label} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit("Aborted.\n")
    return raw if raw else default


def _prompt_optional(label: str, default: str = "") -> str:
    if not sys.stdin.isatty():
        return default
    try:
        return input(f"{label} (optional, Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit("Aborted.\n")


def _prompt_primary_dns(*, default: Optional[str]) -> str:
    """Ask for the primary DNS name (CN / SAN). ``default`` may be None (no bracket hint)."""
    dnorm = default.strip().lower() if default else ""

    if not sys.stdin.isatty():
        if dnorm:
            return dnorm
        sys.exit(
            "ERROR: Primary DNS name is required: pass --domain, or use a TTY with "
            "--prompt-domain.\n"
        )

    label = "Primary DNS name (Common Name / SAN)"
    while True:
        try:
            if dnorm:
                raw = input(f"{label} [{dnorm}]: ").strip().lower()
            else:
                raw = input(f"{label}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit("Aborted.\n")
        chosen = raw if raw else dnorm
        if chosen:
            return chosen
        print("  Domain cannot be empty.")


def _sanitize_filename(hostname: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", hostname.strip().lower())
    return s.strip("._-") or "cert"


def _check_openssl() -> str:
    exe = shutil.which("openssl")
    if not exe:
        sys.exit(
            "ERROR: openssl not found on PATH.\n"
            "Install OpenSSL or use a machine where the openssl CLI is available.\n"
        )
    return exe


def _check_aws_cli() -> str:
    aws_exe = shutil.which("aws")
    if not aws_exe:
        sys.stderr.write(
            "ERROR: AWS CLI not found on PATH.\n"
            "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html\n"
        )
        sys.exit(2)
    return aws_exe


def _ensure_credentials(aws_exe: str, region: str, profile: Optional[str]) -> None:
    sts_cmd = [aws_exe]
    if profile:
        sts_cmd += ["--profile", profile]
        os.environ["AWS_PROFILE"] = profile
    sts_cmd += [
        "sts",
        "get-caller-identity",
        "--region",
        region,
        "--output",
        "json",
    ]

    cred_check = subprocess.run(sts_cmd, capture_output=True, text=True)
    if cred_check.returncode != 0:
        print(
            "\nERROR: AWS credentials are invalid or expired.\n"
            f"Profile: {profile or '(default)'}\n"
            f"Detail:  {cred_check.stderr.strip()}\n"
        )
        try:
            ans = input("Run 'aws sso login' now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans not in ("n", "no"):
            login_cmd = [aws_exe, "sso", "login"]
            if profile:
                login_cmd += ["--profile", profile]
            subprocess.run(login_cmd)
            # Re-run STS and use THIS result for JSON parsing (not the failed run above).
            cred_check = subprocess.run(sts_cmd, capture_output=True, text=True)
            if cred_check.returncode != 0:
                sys.exit(
                    "\nERROR: Still unable to authenticate after sso login.\n"
                    f"Detail: {cred_check.stderr.strip()}\n"
                )
        else:
            sys.exit("Aborted.\n")

    raw = (cred_check.stdout or "").strip()
    if not raw:
        sys.exit(
            "\nERROR: sts get-caller-identity returned empty output.\n"
            f"stderr: {cred_check.stderr.strip()}\n"
        )
    try:
        identity = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(
            "\nERROR: Could not parse sts get-caller-identity output as JSON.\n"
            f"{e}\n"
            f"stdout (first 500 chars): {raw[:500]!r}\n"
            f"stderr: {cred_check.stderr.strip()!r}\n"
        )
    print(f"Identity: {identity.get('Arn', '?')}\n")


def _build_openssl_config(
    *,
    cn: str,
    sans: list[str],
    country: str,
    state: str,
    locality: str,
    org: str,
    ou: str,
    key_bits: int,
) -> str:
    """OpenSSL config: subject DN + SAN (deduped) + TLS server key usage (ALB/ACM-friendly)."""
    cn_l = cn.strip().lower()
    sans = _dedupe_preserve_order([cn_l] + [s for s in sans if s.strip()])

    dn_lines = [f"CN = {cn_l}"]
    if country:
        dn_lines.append(f"C = {country}")
    if state:
        dn_lines.append(f"ST = {state}")
    if locality:
        dn_lines.append(f"L = {locality}")
    if org:
        dn_lines.append(f"O = {org}")
    if ou:
        dn_lines.append(f"OU = {ou}")

    san_block = "\n".join(f"DNS.{i + 1} = {name}" for i, name in enumerate(sans))

    return f"""[req]
default_bits = {key_bits}
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
{chr(10).join(dn_lines)}

[v3_req]
basicConstraints = CA:FALSE
subjectKeyIdentifier = hash
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @san

[san]
{san_block}
"""


def _run_openssl(
    openssl: str,
    config_text: str,
    key_out: Path,
    cert_out: Path,
    days: int,
    key_bits: int,
) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".cnf",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(config_text)
        cfg_path = tmp.name
    try:
        cmd = [
            openssl,
            "req",
            "-x509",
            "-sha256",
            "-newkey",
            f"rsa:{key_bits}",
            "-nodes",
            "-keyout",
            str(key_out),
            "-out",
            str(cert_out),
            "-days",
            str(days),
            "-config",
            cfg_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(
                "ERROR: openssl req failed.\n"
                f"stderr: {proc.stderr.strip()}\n"
                f"stdout: {proc.stdout.strip()}\n"
            )
    finally:
        try:
            os.unlink(cfg_path)
        except OSError:
            pass


def _normalize_private_key_pkcs8_pem(openssl: str, key_path: Path) -> None:
    """Rewrite the private key to unencrypted PKCS#8 PEM (``BEGIN PRIVATE KEY``).

    ACM documents PKCS#1 and PKCS#8; PKCS#8 is the common interchange form.
    If ``openssl pkey`` fails (very old OpenSSL), the original file is left as-is.
    """
    tmp = key_path.with_name(key_path.name + ".pkcs8.tmp")
    proc = subprocess.run(
        [openssl, "pkey", "-in", str(key_path), "-out", str(tmp)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not tmp.is_file():
        print(
            "  (Note: could not normalize private key to PKCS#8; leaving traditional "
            "RSA PEM. ACM accepts PKCS#1 as well.)\n"
        )
        return
    try:
        tmp.replace(key_path)
    except OSError as e:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        sys.exit(f"ERROR: Failed to replace private key with PKCS#8 form: {e}\n")


def _x509_text(openssl: str, cert_path: Path) -> str:
    proc = subprocess.run(
        [openssl, "x509", "-noout", "-text", "-in", str(cert_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.exit(
            "ERROR: openssl x509 -text failed for certificate.\n"
            f"{proc.stderr.strip()}\n"
        )
    return proc.stdout


def _collect_dns_san_names(openssl: str, cert_path: Path) -> set[str]:
    """Return lowercased DNS names from Subject Alternative Name."""
    proc = subprocess.run(
        [
            openssl,
            "x509",
            "-noout",
            "-ext",
            "subjectAltName",
            "-in",
            str(cert_path),
        ],
        capture_output=True,
        text=True,
    )
    blob = proc.stdout if proc.returncode == 0 and proc.stdout.strip() else ""
    if not blob.strip():
        blob = _x509_text(openssl, cert_path)
    names: set[str] = set()
    for m in re.finditer(r"DNS:([^,\s]+)", blob.replace("\n", " ")):
        names.add(m.group(1).strip().lower())
    return names


def _key_modulus_md5(openssl: str, key_path: Path) -> str:
    for args in (
        [openssl, "pkey", "-noout", "-modulus", "-in", str(key_path)],
        [openssl, "rsa", "-noout", "-modulus", "-in", str(key_path)],
    ):
        proc = subprocess.run(args, capture_output=True, text=True)
        if proc.returncode == 0 and "Modulus=" in (proc.stdout or ""):
            mod = subprocess.run(
                [openssl, "md5"],
                input=proc.stdout,
                capture_output=True,
                text=True,
            )
            if mod.returncode == 0:
                return (mod.stdout or "").strip()
    sys.exit("ERROR: Could not read modulus from private key (openssl pkey/rsa).\n")


def _cert_modulus_md5(openssl: str, cert_path: Path) -> str:
    proc = subprocess.run(
        [openssl, "x509", "-noout", "-modulus", "-in", str(cert_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or "Modulus=" not in (proc.stdout or ""):
        sys.exit(
            "ERROR: Could not read modulus from certificate.\n"
            f"{proc.stderr.strip()}\n"
        )
    mod = subprocess.run(
        [openssl, "md5"],
        input=proc.stdout,
        capture_output=True,
        text=True,
    )
    if mod.returncode != 0:
        sys.exit("ERROR: openssl md5 failed for certificate modulus.\n")
    return (mod.stdout or "").strip()


def _validate_acm_alb_pem(
    openssl: str,
    cert_path: Path,
    key_path: Path,
    primary_dns: str,
    *,
    expected_rsa_bits: int,
) -> None:
    """Assert PEMs meet ACM import + ALB TLS listener expectations for RSA certs."""
    want = primary_dns.strip().lower()

    cert_pem = cert_path.read_text(encoding="utf-8", errors="replace")
    key_pem = key_path.read_text(encoding="utf-8", errors="replace")

    if "-----BEGIN CERTIFICATE-----" not in cert_pem:
        sys.exit("ERROR: Certificate file is not PEM (missing BEGIN CERTIFICATE).\n")
    if (
        "-----BEGIN ENCRYPTED PRIVATE KEY-----" in key_pem
        or "Proc-Type: 4,ENCRYPTED" in key_pem
    ):
        sys.exit(
            "ERROR: Private key appears encrypted. ACM import requires an unencrypted key; "
            "regenerate with openssl -nodes.\n"
        )
    if "-----BEGIN PRIVATE KEY-----" not in key_pem and "-----BEGIN RSA PRIVATE KEY-----" not in key_pem:
        sys.exit(
            "ERROR: Private key is not PEM PKCS#8 or PKCS#1 RSA (missing BEGIN PRIVATE KEY / "
            "BEGIN RSA PRIVATE KEY).\n"
        )

    chk = subprocess.run(
        [openssl, "x509", "-checkend", "0", "-noout", "-in", str(cert_path)],
        capture_output=True,
        text=True,
    )
    if chk.returncode != 0:
        sys.exit(
            "ERROR: Certificate is expired or not yet valid (openssl x509 -checkend).\n"
            f"{chk.stderr.strip()}\n"
        )

    text = _x509_text(openssl, cert_path)
    if not re.search(r"Signature Algorithm:\s*sha256", text, re.IGNORECASE):
        sys.exit(
            "ERROR: Expected SHA-256 signature algorithm (sha256WithRSAEncryption) "
            "for ACM/ALB compatibility.\n"
        )

    dns_names = _collect_dns_san_names(openssl, cert_path)
    if want not in dns_names:
        sys.exit(
            f"ERROR: Subject Alternative Name must include DNS:{want!r} for ALB SNI. "
            f"Found DNS names: {sorted(dns_names)!r}\n"
        )

    # RSA public key size (bits) from certificate (must match generated key)
    m = re.search(r"Public-Key:\s*\(\s*(\d+)\s+bit\s*\)", text)
    if m:
        bits = int(m.group(1))
        if bits < 2048:
            sys.exit(
                f"ERROR: RSA public key is {bits} bits; ACM requires at least 2048.\n"
            )
        if bits != expected_rsa_bits:
            sys.exit(
                f"ERROR: Certificate public key is {bits} bits but {expected_rsa_bits} was "
                f"requested (generation mismatch).\n"
            )
    else:
        sys.exit("ERROR: Could not determine RSA public key size from certificate.\n")

    cm = _cert_modulus_md5(openssl, cert_path)
    km = _key_modulus_md5(openssl, key_path)
    if cm != km:
        sys.exit(
            "ERROR: Certificate and private key do not match (modulus digest differs).\n"
        )

    print(
        "ACM/ALB validation OK: PEM X.509, unencrypted RSA key, SHA-256, "
        f"SAN includes DNS:{want}, RSA {expected_rsa_bits} bit, cert/key modulus match.\n"
    )


def _import_certificate(
    aws_exe: str,
    *,
    cert_path: Path,
    key_path: Path,
    chain_path: Optional[Path],
    region: str,
    profile: Optional[str],
    domain: str,
) -> str:
    cmd = [
        aws_exe,
        "acm",
        "import-certificate",
        "--certificate",
        f"fileb://{cert_path}",
        "--private-key",
        f"fileb://{key_path}",
        "--region",
        region,
        "--output",
        "json",
        "--tags",
        "Key=ManagedBy,Value=acm-generate-and-import-cert.py",
        f"Key=PrimaryDomain,Value={domain}",
    ]
    if chain_path is not None:
        cmd += ["--certificate-chain", f"fileb://{chain_path}"]
    if profile:
        cmd += ["--profile", profile]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(
            "ERROR: aws acm import-certificate failed.\n"
            f"stderr: {proc.stderr.strip()}\n"
            f"stdout: {proc.stdout.strip()}\n"
        )
    data = json.loads(proc.stdout)
    arn = data.get("CertificateArn")
    if not arn:
        sys.exit(f"ERROR: Unexpected ACM response (no CertificateArn): {proc.stdout}\n")
    return str(arn)


def _cert_id_from_arn(arn: str) -> str:
    """ACM certificate id (UUID) from full ARN."""
    return arn.rstrip().rsplit("/", 1)[-1]


def _aws_cmd_base(aws_exe: str, profile: Optional[str]) -> list[str]:
    cmd = [aws_exe]
    if profile:
        cmd += ["--profile", profile]
    return cmd


def _aws_acm_list_certificates_json(
    aws_exe: str, profile: Optional[str], region: str
) -> list[dict[str, Any]]:
    """Return all ``CertificateSummary`` objects (paginated via CLI)."""
    summaries: list[dict[str, Any]] = []
    token: Optional[str] = None
    while True:
        cmd = _aws_cmd_base(aws_exe, profile) + [
            "acm",
            "list-certificates",
            "--region",
            region,
            "--output",
            "json",
            "--max-items",
            "100",
        ]
        if token:
            cmd += ["--starting-token", token]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(
                "ERROR: aws acm list-certificates failed.\n"
                f"stderr: {proc.stderr.strip()}\n"
            )
        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: Invalid JSON from list-certificates: {e}\n{proc.stdout!r}\n")
        batch = data.get("CertificateSummaryList") or []
        summaries.extend(batch)
        token = data.get("NextToken")
        if not token:
            break
    return summaries


def _summaries_to_rows(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    filtered = [s for s in summaries if (s.get("CertificateArn") or "").strip()]
    rows: list[dict[str, Any]] = []
    for i, s in enumerate(filtered, start=1):
        arn = str(s.get("CertificateArn", "")).strip()
        rows.append(
            {
                "index": i,
                "certificate_id": _cert_id_from_arn(arn),
                "certificate_arn": arn,
                "type": s.get("Type") or "UNKNOWN",
                "key_algorithm": s.get("KeyAlgorithm") or "N/A",
                "in_use": bool(s.get("InUse", False)),
                "renewal_eligibility": s.get("RenewalEligibility") or "N/A",
            }
        )
    return rows


def _write_cert_list_cache(
    *,
    region: str,
    profile_label: Optional[str],
    rows: list[dict[str, Any]],
) -> None:
    """Replace the cache file so it always reflects the last ``--list-certs`` run."""
    if CERT_LIST_CACHE.exists():
        try:
            CERT_LIST_CACHE.unlink()
        except OSError as e:
            sys.exit(f"ERROR: Could not remove old cache {CERT_LIST_CACHE}: {e}\n")
    payload = {
        "version": 1,
        "region": region,
        "profile": profile_label or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "certificates": rows,
    }
    tmp = CERT_LIST_CACHE.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(CERT_LIST_CACHE)
    except OSError as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        sys.exit(f"ERROR: Could not write cache {CERT_LIST_CACHE}: {e}\n")


def _load_cert_list_cache() -> dict[str, Any]:
    if not CERT_LIST_CACHE.is_file():
        sys.exit(
            f"ERROR: No saved certificate list at {CERT_LIST_CACHE}.\n"
            "Run: python3 deploy/scripts/util/acm-generate-and-import-cert.py --list-certs ...\n"
        )
    try:
        return json.loads(CERT_LIST_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"ERROR: Could not read cache {CERT_LIST_CACHE}: {e}\n")


def _print_cert_list_table(rows: list[dict[str, Any]]) -> None:
    """Print index, cert id, type, key algorithm, in use, renewal only."""
    headers = ("Idx", "Cert ID", "Type", "Key algorithm", "In use", "Renewable")
    w_idx, w_id, w_type, w_key, w_use, w_ren = 4, 40, 14, 16, 8, 12
    line = (
        f"{headers[0]:>{w_idx}}  {headers[1]:<{w_id}}  {headers[2]:<{w_type}}  "
        f"{headers[3]:<{w_key}}  {headers[4]:<{w_use}}  {headers[5]:<{w_ren}}"
    )
    print(line)
    print("-" * len(line))
    for r in rows:
        cid = (r.get("certificate_id") or "")[: w_id - 2]
        print(
            f"{int(r['index']):>{w_idx}}  {cid:<{w_id}}  {str(r.get('type')):<{w_type}}  "
            f"{str(r.get('key_algorithm')):<{w_key}}  "
            f"{str(r.get('in_use')):<{w_use}}  {str(r.get('renewal_eligibility')):<{w_ren}}"
        )
    print(f"\nSaved index map: {CERT_LIST_CACHE}\n")


def _prompt_yes_no(prompt: str, default_yes: bool = True) -> bool:
    if not sys.stdin.isatty():
        sys.exit("ERROR: Confirmation requires a TTY (or answer non-interactively — not supported).\n")
    suf = "[Y/n]" if default_yes else "[y/N]"
    try:
        raw = input(f"{prompt} {suf}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def _delete_certificate(
    aws_exe: str, profile: Optional[str], region: str, certificate_arn: str
) -> None:
    cmd = _aws_cmd_base(aws_exe, profile) + [
        "acm",
        "delete-certificate",
        "--region",
        region,
        "--certificate-arn",
        certificate_arn,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(
            "ERROR: aws acm delete-certificate failed.\n"
            f"stderr: {proc.stderr.strip()}\n"
            f"stdout: {proc.stdout.strip()}\n"
        )


def _resolve_profile_and_region(args: argparse.Namespace) -> tuple[str, Optional[str]]:
    profile: Optional[str] = args.profile
    if profile is None:
        profile = _prompt_profile()
    if profile and profile.lower() == "default":
        profile = None
    region = args.region
    if args.ask_region:
        region = _prompt_line("AWS region", region)
    return region, profile


HELP_EPILOG = f"""
================================================================================
OVERVIEW
================================================================================
This tool does three separate jobs (pick one per run):

  1) DEFAULT — Generate a self-signed RSA TLS certificate with OpenSSL, validate
     it for ACM/ALB-style use, optionally import it into ACM (same region as
     ``--region``).

  2) ``--list-certs`` — List certificates in ACM for ``--region``, print a
     compact table (index, certificate id, type, key algorithm, in use,
     renewal eligibility), and write a JSON map of index → ARN to:

       {CERT_LIST_CACHE}

     Any previous file at that path is removed before writing so the cache
     always matches the **last** list run.

  3) ``--delete-cert`` — Delete **one** certificate from ACM after confirmation.
     Either pick from a **fresh** list (interactive index), or use
     ``--use-saved-cert-list`` with ``--cert-index`` to delete using the last
     cached list without re-prompting through a full table selection.

================================================================================
COMMON FLAGS
================================================================================
  -r, --region REGION     AWS region (default: {DEFAULT_REGION}). ACM is regional.
  --ask-region            Prompt for region (TTY only).
  --profile PROFILE       AWS CLI profile (omit for interactive picker: midas-dev /
                          default / custom — same pattern as aws-ssm-port-forward-all.py).

================================================================================
GENERATE + IMPORT (default mode)
================================================================================
  -d, --domain FQDN       Primary DNS name (CN + SAN). Prompted on TTY if omitted.
  --prompt-domain         Always prompt for primary DNS (``-d`` is default in brackets).
  --san DNS               Extra DNS SAN (repeatable).
  --days N                Validity days (default {DEFAULT_VALIDITY_DAYS}).
  --key-bits 2048|4096    RSA size (default {DEFAULT_KEY_BITS}).
  --skip-import           Only write PEM files under deploy/certs/; do not call ACM.
  --force                 Overwrite existing PEM files in the output directory.
  --no-validate           Skip post-generation modulus/SAN/SHA-256 checks.
  --no-normalize-key      Skip PKCS#8 rewrite of the private key.
  --certificate-chain PEM   Optional chain for ``import-certificate``.
  --output-dir DIR        PEM output directory (default: deploy/certs/ under repo root).

  Prerequisites: OpenSSL; for import: AWS CLI + ``acm:ImportCertificate`` + valid creds.

  Examples:
    python3 deploy/scripts/util/acm-generate-and-import-cert.py \\
        --prompt-domain --profile midas-dev --region us-east-1

    python3 deploy/scripts/util/acm-generate-and-import-cert.py \\
        --domain app.example.com --profile midas-dev --skip-import --force

================================================================================
LIST CERTIFICATES
================================================================================
  --list-certs            List ACM certificates; save index map to temp file (path above).

  Examples:
    python3 deploy/scripts/util/acm-generate-and-import-cert.py --list-certs --profile midas-dev

    python3 deploy/scripts/util/acm-generate-and-import-cert.py --list-certs -r us-east-1 \\
        --profile midas-dev

================================================================================
DELETE CERTIFICATE
================================================================================
  --delete-cert           Delete one ACM certificate after **Y/n** confirmation.

  Without ``--use-saved-cert-list``:
      Fetches the current list, prints the same columns as ``--list-certs``,
      asks you to type an index (1..N), then asks Y/n before calling
      ``aws acm delete-certificate``.

  With ``--use-saved-cert-list``:
      Reads ``{CERT_LIST_CACHE}`` (from the last ``--list-certs``), requires
      ``--cert-index N`` (or prompts for N on a TTY), checks ``--region`` matches
      the cache, shows the chosen row, then Y/n before delete.

  --cert-index N          1-based index (required for non-TTY when using saved list;
                          optional when using saved list on TTY).

  --use-saved-cert-list   Use cached index/ARN file instead of selecting from a
                          newly fetched list (still use with ``--delete-cert``).

  **Warning:** Deleting a cert that is attached to an ALB/listener will break TLS
  until you attach a different certificate.

  Examples:
    python3 deploy/scripts/util/acm-generate-and-import-cert.py --list-certs --profile midas-dev
    python3 deploy/scripts/util/acm-generate-and-import-cert.py --delete-cert --profile midas-dev

    python3 deploy/scripts/util/acm-generate-and-import-cert.py --delete-cert \\
        --use-saved-cert-list --cert-index 2 --profile midas-dev -r us-east-1

================================================================================
CREDENTIALS
================================================================================
If ``sts get-caller-identity`` fails (e.g. expired SSO), the script can offer to
run ``aws sso login`` for the chosen profile, then retry.
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Generate/import self-signed TLS certs to ACM, list ACM certificates, "
            "or delete a certificate by index (with JSON cache under the temp directory)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP_EPILOG,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--list-certs",
        action="store_true",
        help="List ACM certificates in --region; write index map to temp JSON cache.",
    )
    mode.add_argument(
        "--delete-cert",
        action="store_true",
        help="Delete one ACM certificate (interactive index or --use-saved-cert-list).",
    )
    p.add_argument(
        "-d",
        "--domain",
        default=None,
        metavar="FQDN",
        help=(
            "Primary DNS name (CN + SAN). When omitted and --prompt-domain is not used, "
            "you are prompted on a TTY; otherwise required for non-interactive runs."
        ),
    )
    p.add_argument(
        "--prompt-domain",
        "--prompt-name",
        action="store_true",
        dest="prompt_domain",
        help=(
            "Always prompt for the primary DNS name. If --domain is also set, it is "
            "shown as the default in brackets (press Enter to keep it)."
        ),
    )
    p.add_argument(
        "-r",
        "--region",
        default=DEFAULT_REGION,
        metavar="REGION",
        help=f"AWS region for ACM import (default: {DEFAULT_REGION}).",
    )
    p.add_argument(
        "--ask-region",
        action="store_true",
        help="Prompt for AWS region (defaults shown in brackets; TTY only).",
    )
    p.add_argument(
        "--profile",
        default=None,
        metavar="PROFILE",
        help=(
            "AWS CLI profile. When omitted, uses the same interactive picker as "
            "aws-ssm-port-forward-all.py (unless stdin is not a TTY — then "
            "$AWS_PROFILE / $AWS_DEFAULT_PROFILE)."
        ),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"Directory for PEM files (default: {_default_cert_dir()}).",
    )
    p.add_argument(
        "--san",
        action="append",
        default=[],
        metavar="DNS_NAME",
        help="Extra DNS subjectAlternativeName (repeatable).",
    )
    p.add_argument(
        "--certificate-chain",
        type=Path,
        default=None,
        metavar="PEM",
        help="Optional intermediate PEM chain file to pass to import-certificate.",
    )
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_VALIDITY_DAYS,
        metavar="N",
        help=f"Certificate validity in days (default: {DEFAULT_VALIDITY_DAYS}).",
    )
    p.add_argument(
        "--key-bits",
        type=int,
        default=DEFAULT_KEY_BITS,
        choices=(2048, 4096),
        help=f"RSA key size (default: {DEFAULT_KEY_BITS}).",
    )
    p.add_argument(
        "--skip-import",
        action="store_true",
        help="Only generate PEM files; do not call ACM.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing PEM files in the output directory.",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip post-generation checks (PEM/SAN/modulus/SHA-256). Not recommended.",
    )
    p.add_argument(
        "--no-normalize-key",
        action="store_true",
        help="Do not rewrite the private key to PKCS#8 PEM (BEGIN PRIVATE KEY).",
    )
    p.add_argument(
        "--cert-index",
        type=int,
        default=None,
        metavar="N",
        help=(
            "With --delete-cert: 1-based row index. Use with --use-saved-cert-list for "
            "non-interactive delete from the cache file, or with a fresh list when stdin "
            "is not a TTY. On a TTY may be omitted (you will be prompted)."
        ),
    )
    p.add_argument(
        "--use-saved-cert-list",
        action="store_true",
        help=(
            "With --delete-cert: read certificate ARN from the last --list-certs cache "
            f"({CERT_LIST_CACHE}) instead of choosing from a freshly printed list."
        ),
    )
    return p.parse_args()


def cmd_list_certs(args: argparse.Namespace) -> int:
    region, profile = _resolve_profile_and_region(args)
    aws_exe = _check_aws_cli()
    _ensure_credentials(aws_exe, region, profile)
    summaries = _aws_acm_list_certificates_json(aws_exe, profile, region)
    rows = _summaries_to_rows(summaries)
    _write_cert_list_cache(
        region=region,
        profile_label=profile or "",
        rows=rows,
    )
    if not rows:
        print("(No certificates in this region.)\n")
        return 0
    _print_cert_list_table(rows)
    return 0


def cmd_delete_cert(args: argparse.Namespace) -> int:
    region, profile = _resolve_profile_and_region(args)
    aws_exe = _check_aws_cli()
    _ensure_credentials(aws_exe, region, profile)

    if args.use_saved_cert_list:
        data = _load_cert_list_cache()
        cached_region = data.get("region") or ""
        if cached_region and cached_region != region:
            sys.exit(
                f"ERROR: Cache region is {cached_region!r} but --region is {region!r}.\n"
                f"Re-run --list-certs with matching --region, or pass -r {cached_region}\n"
            )
        rows = list(data.get("certificates") or [])
        if not rows:
            sys.exit(f"ERROR: Cache file {CERT_LIST_CACHE} has no certificates.\n")
        idx = args.cert_index
        if idx is None:
            if not sys.stdin.isatty():
                sys.exit(
                    "ERROR: --cert-index N is required with --use-saved-cert-list when stdin is not a TTY.\n"
                )
            _print_cert_list_table(rows)
            try:
                raw = input("Enter index to delete (from saved list): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit("Aborted.\n")
            try:
                idx = int(raw)
            except ValueError:
                sys.exit(f"ERROR: Invalid index: {raw!r}\n")
        chosen = next((r for r in rows if int(r.get("index", -1)) == idx), {})
        if not chosen:
            sys.exit(
                f"ERROR: No certificate with index {idx} in {CERT_LIST_CACHE} "
                f"(valid: 1..{len(rows)}).\n"
            )
    else:
        summaries = _aws_acm_list_certificates_json(aws_exe, profile, region)
        rows = _summaries_to_rows(summaries)
        _write_cert_list_cache(
            region=region,
            profile_label=profile or "",
            rows=rows,
        )
        if not rows:
            print("(No certificates in this region.)\n")
            return 0
        _print_cert_list_table(rows)
        idx = args.cert_index
        if idx is None:
            if not sys.stdin.isatty():
                sys.exit(
                    "ERROR: When stdin is not a TTY, pass --cert-index N with --delete-cert "
                    "(without --use-saved-cert-list, a fresh list was written to the cache file).\n"
                )
            try:
                raw = input("Enter index to delete (1..{}): ".format(len(rows))).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit("Aborted.\n")
            try:
                idx = int(raw)
            except ValueError:
                sys.exit(f"ERROR: Invalid index: {raw!r}\n")
        chosen = next((r for r in rows if int(r.get("index", -1)) == idx), {})
        if not chosen:
            sys.exit(f"ERROR: No certificate with index {idx} (valid: 1..{len(rows)}).\n")

    arn = chosen.get("certificate_arn") or ""
    if not arn:
        sys.exit("ERROR: Selected row has no CertificateArn.\n")

    print(
        "About to delete:\n"
        f"  Index:           {chosen.get('index')}\n"
        f"  Certificate ID: {chosen.get('certificate_id')}\n"
        f"  Type:            {chosen.get('type')}\n"
        f"  Key algorithm:   {chosen.get('key_algorithm')}\n"
        f"  In use:          {chosen.get('in_use')}\n"
        f"  Renewable:       {chosen.get('renewal_eligibility')}\n"
        f"  ARN:             {arn}\n"
    )
    if not _prompt_yes_no("Delete this certificate?", default_yes=False):
        print("Aborted (no changes).\n")
        return 0

    _delete_certificate(aws_exe, profile, region, arn)
    print("Deleted successfully.\n")
    return 0


def main() -> int:
    args = parse_args()

    if args.use_saved_cert_list and not args.delete_cert:
        sys.exit("ERROR: --use-saved-cert-list requires --delete-cert.\n")
    if args.cert_index is not None and not args.delete_cert:
        sys.exit("ERROR: --cert-index is only valid with --delete-cert.\n")

    if args.list_certs:
        return cmd_list_certs(args)
    if args.delete_cert:
        return cmd_delete_cert(args)

    openssl = _check_openssl()

    out_dir = args.output_dir if args.output_dir is not None else _default_cert_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    region, profile = _resolve_profile_and_region(args)

    domain_cli = args.domain.strip().lower() if args.domain else None
    if args.prompt_domain:
        domain = _prompt_primary_dns(default=domain_cli)
    elif not domain_cli:
        domain = _prompt_primary_dns(default=None)
    else:
        domain = domain_cli

    _validate_fqdn_for_tls(domain)

    sans = list(args.san)
    if sys.stdin.isatty():
        extra = _prompt_optional("Extra DNS SANs (comma-separated)")
        if extra:
            sans.extend(s.strip() for s in extra.split(",") if s.strip())

    tty = sys.stdin.isatty()
    if tty:
        days_s = _prompt_line("Validity (days)", str(args.days))
        bits_s = _prompt_line("RSA key bits (2048 or 4096)", str(args.key_bits))
        org = _prompt_line("Organization (O)", "Exlservice")
        ou = _prompt_line("Organizational unit (OU, optional)", "")
        country = _prompt_line("Country code (C, optional)", "US")
        state = _prompt_line("State or province (ST, optional)", "")
        locality = _prompt_line("Locality / city (L, optional)", "")
    else:
        days_s = str(args.days)
        bits_s = str(args.key_bits)
        org, ou, country, state, locality = "Exlservice", "", "US", "", ""

    try:
        days = int(days_s)
    except ValueError:
        sys.exit(f"ERROR: Invalid days: {days_s!r}\n")
    try:
        key_bits = int(bits_s)
    except ValueError:
        sys.exit(f"ERROR: Invalid key bits: {bits_s!r}\n")
    if key_bits not in (2048, 4096):
        sys.exit("ERROR: Key bits must be 2048 or 4096.\n")

    safe = _sanitize_filename(domain)
    key_path = out_dir / f"{safe}.key.pem"
    cert_path = out_dir / f"{safe}.cert.pem"

    if not args.force and (key_path.exists() or cert_path.exists()):
        sys.exit(
            f"ERROR: Refusing to overwrite existing files:\n  {key_path}\n  {cert_path}\n"
            "Use --force to replace them.\n"
        )

    cfg = _build_openssl_config(
        cn=domain,
        sans=[domain] + sans,
        country=country,
        state=state,
        locality=locality,
        org=org,
        ou=ou,
        key_bits=key_bits,
    )
    print(f"Writing:\n  {key_path}\n  {cert_path}\n")
    _run_openssl(openssl, cfg, key_path, cert_path, days, key_bits)

    if not args.no_normalize_key:
        _normalize_private_key_pkcs8_pem(openssl, key_path)

    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass

    if not args.no_validate:
        _validate_acm_alb_pem(
            openssl,
            cert_path,
            key_path,
            domain,
            expected_rsa_bits=key_bits,
        )
    else:
        print("Skipping ACM/ALB validation (--no-validate).\n")

    print("OpenSSL finished successfully.\n")

    if args.skip_import:
        print(
            "Skipping ACM import (--skip-import). Import manually when ready, for example:\n"
            f"  aws acm import-certificate \\\n"
            f"    --certificate fileb://{cert_path} \\\n"
            f"    --private-key fileb://{key_path} \\\n"
            f"    --region {region}"
        )
        if args.certificate_chain:
            print(f"    --certificate-chain fileb://{args.certificate_chain}")
        if profile:
            print(f"    --profile {profile}")
        print()
        return 0

    aws_exe = _check_aws_cli()
    _ensure_credentials(aws_exe, region, profile)
    arn = _import_certificate(
        aws_exe,
        cert_path=cert_path,
        key_path=key_path,
        chain_path=args.certificate_chain,
        region=region,
        profile=profile,
        domain=domain,
    )
    print(f"ACM certificate ARN:\n  {arn}\n")
    print(
        "Notes:\n"
        "  * Imported certificates are not auto-renewed by ACM; plan rotation before expiry.\n"
        "  * Corporate browsers may warn on self-signed certs unless the OS trusts this cert "
        "or you use a publicly trusted ACM-issued cert instead.\n"
        f"  * Use this ARN on an ALB listener in the same region ({region}).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())