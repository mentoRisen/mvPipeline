"""Upload a file to the public FTP and print its public URL.

Usage:
    python scripts/ftpupload.py <relative_path>

Example:
    python scripts/ftpupload.py images/output.png
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.ftpupload import uploadToPublic  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ftpupload.py <relative_path>", file=sys.stderr)
        sys.exit(1)

    relative_path = sys.argv[1]

    try:
        public_url = uploadToPublic(relative_path)
        print(public_url)
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during FTP upload: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

