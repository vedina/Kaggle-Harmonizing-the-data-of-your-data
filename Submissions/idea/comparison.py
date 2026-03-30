import argparse
import pandas as pd
from pathlib import Path
import re
from collections import Counter
from typing import List, Any, Callable, Dict
import numpy as np


def create_comparison_matrix(model_dfs: Dict[str, pd.DataFrame], na_val: str = "not applicable"):
    """
    Creates a summary CSV where:
    - Rows: SDRF Fields (headers)
    - Columns: Model 1 %, Model 1 Examples, Model 2 %, Model 2 Examples...
    """
    report_rows = []
    
    # Use columns from the first available model
    first_model_name = list(model_dfs.keys())[0]
    all_fields = model_dfs[first_model_name].columns

    for field in all_fields:
        row_stats = {"SDRF Field": field}
        
        for name, df in model_dfs.items():
            # Standardize NAs for calculation
            series = df[field].astype(str).replace([na_val, na_val.capitalize(), "nan", ""], np.nan)
            
            # 1. Calculate % Filled
            filled_count = series.notna().sum()
            total_count = len(series)
            fill_pct = (filled_count / total_count * 100) if total_count > 0 else 0
            
            # 2. Extract Top 3 Unique Examples
            top_examples = list(series.dropna().unique()[:3])
            
            # Add columns to the row
            row_stats[f"{name} %"] = f"{fill_pct:.1f}%"
            row_stats[f"{name} Top 3 Values"] = str(top_examples)
            
        report_rows.append(row_stats)
    
    return pd.DataFrame(report_rows)


class SelectorStrategies:
    @staticmethod
    def consensus(values: List[Any]) -> Any:
        """Returns the most frequent non-NA value."""
        valid = [v for v in values if str(v).lower() != "not applicable" and v is not None]
        if not valid: return "not applicable"
        return Counter(valid).most_common(1)[0][0]


    @staticmethod
    def union_delimited(values: List[Any]) -> Any:
        """Merges unique values using a semicolon (ideal for Factors or Mods)."""
        all_items = []
        for v in values:
            if str(v).lower() != "not applicable" and v:
                # Split by semicolon in case a model already provided a list
                items = [i.strip() for i in str(v).split(";")]
                all_items.extend(items)
        unique_items = sorted(list(set(all_items)))
        return "; ".join(unique_items) if unique_items else "not applicable"

    @staticmethod
    def trust_first(values: List[Any]) -> Any:
        """Trusts the first model (e.g., GPT-4o) if it found something, else consensus."""
        if str(values[0]).lower() != "not applicable":
            return values[0]
        return SelectorStrategies.consensus(values)


class SDRFMerger:
    def __init__(self):
        # Define Families using Regex patterns
        self.family_map = [
            (re.compile(r"factor value\[.*\]|factors", re.I), SelectorStrategies.union_delimited),
            (re.compile(r"characteristics\[.*\]", re.I), SelectorStrategies.consensus),
            (re.compile(r"comment\[instrument\]|comment\[software\]", re.I), SelectorStrategies.trust_first),
        ]
        self.default_strategy = SelectorStrategies.consensus

    def get_strategy(self, column_name: str) -> Callable:
        for pattern, strategy in self.family_map:
            if pattern.match(column_name):
                return strategy
        return self.default_strategy

    def merge(self, model_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
        names = list(model_dfs.keys())
        base_df = next(iter(model_dfs.values()))
        merged_df = pd.DataFrame(index=base_df.index, columns=base_df.columns)

        for col in base_df.columns:
            strategy = self.get_strategy(col)
            for idx in base_df.index:
                cell_values = [model_dfs[name].at[idx, col] for name in names]
                merged_df.at[idx, col] = strategy(cell_values)
        return merged_df
    

def main():
    parser = argparse.ArgumentParser(description="Generate SDRF Comparison Matrix CSV.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Paths to model CSVs")
    parser.add_argument("--names", nargs="+", help="Names for models (e.g. GPT4o Claude3)")
    parser.add_argument("--output_matrix", default="model_comparison_matrix.csv")
    
    args = parser.parse_args()
    names = args.names if args.names else [Path(p).stem for p in args.inputs]
    
    # Load all DataFrames
    model_dfs = {
        name: pd.read_csv(path).replace("Not Applicable", np.nan)
        for name, path in zip(names, args.inputs)
    }
    
    # Generate the Matrix
    matrix_df = create_comparison_matrix(model_dfs)
    
    # Save to CSV
    matrix_df.to_csv(args.output_matrix, index=False)
    print(f"📊 Comparison Matrix saved to: {args.output_matrix}")

if __name__ == "__main__":
    main()