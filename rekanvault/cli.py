import argparse
import json
from pathlib import Path

from rekanvault.contracts.export import export_all_schemas


def main() -> None:
    parser = argparse.ArgumentParser(prog="rekanvault", description="RekanVault Knowledge Base & RAG Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # version
    subparsers.add_parser("version", help="Show RekanVault version")

    # health
    subparsers.add_parser("health", help="Check local component health")

    # export-schemas
    export_parser = subparsers.add_parser("export-schemas", help="Export canonical JSON and OpenAPI schemas")
    export_parser.add_argument(
        "--outdir", type=str, default="packages/contracts/schemas", help="Target output directory"
    )

    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan connector source")
    scan_parser.add_argument("--provider", type=str, choices=["google_drive", "notion"], required=True)
    scan_parser.add_argument("--source-id", type=str, required=True)

    args = parser.parse_args()

    if args.command == "version":
        print("RekanVault CLI v0.1.0")
    elif args.command == "health":
        print(json.dumps({"status": "ok", "version": "0.1.0", "component": "cli"}))
    elif args.command == "export-schemas":
        outpath = Path(args.outdir)
        export_all_schemas(outpath)
        print(f"Schema export complete: {outpath}")
    elif args.command == "scan":
        print(f"Scanning source '{args.source_id}' with provider '{args.provider}'...")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
