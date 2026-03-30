# post_cli.py

import argparse
from pathlib import Path
import pandas as pd
import logging
import sys
from sdrf_pipelines.ols.ols import OLS_AVAILABLE

from cv_map import build_cv_normaliser, normalise_submission

DEFAULT_SAMPLE = Path("..") / ".." / "data" / "SampleSubmission.csv"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def sanity_check(combined_df):
    # defaults, mandatory for proteomics
    mandatory_col = "Characteristics[CleavageAgent]"
    combined_df.loc[combined_df[mandatory_col] == "Not Applicable", mandatory_col] = "AC=MS:1001251; NT=Trypsin"
    mandatory_col = "Comment[AcquisitionMethod]"
    combined_df.loc[combined_df[mandatory_col] == "Not Applicable", mandatory_col] = "DDA"


def combine(sdrf_folder: Path = None, 
            output_file: Path = None,
            cols_order=None, pxds=None):

    # --- iterate SDRF CSVs ---
    all_dfs = []
    # we want them same order as in the sample submission
    for pxd in pxds:
        # Extract PXD from filename
        f = sdrf_folder / f"{pxd}_PubText.sdrf.csv"
        df = pd.read_csv(f)
        try:
            df["PXD"] = pxd
            all_dfs.append(df)
        except Exception as err:
            logging.error(err)

    # --- concatenate all files ---
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # --- ensure all sample columns exist ---
    for c in cols_order:
        if c not in combined_df.columns:
            combined_df[c] = pd.NA
    
    # --- assign consecutive IDs ---
    if "ID" in cols_order:
        combined_df["ID"] = range(1, len(combined_df) + 1)
    
    # --- keep only columns from sample CSV and in order ---
    combined_df = combined_df[cols_order]
    # no idea, but this is in SampleSubmission
    combined_df['Usage'] = ['Public' if i % 2 == 0 else 'Private' for i in range(len(combined_df))]
    combined_df = combined_df.replace('not applicable', 'Not Applicable')
    sanity_check(combined_df)
    
    # ---  save final combined CSV ---
    combined_df.to_csv(output_file, index=False)
    return combined_df


def process(
    sdrf_dir: Path,
    output_file: Path,
    sample_submission: Path,
    normalisation: bool = True,
    merge=None,
):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Input dir: {sdrf_dir}")
    print(f"Output submission file: {output_file}")
    print(f"Sample submission: {sample_submission}")
    print(f"Normalisation: {normalisation}")    
    if normalisation:
        cv_normalizer = build_cv_normaliser(use_ols=True) 
        if not OLS_AVAILABLE:
            logging.warning(f"OLS not available, normalisation will be incomplete!")
    print(f"Merge: {merge}")

    # 👉 TODO: replace with real logic
     
    submission = None 
    sample_df = pd.read_csv(sample_submission)
    file_not_normalized = str(output_file).replace(".csv", ".not_normalized.csv")
    submission_df = combine(
        Path(sdrf_dir), Path(file_not_normalized), 
        sample_df.columns.tolist(),
        sample_df["PXD"].unique())
    submission = submission_df
    print(f"Combined SDRF dataframe saved -> {file_not_normalized} dataset shape {submission_df.shape}")

    if normalisation:
        submission_norm = normalise_submission(submission_df, cv_normalizer)
        file_normalized = str(output_file).replace(".csv", ".normalized.csv")
        submission_norm.to_csv(file_normalized, index=False)
        print(f"Normalised SDRF dataframe saved -> {file_normalized} dataset shape {submission_norm.shape}")
        submission = submission_norm

    if merge:
        pass

    if submission is None:
        pass
    else:
        submission.to_csv(output_file, index=False)
        print(f"Submission SDRF dataframe saved -> {output_file} dataset shape {submission.shape}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Post-process SDRF pipeline outputs"
    )

    # required
    parser.add_argument(
        "sdrf_dir",
        type=Path,
        help="Folder with outputs from sdrf_pipeline.main_fill",
    )

    # optional with default
    parser.add_argument(
        "--sample-submission",
        type=Path,
        default=DEFAULT_SAMPLE,
        help=f"Sample submission file (default: {DEFAULT_SAMPLE})",
    )

    # boolean flag (default True → allow disabling)
    parser.add_argument(
        "--no-normalisation",
        action="store_true",
        help="Disable normalisation (enabled by default)",
    )

    # required output
    parser.add_argument(
        "-o",
        "--output-file",
        type=Path,
        default="submission.csv",
        help="Output - submission.csv",
    )

    # flexible merge input
    parser.add_argument(
        "--merge",
        type=str,
        default=None,
        help="Path to file to another submission.csv to merge with (optional)",
    )

    args = parser.parse_args(argv)

    normalisation = not args.no_normalisation

    process(
        sdrf_dir=args.sdrf_dir,
        output_file=args.output_file,
        sample_submission=args.sample_submission,
        normalisation=normalisation,
        merge=args.merge,
    )


if __name__ == "__main__":
    main()