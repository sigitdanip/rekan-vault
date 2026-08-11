"""
Scan the pilot Notion root page and dump a content inventory.

Read-only — does NOT write to Postgres or Qdrant.
Outputs page titles, block counts, and content previews to stdout
so we can author golden questions against real content.

Usage:  python scratch/scan_notion_inventory.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

# Ensure repo root is on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import httpx
from apps.api.config import settings
from rekanvault.sources.notion import NotionConnector


async def main() -> None:
    token = settings.RV_NOTION_TOKEN
    page_id = settings.RV_NOTION_PAGE_ID

    if not token or not page_id:
        print("ERROR: RV_NOTION_TOKEN and RV_NOTION_PAGE_ID must be set in .env")
        sys.exit(1)

    print(f"Scanning Notion root page: {page_id} (Sulaiman OS)")
    print(f"API version: {settings.RV_NOTION_API_VERSION}")
    print()

    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.RV_NOTION_API_TIMEOUT_SECONDS)) as client:
        connector = NotionConnector(
            source_id="inventory-scan",
            config={"root_page_id": page_id},
            client=client,
            token=token,
        )

        documents = await connector.scan()

    print(f"Found {len(documents)} pages/databases\n")

    total_blocks = 0
    block_type_counts: Counter[str] = Counter()
    page_entries: list[dict] = []

    for doc in documents:
        version = next(
            (v for v in doc.versions if v.version_id == doc.active_version_id),
            None,
        )
        blocks = version.blocks if version else []
        block_count = len(blocks)
        total_blocks += block_count

        for b in blocks:
            block_type_counts[b.block_type] += 1

        entry = {
            "title": doc.title,
            "page_id": doc.locator.native_id,
            "uri": doc.locator.uri,
            "block_count": block_count,
            "content_preview": " ".join(b.content for b in blocks if b.content)[:200],
            "block_types": list(set(b.block_type for b in blocks)),
        }
        page_entries.append(entry)

        print(f"  {doc.title}")
        print(f"    id:    {doc.locator.native_id}")
        print(f"    uri:   {doc.locator.uri}")
        print(f"    blocks: {block_count}")
        print(f"    types:  {', '.join(sorted(set(b.block_type for b in blocks)))}")
        preview = " ".join(b.content for b in blocks if b.content)[:150]
        if preview:
            print(f"    preview: {preview}...")
        print()

    print("--- Summary ---")
    print(f"Total pages:          {len(documents)}")
    print(f"Total blocks:         {total_blocks}")
    print(f"Block type breakdown:  {dict(block_type_counts.most_common())}")

    # Also dump JSON for programmatic use.
    out_path = Path("/tmp/notion_inventory.json")
    out_path.write_text(json.dumps(page_entries, indent=2, ensure_ascii=False))
    print(f"\nFull JSON inventory: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
