import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from scipy.stats import genpareto
from scipy.ndimage import gaussian_filter1d

# --- Read tickers ---
def read_tickers() -> list:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "..", "data", "Stocks.xlsx")
    df = pd.read_excel(file_path)
    tickers = df['Stock_Symbol'].dropna().tolist()
    canadian_tickers = {'RY', 'TD'}
    return [f"{t}.TO" if t in canadian_tickers else t for t in tickers]

# --- Download stock data ---
def fetch_stock_data(tickers: list) -> pd.DataFrame:
    successful_data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start="2022-01-01", end="2024-12-31", progress=False)
            if not df.empty:
                successful_data[ticker] = df
            else:
                print(f"No data for {ticker}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
    if successful_data:
        return pd.concat(successful_data, axis=1)
    else:
        print("No data was downloaded.")
        return pd.DataFrame()

# --- Hill Estimator ---
def hill_estimator(data, k_values):
    data = np.sort(data)[::-1]
    return np.array([
        np.mean(np.log(data[:k]) - np.log(data[k])) if k < len(data) else np.nan
        for k in k_values
    ])

# Smooths Hill estimator
def smoothed_hill_estimator(data, k_values, sigma=2):
    return gaussian_filter1d(hill_estimator(data, k_values), sigma=sigma)

# Returns optimal order statistics (scalar)
def select_optimal_k(smoothed_hill: np.ndarray, k_values: np.ndarray, window: int = 5) -> int:
    slope = np.abs(np.gradient(smoothed_hill))
    slope_smooth = gaussian_filter1d(slope, sigma=window)
    min_slope_idx = np.argmin(slope_smooth)
    return k_values[min_slope_idx]

# Returns optimal xi (scalar) based on optimal order statistc
def compute_final_xi(data, optimal_k):
    data = np.sort(data)[::-1]
    return np.mean(np.log(data[:optimal_k]) - np.log(data[optimal_k]))

# --- GPD VaR & ES ---
def estimate_var_es_gpd(data: np.ndarray, threshold: float, confidence_level: float = 0.95):
    exceedances = data[data > threshold] - threshold
    if len(exceedances) < 2:
        raise ValueError("Not enough exceedances above threshold to fit GPD.")

    shape, loc, scale = genpareto.fit(exceedances)

    prob = 1 - confidence_level
    var = threshold + (scale / shape) * ((1 / prob) ** shape - 1)

    if shape >= 1:
        es = np.inf  # ES is undefined if shape ≥ 1
    else:
        es = (var + (scale - shape * threshold) / (1 - shape))

    return var, es, shape, scale

# --- Main ---
if __name__ == "__main__":
    tickers = read_tickers()
    stock_data = fetch_stock_data(tickers)

    if not stock_data.empty:
        close_prices = stock_data.xs(key='Close', axis=1, level=1)
        open_prices = stock_data.xs(key='Open', axis=1, level=1)
        daily_change = close_prices - open_prices
        daily_change_pct = (daily_change / open_prices) * 100
        daily_change_pct = daily_change_pct[daily_change_pct < 0]

        ticker = daily_change_pct.columns[0]
        data = -daily_change_pct[ticker].dropna().values  # Flip to positive tail

        k_values = np.arange(5, min(len(data) - 10, 200)) # Sets window size for smoothed Hill estim.
        smoothed_vals = smoothed_hill_estimator(data, k_values, sigma=3)

        optimal_k = select_optimal_k(smoothed_vals, k_values)
        xi = compute_final_xi(data, optimal_k)

        sorted_data = np.sort(data)[::-1]
        threshold = sorted_data[optimal_k]

        try:
            var_95, es_95, shape, scale = estimate_var_es_gpd(data, threshold, confidence_level=0.95)
            print(f"\n[ticker: {ticker}]")
            print(f"Optimal k = {optimal_k}")
            print(f"Threshold = {threshold:.4f}")
            print(f"Hill index ξ = {xi:.4f}")
            print(f"GPD shape = {shape:.4f}, scale = {scale:.4f}")
            print(f"95% VaR (GPD) = {var_95:.4f}%")
            print(f"95% Expected Shortfall (GPD) = {es_95:.4f}%")
        except Exception as e:
            print(f"Error estimating VaR/ES: {e}")

        # --- Plot Hill Estimator ---
        plt.figure(figsize=(10, 6))
        plt.plot(k_values, hill_estimator(data, k_values), label="Hill Estimator", alpha=0.4)
        plt.plot(k_values, smoothed_vals, label="Smoothed Hill Estimator", linewidth=2)
        plt.axvline(optimal_k, color="red", linestyle="--", label=f"Optimal k = {optimal_k}")
        plt.xlabel("Order Statistic k")
        plt.ylabel("Hill Index (ξ)")
        plt.title(f"Hill Plot for {ticker}")
        plt.legend()
        plt.grid(True)
        plt.show()


        plt.hist(data, bins=100, density=True)
        plt.axvline(threshold, color='red', linestyle='--', label='GPD threshold')
        plt.title(f'Distribution of Losses - {ticker}')
        plt.legend()
        plt.show()

        for delta in [-10, 0, 10]:
            test_k = optimal_k + delta
            if test_k < len(data):
             thresh = np.sort(data)[::-1][test_k]
            try:
                shape, loc, scale = genpareto.fit(data[data > thresh] - thresh)
                print(f"k={test_k}, shape={shape:.4f}, threshold={thresh:.4f}")
            except Exception as e:
                print(f"Error with k={test_k}: {e}")
                
        # # --- Plot Slope of Hill Estimator ---
        # plt.figure(figsize=(10, 4))
        # slope = np.abs(np.gradient(smoothed_vals))
        # plt.plot(k_values, slope, label="|d(Hill)/dk|", color="orange")
        # plt.axvline(optimal_k, color="red", linestyle="--", label=f"Optimal k = {optimal_k}")
        # plt.xlabel("Order Statistic k")
        # plt.ylabel("Slope of Smoothed Hill")
        # plt.title("Slope of Hill Estimator Curve")
        # plt.legend()
        # plt.grid(True)
        # plt.show()
