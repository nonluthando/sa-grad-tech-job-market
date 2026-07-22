"""Command-line entry point for Milestone 2 dataset construction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.transformation.dataset import build_dataset, write_dataset_outputs
from src.transformation.snapshots import SnapshotReadError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the canonical jobs Parquet dataset from raw snapshots."
    )
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def print_summary(result: object, parquet_path: Path, quality_path: Path) -> None:
    quality_report = result.quality_report
    print("\nCanonical dataset build summary")
    print("=" * 72)
    print(f"Raw snapshots:          {quality_report['raw_snapshot_count']}")
    print(f"Raw job observations:   {quality_report['raw_job_observation_count']}")
    print(f"Canonical jobs:         {quality_report['canonical_job_count']}")
    print(f"Duplicate observations: {quality_report['duplicate_observations_removed']}")
    print(f"South African jobs:     {quality_report['south_africa_job_count']}")
    print(f"Technology jobs:        {quality_report['technology_job_count']}")
    print(f"Target-market jobs:     {quality_report['target_market_job_count']}")
    print(f"\nDataset:        {parquet_path}")
    print(f"Quality report: {quality_path}")


def main() -> int:
    args = parse_args()
    try:
        result = build_dataset(args.raw_root)
        parquet_path, quality_path = write_dataset_outputs(
            result,
            args.output_root,
        )
    except (SnapshotReadError, ValueError, OSError, RuntimeError) as error:
        print(f"Dataset build failed: {error}", file=sys.stderr)
        return 1

    print_summary(result, parquet_path, quality_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
