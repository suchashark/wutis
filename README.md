## Code Structure (wutis_task.py)

The script is organized into four logical components:

### 1. MomentumStrategy (bt.Strategy)
Handles order execution based on pre-calculated signals. 
- Includes a lunch-hour filter (12:30–14:00)
- Reads the target_position line (1 for Long, -1 for Short, 0 for Flat) and executes self.buy(), self.sell(), or self.close() accordingly.

### 2. prepare_momentum_data(df)
The quantitative core. Pre-calculates all indicators exactly as described in the original research, adapted for 5-minute yfinance data:
- VWAP: Intraday Volume-Weighted Average Price.
- `sigma_open`: Rolling mean of absolute open-to-close moves, shifted by 1 period to prevent look-ahead bias.
- Bands (UB/LB): Dynamic upper and lower boundaries based on sigma_open and the previous day's close.
- Signal Generation: Triggers only when price breaches bands *and* aligns with VWAP, filtered to evaluate every 30 minutes.

### 3. PandasDataWithSignal (bt.feeds.PandasData)
A custom data feed class that injects the pre-calculated target_position column into backtrader's data lines, allowing the strategy to read pandas-generated signals seamlessly.

### 4. Main Execution Block (if __name__ == '__main__':)
Orchestrates the backtest lifecycle:
- Data Fetching: Downloads 60 days of 5-minute SPY data (the maximum limit for free yfinance intraday data) and cleans the MultiIndex.
- Train/Test Split: Splits data 75% / 25% to validate robustness and prevent overfitting on a short timeframe.
- `run_and_analyze()` Function: Initializes Cerebro, applies realistic market friction, attaches analyzers, and returns performance metrics.
- Visualization: Uses matplotlib in interactive mode to simultaneously display the backtrader candlestick chart, a metrics comparison bar chart, and an equity curve.

## Design Justifications (Assignment Requirements)

- Train/Test Split: A 75/25 split is enforced. Given the 60-day data constraint, testing on unseen data is critical to prove the strategy is not overfitted to a specific market regime.
- Realistic Costs & Slippage: Commission is set to 0.0001 (0.01%) and slippage to 0.0005 (0.05%). These are realistic estimates for highly liquid ETFs like SPY, ensuring the backtest reflects actual execution friction rather than theoretical perfection.
- Metrics Calculation: 
  - SharpeRatio and Returns are extracted via native backtrader analyzers (with timeframe=bt.TimeFrame.Days to ensure correct annualization on short datasets).
  - Volatility: Standard backtrader lacks a built-in Volatility analyzer. Therefore, annualized volatility is correctly calculated manually from the TimeReturn analyzer using the standard financial formula: std(daily_returns) * sqrt(252) * 100.
- Benchmark Comparison: The script explicitly calculates and prints the Buy & Hold return for the test period, providing the required direct comparison to evaluate the strategy's alpha.
