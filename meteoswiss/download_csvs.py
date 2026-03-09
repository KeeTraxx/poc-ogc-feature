#!/usr/bin/env python3
"""Download all CSV assets from a MeteoSwiss OGD STAC item."""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

STAC_BASE = "https://data.geo.admin.ch/api/stac/v1"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)


def main():
    parser = argparse.ArgumentParser(
        description="Download all CSV assets from a MeteoSwiss STAC item."
    )
    parser.add_argument(
        "item_id",
        nargs="?",
        default="20260308-ch",
        help="STAC item ID (default: 20260308-ch)",
    )
    parser.add_argument(
        "--collection",
        default="ch.meteoschweiz.ogd-local-forecasting",
        help="STAC collection ID",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=str(Path(__file__).parent / "data"),
        help="Directory to save CSV files (default: <script_dir>/data)",
    )
    args = parser.parse_args()

    item_url = f"{STAC_BASE}/collections/{args.collection}/items/{args.item_id}"
    print(f"Fetching item metadata: {item_url}")
    item = fetch_json(item_url)

    assets = item.get("assets", {})
    csv_assets = {k: v for k, v in assets.items() if k.endswith(".csv")}

    if not csv_assets:
        print("No CSV assets found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(csv_assets)} CSV assets.")
    output_dir = Path(args.output_dir)

    for i, (name, asset) in enumerate(csv_assets.items(), 1):
        href = asset["href"]
        dest = output_dir / name
        if dest.exists():
            print(f"[{i}/{len(csv_assets)}] Skipping (exists): {name}")
            continue
        print(f"[{i}/{len(csv_assets)}] Downloading: {name}")
        download_file(href, dest)

    print("Done.")


if __name__ == "__main__":
    main()
