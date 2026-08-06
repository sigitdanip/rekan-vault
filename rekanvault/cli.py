import argparse
import asyncio
import json
from pathlib import Path

from apps.api.config import settings
from rekanvault.contracts.export import export_all_schemas
from rekanvault.storage.qdrant import QdrantStore


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

    # qdrant
    qdrant_parser = subparsers.add_parser("qdrant", help="Qdrant index operations")
    qdrant_sub = qdrant_parser.add_subparsers(dest="qdrant_command", help="Qdrant subcommands")
    qdrant_sub.add_parser("rebuild", help="Drop and recreate the Qdrant collection")

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
    elif args.command == "qdrant" and args.qdrant_command == "rebuild":
        asyncio.run(_qdrant_rebuild())
    else:
        parser.print_help()


async def _qdrant_rebuild() -> None:
    store = QdrantStore(settings)
    collection = store.collection_name
    print(f"Dropping collection {collection}...")
    print("Recreating collection...")
    await store.rebuild_from_postgres()
    print("Rebuild complete.")


if __name__ == "__main__":
    main()
