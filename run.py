"""
项目运行入口
支持命令行参数选择策略
"""

import sys
import argparse
import pandas as pd
from datetime import date

from src.config import BacktestConfig, DataConfig, STOCK_POOL
from src.data.loader import DataLoader
from src.strategy.monthly_trend_rotation import MonthlyTrendDividendRotation
from src.strategy.double_ma import DoubleMAStrategy
from src.backtest.engine import BacktestEngine
from src.reporting.metrics import compute_metrics


def main():
    parser = argparse.ArgumentParser(description="A-Share Quantitative Backtest")
    parser.add_argument("--strategy", type=str, default="trend", 
                        choices=["trend", "ma"], help="Choose strategy: trend (Monthly Trend Rotation) or ma (Double MA)")
    parser.add_argument("--stocks", type=int, default=None,
                        help="Number of stocks to load (default: all)")
    args = parser.parse_args()

    # 1. 配置
    backtest_config = BacktestConfig(
        initial_cash=1_000_000,
        commission_rate=0.0003,
        slippage=0.001
    )
    data_config = DataConfig()
    
    # 2. 数据加载
    loader = DataLoader(data_config)
    print("Loading data...")
    
    # 选择要加载的股票
    stocks_to_load = STOCK_POOL
    if args.stocks:
        stocks_to_load = STOCK_POOL[:args.stocks]
        print(f"Loading {len(stocks_to_load)} stocks (limited by --stocks argument)")
    
    loader.load_all(stocks_to_load)
    
    # 3. 策略选择
    if args.strategy == "trend":
        print("Running Strategy: Monthly Trend & Dividend Rotation")
        strategy = MonthlyTrendDividendRotation()
    elif args.strategy == "ma":
        print("Running Strategy: Double Moving Average (20/60)")
        strategy = DoubleMAStrategy(short_window=20, long_window=60)
    else:
        print(f"Unknown strategy: {args.strategy}")
        return
    
    # 4. 回测引擎
    engine = BacktestEngine(
        config=backtest_config,
        loader=loader,
        strategy=strategy,
        stk_pool=STOCK_POOL
    )
    
    # 5. 运行回测 (2018-至今)
    start_date = date(2018, 1, 1)
    end_date = date.today()
    print(f"Backtesting range: {start_date} to {end_date}")
    
    try:
        engine.run(start_date, end_date)
    except Exception as e:
        print(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 6. 结果分析
    print("\nBacktest Completed.")
    if engine.equity_curve:
        print(f"Final Equity: {engine.equity_curve[-1].total_assets:,.2f}")
        
        metrics = compute_metrics(engine.equity_curve, engine.trades, backtest_config.initial_cash)
        print("\nPerformance Metrics:")
        for k, v in metrics.items():
            if "收益率" in k or "回撤" in k or "胜率" in k:
                print(f"{k}: {v:.2%}")
            elif "次数" in k:
                print(f"{k}: {v}")
            else:
                print(f"{k}: {v:.4f}")
    else:
        print("No trades or equity data generated.")

if __name__ == "__main__":
    main()
