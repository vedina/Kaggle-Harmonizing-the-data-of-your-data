import argparse
import pandas as pd
import re
import numpy as np
from pathlib import Path
from collections import Counter
from typing import List, Any, Callable

class SDRFMerger:
    def __init__(self, apply_defaults=True):
        self.apply_defaults = apply_defaults
        
        # 1. Define Proteomics Defaults (Using required SDRF/Ontology formats)
        self.hard_defaults = {
            r".*AlkylationReagent.*": "IAA",
            r".*ReductionReagent.*": "DTT",
            r".*Enzyme.*": "NT=Trypsin;AC=MS:1001251",
            r".*FractionIdentifier.*": "1",  # we should have this from rules ...
        }

        # 2. Strategy Mapping (First match wins)
        self.family_map = [
            (re.compile(r"number_of_.*|.*_tolerance|.*_replicates", re.I), self._numeric_consensus),
            (re.compile(r"factor value\[.*\]|factors", re.I), self._union_delimited),
            (re.compile(r"characteristics\[.*\]", re.I), self._consensus),
            (re.compile(r"comment\[instrument\]|comment\[software\]", re.I), self._trust_first),
        ]
        
        self.default_strategy = self._consensus

    def _get_default_for_col(self, col_name: str) -> Any:
        if not self.apply_defaults:
            return "Not Applicable"
        for pattern, val in self.hard_defaults.items():
            if re.match(pattern, col_name, re.I):
                return val
        return "Not Applicable"

    @staticmethod
    def _to_python_type(val: Any) -> Any:
        """Helper to convert NumPy types to standard Python types to avoid np.int64 etc."""
        if pd.isna(val):
            return val
        if isinstance(val, (np.integer, np.floating)):
            return val.item()  # Returns standard Python int or float
        return val

    @staticmethod
    def _numeric_consensus(values: List[Any], col_name: str = None) -> Any:
        valid = [v for v in values if pd.notna(v)]
        if not valid: 
            return "Not Applicable"
        
        counts = Counter(valid)
        most_common_val = counts.most_common(1)[0][0]
        
        # Tie-breaker: pick the highest number
        if len(counts) > 1 and counts.most_common(2)[0][1] == counts.most_common(2)[1][1]:
            try: 
                result = max(valid, key=float)
            except (ValueError, TypeError): 
                result = most_common_val
        else:
            result = most_common_val
            
        return SDRFMerger._to_python_type(result)

    @staticmethod
    def _union_delimited(values: List[Any], col_name: str = None) -> Any:
        all_items = []
        for v in values:
            if pd.notna(v):
                items = [i.strip() for i in str(v).split(";")]
                all_items.extend(items)
        unique_items = sorted(list(set(all_items)))
        return "; ".join(unique_items) if unique_items else "Not Applicable"

    @staticmethod
    def _trust_first(values: List[Any], col_name: str = None) -> Any:
        val = values[0] if pd.notna(values[0]) else SDRFMerger._consensus(values)
        return SDRFMerger._to_python_type(val)

    @staticmethod
    def _consensus(values: List[Any], col_name: str = None) -> Any:
        valid = [v for v in values if pd.notna(v)]
        if not valid: 
            return None
        result = Counter(valid).most_common(1)[0][0]
        return SDRFMerger._to_python_type(result)

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
                result = strategy(cell_values, col)
                
                if result is None or str(result).lower() == "not applicable":
                    result = self._get_default_for_col(col)
                
                merged_df.at[idx, col] = result
        return merged_df

def load_and_normalize(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.replace(r"\|", ";", regex=True,  inplace=True)
    df.replace(';none', '',  inplace=True)
    df.replace(';Not Applicable', '',  inplace=True)   
    pattern = re.compile(r"^none$", re.I)
    df = df.replace(pattern, "Not Applicable")
    holes = (df.apply(lambda col: col.astype(str).str.lower() == "not applicable")).sum().sum()
    print(f"{path} holes {holes}")
    # Convert 'not applicable' strings to real NaNs for logic processing
    na_patterns = re.compile(r"^(not applicable|n/a|none|nan)$", re.I)
    df = df.replace(na_patterns, np.nan)
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Finalize SDRF with Defaults and Conflict Counts.")
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--names", nargs="+")
    parser.add_argument("--out_sdrf", default="final_consensus.sdrf.csv")
    parser.add_argument("--out_matrix", default="comparison_matrix.csv")
    parser.add_argument("--no_defaults", action="store_false", dest="apply_defaults")
    parser.add_argument("--out_merge", default="final_merged.sdrf.csv")

    args = parser.parse_args()
    model_names = args.names if args.names else [Path(p).stem for p in args.inputs]
    model_dfs = {name: load_and_normalize(path) for name, path in zip(model_names, args.inputs)}

    merger = SDRFMerger(apply_defaults=args.apply_defaults)
    final_sdrf = merger.merge(model_dfs)
    
    # Save the merged SDRF
    final_sdrf.to_csv(args.out_sdrf, index=False)

    holes = final_sdrf.map(lambda x: str(x).strip().lower() == "not applicable").values.sum()    

    # Comparison Matrix Logic
    report_rows = []
    for col in final_sdrf.columns:
        row_stats = {"SDRF Field": col}
        all_series = []
        for name, df in model_dfs.items():
            series = df[col]
            all_series.append(series)
            row_stats[f"{name} %"] = f"{(series.notna().sum() / len(series) * 100):.1f}%"
            row_stats[f"{name} Top 3"] = str(list(series.dropna().unique()[:3]))
        
        is_defaulted = any(re.match(p, col, re.I) for p in merger.hard_defaults.keys())
        all_empty = all(df[col].isna().all() for df in model_dfs.values())
        row_stats["Used Default?"] = "YES" if (is_defaulted and all_empty) else "No"
        
        temp_df = pd.concat(all_series, axis=1)
        row_stats["Conflict Count"] = temp_df.apply(lambda x: x.nunique(dropna=True) > 1, axis=1).sum()
        
        report_rows.append(row_stats)
    
    df = pd.DataFrame(report_rows)
    df.to_csv(args.out_matrix, index=False)

    print(f"✅ Final SDRF: {args.out_sdrf}\n📊 Comparison: {args.out_matrix} Holes {holes}")

if __name__ == "__main__":
    main()