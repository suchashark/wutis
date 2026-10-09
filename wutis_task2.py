import backtrader as bt
import yfinance as yf
import pandas as pd
import numpy as np

class MomentumStrategy(bt.Strategy):


    def next(self):
        #VWAP (Volume-Weighted Average Price
        #1 long, buy, upper bound acc noize area      if the market breaches the boundaries of the Noise Area, our strategy initiates positions.
        #-1 short,sall, lower bound
        target_pos = self.data.target_position[0]
        current_pos = self.position.size

        if target_pos == 1 and current_pos <= 0:
            self.buy()
            #if in short or flat, want long
            #if in short, closes it and opens long
        elif target_pos == -1 and current_pos >= 0:
            self.sell()
            #if no cash, lend by brocker
            #Positions are unwound either at market Close or if there is a crossover to the opposite boundary
            # In the event of such a crossover, the existing position is closed, and a new one is initiated in
            # the opposite direction to align with the latest evidence of demand/supply imbalance.
        elif target_pos == 0 and current_pos != 0:
            self.close()
#send market orders 

def prepare_momentum_data(df):
    if df.index.tz is not None:
        df.index = df.index.tz_convert('US/Eastern') # 
        df.index = df.index.tz_localize(None) #to join tz naive and tz aware

    df = df.copy() #local variable
    df['day'] = df.index.date

    daily_groups = df.groupby('day')
    all_days = df['day'].unique()

    df['vwap'] = np.nan # new null columns, nan because float64
    df['move_open'] = np.nan
    df['sigma_open'] = np.nan

    spy_ret = pd.Series(index=all_days, dtype=float) #by default nan

    for d in range(1, len(all_days)):
        current_day = all_days[d]
        prev_day = all_days[d - 1]

        current_day_data = daily_groups.get_group(current_day)
        prev_day_data = daily_groups.get_group(prev_day)

#Volume Weighted AveragePrice (VWAP) = (S price x volume) / (S volume)
        hlc = (current_day_data['high'] + current_day_data['low'] + current_day_data['close']) / 3 #price
        vol_x_hlc = current_day_data['volume'] * hlc # price x volume
        cum_vol_x_hlc = vol_x_hlc.cumsum() #cumulative sum for every 5 mins
        cum_volume = current_day_data['volume'].cumsum()
        df.loc[current_day_data.index, 'vwap'] = cum_vol_x_hlc / cum_volume

        open_price = current_day_data['open'].iloc[0] #bacause index is date, iloc to take chrini first
        df.loc[current_day_data.index, 'move_open'] = np.abs(current_day_data['close'] / open_price - 1) #loc to not write for all days at once, only forcurr

        spy_ret.loc[current_day] = current_day_data['close'].iloc[-1] / prev_day_data['close'].iloc[-1] - 1 #daily return for standard deviation

        if d > 14:
            df.loc[current_day_data.index, 'spy_dvol'] = spy_ret.iloc[d - 15:d - 1].std(skipna=False) #std sigma standart abweichung standard deviation
#false not to ignore skipped values (because in formula 14 days)

    market_open = pd.to_datetime(df.index.date.astype(str) + ' 09:30:00') #"2001-03-15" + " 09:30:00"
    df['min_from_open'] = ((df.index - market_open) / pd.Timedelta(minutes=1)) + 1 #how much time frim open market / 1 min, float
    df['minute_of_day'] = df['min_from_open'].round().astype(int) #float to int

    minute_groups = df.groupby('minute_of_day')
    df['move_open_rolling_mean'] = minute_groups['move_open'].transform(
        lambda x: x.rolling(window=14, min_periods=1).mean()
    )
    df['sigma_open'] = minute_groups['move_open_rolling_mean'].transform(lambda x: x.shift(1)) #shift not cur day ( to avoid looking in the future)

    daily_close = df.groupby('day')['close'].last().shift(1)
    df['prev_close'] = df['day'].map(daily_close).astype(float)
    df['open_price'] = df.groupby('day')['open'].transform('first')

    band_mult = 1
    df['UB'] = np.maximum(df['open_price'], df['prev_close']) * (1 + band_mult * df['sigma_open'].fillna(0))
    df['LB'] = np.minimum(df['open_price'], df['prev_close']) * (1 - band_mult * df['sigma_open'].fillna(0))

    df['buy_signal'] = (df['close'] > df['UB']) & (df['close'] > df['vwap'])
    df['sell_signal'] = (df['close'] < df['LB']) & (df['close'] < df['vwap'])

    df['trade_bar'] = ((df['min_from_open'] - 1) % 30 == 0)

    df['target_position'] = 0
    df.loc[df['buy_signal'] & df['trade_bar'], 'target_position'] = 1
    df.loc[df['sell_signal'] & df['trade_bar'], 'target_position'] = -1

    def custom_ffill(group):
        group = group.replace(0, np.nan).ffill().fillna(0)
        return group

    df['target_position'] = df.groupby('day')['target_position'].transform(custom_ffill)

    df['target_position'] = df.groupby('day')['target_position'].shift(1).fillna(0)

    return df

class PandasDataWithSignal(bt.feeds.PandasData):
    lines = ('target_position',)
    params = (('target_position', -1),)

if __name__ == '__main__':
    import matplotlib.pyplot as plt

    df = yf.download('SPY', period='60d', interval='5m', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df.columns = [col.lower() for col in df.columns]

    df = prepare_momentum_data(df)

    split_idx = int(len(df) * 0.75)
    df_train = df.iloc[:split_idx]
    df_test = df.iloc[split_idx:]

    def run_and_analyze(df_slice, label, initial_cash=100000):
        cerebro = bt.Cerebro()
        feed = PandasDataWithSignal(dataname=df_slice)
        cerebro.adddata(feed)
        cerebro.addstrategy(MomentumStrategy)
        cerebro.addsizer(bt.sizers.PercentSizer, percents=50)

        cerebro.broker.setcommission(commission=0.0001)
        cerebro.broker.set_slippage_perc(perc=0.0005)

        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.04, annualize=True, timeframe=bt.TimeFrame.Days)
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='volatility', timeframe=bt.TimeFrame.Days)

        cerebro.broker.setcash(initial_cash)
        results = cerebro.run()
        strat = results[0]

        analysis = {
            'Sharpe Ratio': strat.analyzers.sharpe.get_analysis().get('sharperatio', 0),
            'Annualized Return (%)': strat.analyzers.returns.get_analysis().get('rnorm100', 0),
            'Annualized Volatility (%)': pd.Series(strat.analyzers.volatility.get_analysis()).std() * np.sqrt(252) * 100,
            'Final Portfolio Value': cerebro.broker.getvalue()
        }

        print(f"\n {label} ")
        for k, v in analysis.items():
            print(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}")

        return strat, cerebro, analysis

    strat_train, cerebro_train, metrics_train = run_and_analyze(df_train, "TRAIN SET (First 75%)")
    strat_test, cerebro_test, metrics_test = run_and_analyze(df_test, "TEST SET (Last 25%)")

    print(f"\n BENCHMARK COMPARISON (TEST SET) ")
    bh_start = df_test['close'].iloc[0]
    bh_end = df_test['close'].iloc[-1]
    bh_total_return = ((bh_end / bh_start) - 1) * 100
    strat_total_return = ((metrics_test['Final Portfolio Value'] / 100000) - 1) * 100

    print(f"Strategy Total Return: {strat_total_return:.2f}%")
    print(f"Buy & Hold Total Return: {bh_total_return:.2f}%")

    print("\n Plots")

    plt.ion()

    cerebro_test.plot(iplot=False)

    fig1, ax1 = plt.subplots(figsize=(12, 5))
    fig1.canvas.manager.set_window_title('Metrics Comparison')
    fig1.suptitle('Strategy vs Buy & Hold Benchmark (Test Set)', fontsize=14, fontweight='bold')

    metrics_to_plot = ['Sharpe Ratio', 'Annualized Return (%)', 'Annualized Volatility (%)']
    strategy_values = [metrics_test[m] for m in metrics_to_plot]

    test_returns = df_test['close'].pct_change().dropna()
    bh_sharpe = (test_returns.mean() / test_returns.std()) * np.sqrt(252) if test_returns.std() != 0 else 0
    bh_return = ((df_test['close'].iloc[-1] / df_test['close'].iloc[0]) - 1) * 100 * (252 / len(df_test))
    bh_volatility = test_returns.std() * np.sqrt(252) * 100
    benchmark_values = [bh_sharpe, bh_return, bh_volatility]

    x = np.arange(len(metrics_to_plot))
    width = 0.35

    bars1 = ax1.bar(x - width/2, strategy_values, width, label='Strategy', color='blue', alpha=0.7)
    bars2 = ax1.bar(x + width/2, benchmark_values, width, label='Buy & Hold', color='red', alpha=0.7)

    for bar in bars1:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{bar.get_height():.2f}',
                 ha='center', va='bottom', fontsize=9)
    for bar in bars2:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{bar.get_height():.2f}',
                 ha='center', va='bottom', fontsize=9)

    ax1.set_xticks(x)
    ax1.set_xticklabels(metrics_to_plot, rotation=15, ha='right')
    ax1.set_ylabel('Value')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)

    fig2, ax2 = plt.subplots(figsize=(12, 6))
    fig2.canvas.manager.set_window_title('Equity Curve')

    strat_returns = pd.Series(strat_test.analyzers.volatility.get_analysis())

    strat_equity = 100000 * (1 + strat_returns).cumprod()
    bh_equity = 100000 * (1 + test_returns).cumprod()

    ax2.plot(strat_equity.index, strat_equity.values, label='Strategy', color='blue', linewidth=2)
    ax2.plot(bh_equity.index, bh_equity.values, label='Buy & Hold (SPY)', color='red', linewidth=2, linestyle='--')
    ax2.set_title('Equity Curve: Strategy vs Buy & Hold (Test Set)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Portfolio Value ($)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    plt.xticks(rotation=45)

    plt.ioff()
    plt.show()

    print("\nAll 3 plots are displayed. Close the windows to finish the script.")
