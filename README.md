# Investment Risk Dashboard

This project provides an interactive dashboard designed to analyze the risk of various stocks listed on the New York Stock Exchange (NYSE).

It calculates multiple measures of financial risk, including:
* **Variance:** A basic measure of dispersion.
* **Value at Risk (VaR):** Estimates the maximum potential loss at a given confidence level over a specific period.
* **Expected Shortfall (ES):** Quantifies the average loss expected to occur beyond the VaR level, providing a more robust risk measure for extreme events.

These risk measures are calculated using **Extreme Value Methods**, which are particularly suited for modeling the tails of financial data distributions to better capture extreme market movements. Here, the threshold for the extreme value is selected using a smoothed Hill estimator.

The dashboard allows for selecting a stock and graphing its return vs. risk (for measures of VaR and ES) alongside comparable stocks.

---

## Features (To be expanded)
* Interactive dashboard for real-time stock data analysis.
* Calculation of Variance, VaR, and ES.
* Utilization of Extreme Value Theory for robust risk assessment.
* Threshold for extreme value selected using a smoothed Hill estimator.
* Ability to select a stock and visualize its return vs. risk.
* Comparison against comparable stocks.
* *(Add more features as your project develops)*

## Installation (To be expanded)

To run this project locally, follow these steps:
```bash
git clone [https://github.com/TonyMPeluso/extreme_value.git](https://github.com/TonyMPeluso/extreme_value.git)
cd extreme_value # Or your repository name if different
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
