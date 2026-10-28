"""Run native Portal operator commands without sourcing secrets into a shell."""

import os
import sys
from pathlib import Path

# User-service installs keep settings in the home directory; setup-server.sh in /etc.
CANDIDATES = (
    Path.home() / ".config/vmportal/portal.env",
    Path("/etc/vmportal/portal.env"),
)


def run():
    private = next((path for path in CANDIDATES if path.is_file()), None)
    if private is None:
        raise SystemExit(
            "Service environment not found (run with sudo on a setup-server.sh install)"
        )
    from dotenv import dotenv_values

    # Values may be quoted; parse them exactly as the services do.
    os.environ.update(
        {
            key: value
            for key, value in dotenv_values(private, interpolate=False).items()
            if value is not None
        }
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.cli import main

    main()


if __name__ == "__main__":
    run()
