## Code Structure (wutis_task.py)

The intraday task was made by Elizaveta Kariavkina on Python

### 1. MomentumStrategy (bt.Strategy)
- Reads the target_position line (1 for Long, -1 for Short, 0 for Flat) and executes self.buy(), self.sell(), or self.close() accordingly.

### 2. prepare_momentum_data(df)
Pre-calculates data:
- VWAP: Volume Weighted Average Price.
- Borders: (UB/LB): upper and lower boundaries based on sigma_open and the previous day's close.
- Signal: Triggers only when price breaches bands and with VWAP, every 30 minutes.

### 3. PandasDataWithSignal (bt.feeds.PandasData)
A custom data feed class that inherits and adds new line.

### 4. Main Execution Block (if __name__ == '__main__':)
Downloads and splits data. Prints indicators
## Details

- Train/Test Split: 75/25 
- Realistic Costs & Slippage: Commission is set to 0.001  and slippage to 0.0035 
  - SharpeRatio and Returns are extracted via native backtrader analyzers (with timeframe=bt.TimeFrame.Days ).
  - Volatilitycalculated as : std(daily_returns) * sqrt(252) * 100.
- Benchmark Comparison:  Buy & Hold comparison to evaluate the strategy's alpha.
