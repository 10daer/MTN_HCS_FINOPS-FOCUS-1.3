"""
Standalone script to test IAM authentication against HCS ManageOne.

Uses curl (via subprocess) so it inherits system/VPN routing and SSL bypass
identically to running curl directly in the terminal.

Usage:
    python test_iam_auth.py
"""

import json
import subprocess
import sys

# ── Fill in your credentials ──────────────────────────────────────────
IAM_URL = "https://iam-apigateway-proxy.mtn.com/v3/auth/tokens"
USERNAME = ""           # IAM username, e.g. "finops_admin"
PASSWORD = ""           # IAM password
AUTH_DOMAIN = "mo_bss_admin"
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    if not USERNAME or not PASSWORD:
        print("ERROR: Set USERNAME and PASSWORD at the top of this script before running.")
        sys.exit(1)

    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "domain": {"name": AUTH_DOMAIN},
                        "name": USERNAME,
                        "password": PASSWORD,
                    }
                },
            },
            "scope": {"domain": {"name": AUTH_DOMAIN}},
        }
    }

    cmd = [
        "curl",
        "--insecure",
        "--silent",
        "--show-error",
        "--max-time", "30",
        "--request", "POST",
        "--url", IAM_URL,
        "--header", "Content-Type: application/json",
        "--header", "Accept: */*",
        "--data", json.dumps(body),
        "--dump-header", "-",
    ]

    print(f"POST {IAM_URL}")
    print(f"User: {USERNAME} | Domain: {AUTH_DOMAIN}\n")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"curl error:\n{result.stderr}")
        sys.exit(1)

    output = result.stdout

    # Split headers from body (separated by a blank line)
    header_section, _, body_section = output.partition("\r\n\r\n")
    if not body_section:
        header_section, _, body_section = output.partition("\n\n")

    # Print status line + token header
    for line in header_section.splitlines():
        if line.startswith("HTTP/") or line.lower().startswith("x-subject-token"):
            print(line)

    # Pretty-print JSON body
    print()
    try:
        parsed = json.loads(body_section)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(body_section)


if __name__ == "__main__":
    main()
