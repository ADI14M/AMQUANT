"""Parquet and DuckDB Analytical Storage Architecture for AMQUANT INDIA.

Separates:
- Raw Ingested Data (`data/india/raw/`)
- Cleaned & Audited Data (`data/india/cleaned/`)
- Corporate-Action Adjusted Data (`data/india/adjusted/`)
- Derived Signals & Features (`data/india/derived/`)

Leverages DuckDB for zero-copy analytical SQL over Parquet partitions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Literal
import duckdb
import pandas as pd

StageType = Literal["raw", "cleaned", "adjusted", "derived"]

# Base directory for storage (supports AMQUANT_DATA_DIR environment variable for Render persistent disk or cloud volumes)
DATA_DIR_ENV = os.getenv("AMQUANT_DATA_DIR")
BASE_DATA_DIR = Path(DATA_DIR_ENV).resolve() if DATA_DIR_ENV else Path(__file__).resolve().parent / "data"


@dataclass
class DatasetMetadata:
    symbol: str
    stage: StageType
    dataset_type: str
    source: str
    records_count: int
    start_date: str
    end_date: str
    collected_at: str
    exchange_tz: str = "Asia/Kolkata"
    frequency: str = "1D"
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IndiaStorageEngine:
    def __init__(self, base_dir: Path | str | None = None):
        target_dir = Path(base_dir) if base_dir else BASE_DATA_DIR
        self.base_dir = target_dir
        self.raw_dir = self.base_dir / "raw"
        self.cleaned_dir = self.base_dir / "cleaned"
        self.adjusted_dir = self.base_dir / "adjusted"
        self.derived_dir = self.base_dir / "derived"
        self.duckdb_dir = self.base_dir / "duckdb"

        # Ensure directory structure exists
        for d in (self.raw_dir, self.cleaned_dir, self.adjusted_dir, self.derived_dir, self.duckdb_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.db_path = self.duckdb_dir / "amquant_india.duckdb"

        # If a custom external/persistent volume is mounted, seed baseline parquet files if volume is empty
        package_seed_dir = Path(__file__).resolve().parent / "data"
        if self.base_dir != package_seed_dir and package_seed_dir.exists():
            self._seed_from_package(package_seed_dir)

    def _seed_from_package(self, seed_dir: Path) -> None:
        """Seed baseline parquet datasets onto persistent volume on first mount."""
        import shutil
        for sub in ("cleaned", "adjusted", "derived", "raw"):
            src_sub = seed_dir / sub
            dst_sub = self.base_dir / sub
            if src_sub.exists():
                try:
                    shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)
                except Exception:
                    pass

    def _get_stage_dir(self, stage: StageType) -> Path:
        mapping = {
            "raw": self.raw_dir,
            "cleaned": self.cleaned_dir,
            "adjusted": self.adjusted_dir,
            "derived": self.derived_dir,
        }
        return mapping[stage]

    def save_parquet(
        self,
        symbol: str,
        df: pd.DataFrame,
        stage: StageType = "cleaned",
        dataset_type: str = "ohlcv",
        source: str = "Yahoo Finance",
    ) -> DatasetMetadata:
        """Persist a DataFrame to partitioned Parquet with provenance metadata."""
        if df.empty:
            raise ValueError(f"Cannot save empty DataFrame for symbol {symbol}")

        stage_dir = self._get_stage_dir(stage) / dataset_type
        stage_dir.mkdir(parents=True, exist_ok=True)

        clean_symbol = symbol.strip().upper().replace("^", "IDX_").replace(".", "_")
        file_path = stage_dir / f"{clean_symbol}.parquet"

        save_df = df.copy()

        # Format date column if present
        date_col = next((c for c in save_df.columns if c in ("date", "timestamp", "datetime")), None)
        if date_col:
            # Convert to string or ISO for parquet serialization
            save_df[date_col] = pd.to_datetime(save_df[date_col]).dt.tz_localize(None)

        save_df.to_parquet(file_path, engine="pyarrow", index=False)

        collected_at = datetime.now(timezone.utc).isoformat()
        start_date = str(save_df[date_col].min()) if date_col else ""
        end_date = str(save_df[date_col].max()) if date_col else ""

        meta = DatasetMetadata(
            symbol=symbol,
            stage=stage,
            dataset_type=dataset_type,
            source=source,
            records_count=len(save_df),
            start_date=start_date[:10] if start_date else "",
            end_date=end_date[:10] if end_date else "",
            collected_at=collected_at,
            exchange_tz="Asia/Kolkata",
            frequency="1D",
            file_path=str(file_path),
        )

        return meta

    def load_parquet(
        self,
        symbol: str,
        stage: StageType = "cleaned",
        dataset_type: str = "ohlcv",
    ) -> pd.DataFrame | None:
        """Load a DataFrame from Parquet storage."""
        stage_dir = self._get_stage_dir(stage) / dataset_type
        clean_symbol = symbol.strip().upper().replace("^", "IDX_").replace(".", "_")
        file_path = stage_dir / f"{clean_symbol}.parquet"

        if not file_path.exists():
            return None

        df = pd.read_parquet(file_path, engine="pyarrow")
        return df

    def save_intraday_parquet(
        self,
        symbol: str,
        df: pd.DataFrame,
        interval: str = "5m",
        stage: StageType = "cleaned",
        source: str = "Yahoo Finance",
    ) -> DatasetMetadata:
        """Persist intraday OHLCV DataFrame partitioned by interval."""
        if df.empty:
            raise ValueError(f"Cannot save empty intraday DataFrame for symbol {symbol}")

        stage_dir = self._get_stage_dir(stage) / "intraday" / interval
        stage_dir.mkdir(parents=True, exist_ok=True)

        clean_symbol = symbol.strip().upper().replace("^", "IDX_").replace(".", "_")
        file_path = stage_dir / f"{clean_symbol}.parquet"

        save_df = df.copy()
        date_col = next((c for c in save_df.columns if c in ("datetime", "timestamp", "date")), None)
        if date_col:
            save_df[date_col] = pd.to_datetime(save_df[date_col]).dt.tz_localize(None)

        save_df.to_parquet(file_path, engine="pyarrow", index=False)

        collected_at = datetime.now(timezone.utc).isoformat()
        start_date = str(save_df[date_col].min()) if date_col else ""
        end_date = str(save_df[date_col].max()) if date_col else ""

        return DatasetMetadata(
            symbol=symbol,
            stage=stage,
            dataset_type=f"intraday_{interval}",
            source=source,
            records_count=len(save_df),
            start_date=start_date,
            end_date=end_date,
            collected_at=collected_at,
            exchange_tz="Asia/Kolkata",
            frequency=interval.upper(),
            file_path=str(file_path),
        )

    def load_intraday_parquet(
        self,
        symbol: str,
        interval: str = "5m",
        stage: StageType = "cleaned",
    ) -> pd.DataFrame | None:
        """Load intraday DataFrame for a symbol and interval."""
        stage_dir = self._get_stage_dir(stage) / "intraday" / interval
        clean_symbol = symbol.strip().upper().replace("^", "IDX_").replace(".", "_")
        file_path = stage_dir / f"{clean_symbol}.parquet"

        if not file_path.exists():
            return None

        return pd.read_parquet(file_path, engine="pyarrow")

    def save_derivatives_parquet(
        self,
        symbol: str,
        df: pd.DataFrame,
        dataset_type: str = "futures",  # 'futures' | 'options' | 'continuous'
        stage: StageType = "cleaned",
        source: str = "NSE/Yahoo",
    ) -> DatasetMetadata:
        """Persist F&O contract dataset."""
        if df.empty:
            raise ValueError(f"Cannot save empty derivatives DataFrame for {symbol}")

        stage_dir = self._get_stage_dir(stage) / dataset_type
        stage_dir.mkdir(parents=True, exist_ok=True)

        clean_symbol = symbol.strip().upper().replace("^", "IDX_").replace(".", "_")
        file_path = stage_dir / f"{clean_symbol}.parquet"

        save_df = df.copy()
        date_col = next((c for c in save_df.columns if c in ("date", "datetime", "timestamp")), None)
        if date_col:
            save_df[date_col] = pd.to_datetime(save_df[date_col]).dt.tz_localize(None)

        save_df.to_parquet(file_path, engine="pyarrow", index=False)

        collected_at = datetime.now(timezone.utc).isoformat()
        start_date = str(save_df[date_col].min()) if date_col else ""
        end_date = str(save_df[date_col].max()) if date_col else ""

        return DatasetMetadata(
            symbol=symbol,
            stage=stage,
            dataset_type=dataset_type,
            source=source,
            records_count=len(save_df),
            start_date=start_date[:10] if start_date else "",
            end_date=end_date[:10] if end_date else "",
            collected_at=collected_at,
            exchange_tz="Asia/Kolkata",
            frequency="1D",
            file_path=str(file_path),
        )

    def load_derivatives_parquet(
        self,
        symbol: str,
        dataset_type: str = "futures",
        stage: StageType = "cleaned",
    ) -> pd.DataFrame | None:
        """Load derivatives dataset."""
        stage_dir = self._get_stage_dir(stage) / dataset_type
        clean_symbol = symbol.strip().upper().replace("^", "IDX_").replace(".", "_")
        file_path = stage_dir / f"{clean_symbol}.parquet"

        if not file_path.exists():
            return None

        return pd.read_parquet(file_path, engine="pyarrow")

    def query_duckdb(self, query: str) -> list[dict[str, Any]]:
        """Run an analytical SQL query via DuckDB over the dataset directory."""
        conn = duckdb.connect(str(self.db_path))
        try:
            # Register parquet views if files exist
            for stage in ["cleaned", "adjusted", "derived"]:
                stage_dir = self._get_stage_dir(stage) / "ohlcv"
                if stage_dir.exists():
                    parquet_files = list(stage_dir.glob("*.parquet"))
                    if parquet_files:
                        pattern = str(stage_dir / "*.parquet")
                        conn.execute(f"CREATE OR REPLACE VIEW india_{stage}_ohlcv AS SELECT * FROM read_parquet('{pattern}')")

                # Register intraday views if present
                intra_dir = self._get_stage_dir(stage) / "intraday"
                if intra_dir.exists():
                    files = list(intra_dir.rglob("*.parquet"))
                    if files:
                        pattern = str(intra_dir / "*/*.parquet")
                        conn.execute(f"CREATE OR REPLACE VIEW india_{stage}_intraday AS SELECT * FROM read_parquet('{pattern}')")

            result = conn.execute(query).fetchdf()
            return result.to_dict(orient="records")
        finally:
            conn.close()

    def get_coverage_audit(self) -> dict[str, Any]:
        """Audit existing Parquet files, row counts, and dataset presence."""
        stages_info: dict[str, Any] = {}
        total_files = 0
        total_size_bytes = 0

        for stage in ["raw", "cleaned", "adjusted", "derived"]:
            stage_dir = self._get_stage_dir(stage)
            files = list(stage_dir.rglob("*.parquet"))
            total_files += len(files)
            stage_size = sum(f.stat().st_size for f in files)
            total_size_bytes += stage_size

            symbols = [f.stem.replace("IDX_", "^").replace("_", ".") for f in files]
            stages_info[stage] = {
                "file_count": len(files),
                "total_size_kb": round(stage_size / 1024, 2),
                "symbols_stored": symbols[:20],
            }

        return {
            "status": "operational",
            "storage_engine": "DuckDB + Apache Parquet",
            "duckdb_database": str(self.db_path),
            "total_parquet_files": total_files,
            "total_size_kb": round(total_size_bytes / 1024, 2),
            "stages": stages_info,
            "missing_coverage": [
                {"dataset": "Corporate Announcements & Audio Transcripts", "status": "Available via NSE RSS/API; Mocked interface provided"},
                {"dataset": "Tick-Level L3 Order Book", "status": "Requires commercial exchange colocation/feed; 1D & 1W provided"},
                {"dataset": "Delisted Stocks Historical Universe", "status": "Partial coverage via public archives; Point-in-time flags active"},
                {"dataset": "Historical Option Greeks (Intraday)", "status": "Requires live broker F&O subscription; EOD proxies provided"},
            ],
        }

