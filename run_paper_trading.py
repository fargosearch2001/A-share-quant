
import os
import sys
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import DataConfig
from src.trading.data import RealTimeDataLoader
from src.trading.broker import SimulatedBroker
from src.trading.engine import PaperTradingEngine
from src.trading.vnpy_runner import start_vnpy_engine
from src.strategy.double_ma import DoubleMAStrategy

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["once", "loop"], default="once")
    parser.add_argument("--engine", choices=["builtin", "vnpy"], default="builtin")
    parser.add_argument("--interval-minutes", type=int, default=5)
    parser.add_argument("--start-time", default="09:30")
    parser.add_argument("--end-time", default="15:00")
    parser.add_argument("--max-runs", type=int, default=0)
    parser.add_argument("--symbols", default="600000.SH,000001.SZ,600519.SH")
    return parser.parse_args()

def main():
    print("=== Starting Paper Trading System ===")
    args = parse_args()
    stk_pool = [s.strip() for s in args.symbols.split(",") if s.strip()]
    
    data_config = DataConfig()
    
    if args.engine == "vnpy":
        start_vnpy_engine()
        print("vn.py 引擎已初始化")
        return

    loader = RealTimeDataLoader(data_config)
    broker = SimulatedBroker(account_file="paper_account.json", initial_cash=100000.0)
    strategy = DoubleMAStrategy(short_window=5, long_window=20)
    engine = PaperTradingEngine(
        strategy=strategy,
        broker=broker,
        loader=loader,
        stk_pool=stk_pool
    )
    
    max_runs = args.max_runs if args.max_runs > 0 else None
    if args.mode == "loop":
        engine.run_loop(
            interval_minutes=args.interval_minutes,
            start_time=args.start_time,
            end_time=args.end_time,
            max_runs=max_runs
        )
    else:
        engine.run_daily()
    
    print("\n=== Current Account Status ===")
    print(f"Cash: {broker.get_cash():.2f}")
    print(f"Positions: {broker.get_positions()}")

if __name__ == "__main__":
    main()
