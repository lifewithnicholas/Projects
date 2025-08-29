import pandas as pd

def load_csv(file_path: str) -> pd.DataFrame:
    """Load CSV file into a Pandas DataFrame."""
    try:
        df = pd.read_csv(file_path)
        print(f"✅ Loaded data with shape {df.shape}")
        return df
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return pd.DataFrame()
