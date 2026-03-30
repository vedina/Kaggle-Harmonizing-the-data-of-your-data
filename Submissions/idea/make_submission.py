# post_cli.py

import argparse
from pathlib import Path


def process(
    input_dir: Path,
    output_dir: Path,
    sample_submission: Path,
    normalisation: bool = True,
    merge=None,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Input dir: {input_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Sample submission: {sample_submission}")
    print(f"Normalisation: {normalisation}")
    print(f"Merge: {merge}")

    # 👉 TODO: replace with real logic

    # Example: iterate input files
    for f in input_dir.glob("*.tsv"):
        out_file = output_dir / f.name

        with open(f, "r", encoding="utf-8") as fin:
            lines = fin.readlines()

        if normalisation:
            lines = [line.strip() + "\n" for line in lines]

        with open(out_file, "w", encoding="utf-8") as fout:
            fout.writelines(lines)

    print("Done.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Post-process SDRF pipeline outputs"
    )

    # ✅ required
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Folder with outputs from sdrf_pipeline.main_fill",
    )

    # ✅ optional with default
    parser.add_argument(
        "--sample-submission",
        type=Path,
        default=Path("SampleSubmission.csv"),
        help="Sample submission file (default: ..//..//data//SampleSubmission.csv)",
    )

    # ✅ boolean flag (default True → allow disabling)
    parser.add_argument(
        "--no-normalisation",
        action="store_true",
        help="Disable normalisation (enabled by default)",
    )

    # ✅ required output
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Output folder",
    )

    # ✅ flexible merge input
    parser.add_argument(
        "--merge",
        type=str,
        default=None,
        help="Path to file to another submission.csv to merge with (optional)",
    )

    args = parser.parse_args(argv)

    normalisation = not args.no_normalisation

    process(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        sample_submission=args.sample_submission,
        normalisation=normalisation,
        merge=args.merge,
    )


if __name__ == "__main__":
    main()