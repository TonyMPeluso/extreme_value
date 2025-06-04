import os
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import genpareto
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import minimize
from typing import Dict, List, Union

# --- Configuration ---
START_DATE = "2022-01-01"
END_DATE = "2024-12-31"
LOSS_THRESHOLD = 30
HILL_K_MIN = 5
HILL_K_MAX_FACTOR = 0.95
HILL_SIGMA = 2
SELECT_K_SIGMA = 5
GPD_ALPHA = 0.95
MIN_EXCEEDANCES = 5

# --- File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "stock_summary.csv")
TICKERS_FILE = os.path.join(DATA_DIR, "Stocks.xlsx")

# --- Ensure data directory exists ---
os.makedirs(DATA_DIR, exist_ok=True)

# --- Data Structures ---
PriceData = Dict[str, pd.DataFrame]
RiskRecord = Dict[str, Union[float, str]]

# --- Read tickers ---
def read_tickers() -> pd.DataFrame:
    try:
        df = pd.read_excel(TICKERS_FILE)
        canadian = {"RY", "TD"}
        df["Ticker"] = df["Stock_Symbol"].apply(lambda t: f"{t}.TO" if t in canadian else t)
        return df[["Company_Name", "Ticker"]]
    except FileNotFoundError:
        print(f"Error: Tickers file not found at {TICKERS_FILE}")
        return pd.DataFrame(columns=["Company_Name", "Ticker"])

# --- Download prices ---
def download_prices(ticker_list: List[str]) -> PriceData:
    results: PriceData = {}
    for ticker in ticker_list:
        print(f"Downloading: {ticker}")
        try:
            df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)[["Open", "Close"]].dropna()
            if not df.empty:
                results[ticker] = df
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
    return results

# --- Hill estimator functions ---
def hill_estimator(data: np.ndarray, k_vals: np.ndarray) -> np.ndarray:
    """Performs Hill estimation and smooths output."""
    data_sorted = np.sort(data)[::-1]
    return gaussian_filter1d([np.mean(np.log(data_sorted[:k]) - np.log(data_sorted[k])) if k < len(data_sorted) else np.nan for k in k_vals], sigma=HILL_SIGMA)

def select_k(smoothed: np.ndarray, k_vals: np.ndarray) -> int:
    """Finds optimal k such that zero gradient of Hill estimator -- "Eye-ball method". """
    return k_vals[np.argmin(gaussian_filter1d(np.abs(np.gradient(smoothed)), sigma=SELECT_K_SIGMA))]

def estimate_hill_shape(data: np.ndarray, k: int) -> float:
    """Estimates the shape parameter using the Hill estimator for optimal k."""
    data_sorted = np.sort(data)[::-1]
    if k >= len(data_sorted) or k <= 0:
        raise ValueError("k must be a valid index within the data")
    return np.mean(np.log(data_sorted[:k]) - np.log(data_sorted[k]))

# --- GPD fitting using MLE (with fixed shape) to extract scale parameter ---
def gpd_log_likelihood_fixed_shape(scale, data, shape):
    """Log-likelihood function for the GPD with a fixed shape parameter from above."""
    if scale <= 0:
        return np.inf
    try:
        return -np.sum(genpareto.logpdf(data, shape, loc=0, scale=scale))
    except Exception:
        return np.inf

def fit_gpd_mle_fixed_shape(data: np.ndarray, shape: float) -> Union[float, None]:
    """Fits the GPD scale parameter using MLE, with the shape parameter fixed."""
    if len(data) < MIN_EXCEEDANCES:
        return None
    initial_guess = np.std(data)  # Initial guess for scale
    bounds = [(1e-6, np.inf)]  # Scale must be positive
    result = minimize(gpd_log_likelihood_fixed_shape, initial_guess, args=(data, shape), bounds=bounds, method='L-BFGS-B')
    if result.success:
        return float(result.x[0])
    else:
        print(f"MLE fitting failed: {result.message}")
        return None

# --- Returns risk measures -- Value at Risk and Expected Shortfall ---
def compute_gpd_risks_mle(data: np.ndarray, threshold: float, alpha: float = GPD_ALPHA) -> tuple[Union[float, None], Union[float, None]]:
    """ Returns risk measures -- Value at Risk and Expected Shortfall """
    exceed = data[data > threshold] - threshold
    if len(exceed) < MIN_EXCEEDANCES:
        return None, None
    k_vals = np.arange(HILL_K_MIN, min(len(exceed) - 10, 150))
    if len(k_vals) < 2:
        return None, None
    smoothed = hill_estimator(exceed, k_vals)
    k_star = select_k(smoothed, k_vals)
    shape = estimate_hill_shape(exceed, k_star)
    scale = fit_gpd_mle_fixed_shape(exceed, shape)

    if scale is not None:
        q = 1 - alpha
        if shape == 0:
            var = threshold + scale * np.log(1 / q)
            es = threshold + scale * (np.log(1 / q) + 1)
        elif shape > 0:
            var = threshold + (scale / shape) * ((1 / q)**shape - 1)
            es = threshold + (var - threshold + scale) / (1 - shape)
        else:
            var = threshold + (scale / shape) * ((1 / q)**shape - 1)
            es = threshold + (var - threshold + scale) / (1 - shape)
        return float(var.item()), float(es.item())  # Changed this line
    return None, None

# --- Compute risks and return ---
def compute_risks(prices: PriceData, metadata: pd.DataFrame) -> pd.DataFrame:
    records: List[RiskRecord] = []
    for ticker, df in prices.items():
        try:
            daily_ret = (df["Close"] - df["Open"]) / df["Open"] * 100
            losses = -daily_ret[daily_ret < 0].dropna().values
            if len(losses) < LOSS_THRESHOLD:
                print(f"Insufficient loss data for {ticker}. Skipping.")
                continue
            k_vals = np.arange(HILL_K_MIN, min(len(losses) - 10, 150))
            if len(k_vals) < 2:
                print(f"Insufficient k values for Hill estimator for {ticker}. Skipping.")
                continue
            smoothed = hill_estimator(losses, k_vals)
            threshold = np.sort(losses)[::-1][select_k(smoothed, k_vals)]
            var, es = compute_gpd_risks_mle(losses, threshold)
            avg_return = daily_ret.mean().item() if isinstance(daily_ret.mean(), pd.Series) else float(daily_ret.mean())
            name = metadata.loc[metadata["Ticker"] == ticker, "Company_Name"].iloc[0] if not metadata.loc[metadata["Ticker"] == ticker, "Company_Name"].empty else ticker
            records.append({
                "Name": name,
                "Ticker": ticker,
                "Average_Return": avg_return,
                "VaR": var,
                "ES": es,
            })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
    summary_df = pd.DataFrame(records)
    for col in ['Average_Return', 'VaR', 'ES']: # Exclude 'Scale'
        if col in summary_df.columns:
            summary_df[f"{col}_Rank"] = summary_df[col].rank(ascending=(col == 'Average_Return'), na_option='bottom').astype('Int64')
    return summary_df

# --- Save summary ---
def save_summary(df: pd.DataFrame):
    if not df.empty:
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n Saved summary to: {OUTPUT_FILE}")
    else:
        print("No summary DataFrame to save.")

# --- Main ---
if __name__ == "__main__":
    metadata = read_tickers()
    if metadata.empty:
        print("Exiting due to empty or missing tickers file.")
        exit()
    prices = download_prices(metadata["Ticker"].tolist())
    summary_df = compute_risks(prices, metadata)
    save_summary(summary_df)