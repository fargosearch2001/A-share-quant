
import pandas as pd
import time as time_module
from typing import Dict, List, Any, Optional
from datetime import date, datetime, time, timedelta

from src.strategy.base import Strategy
from src.trading.broker import Broker
from src.trading.data import RealTimeDataLoader

class PaperTradingEngine:
    """
    实盘/模拟盘交易引擎
    """
    def __init__(self, 
                 strategy: Strategy, 
                 broker: Broker,
                 loader: RealTimeDataLoader,
                 stk_pool: List[str]):
        self.strategy = strategy
        self.broker = broker
        self.loader = loader
        self.stk_pool = stk_pool
        
        self.current_date = datetime.now().date()
        
        # 缓存数据
        self._price_cache: Dict[str, float] = {}

    @property
    def cash(self) -> float:
        return self.broker.get_cash()

    @property
    def positions(self) -> Dict[str, int]:
        return self.broker.get_positions()

    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格，优先使用缓存"""
        if symbol in self._price_cache:
            return self._price_cache[symbol]
            
        price = self.loader.get_current_price(symbol)
        if price > 0:
            self._price_cache[symbol] = price
        return price

    def buy(self, symbol: str, quantity: int, note: str = "") -> bool:
        price = self._get_current_price(symbol)
        if price <= 0:
            print(f"Cannot buy {symbol}: Invalid price {price}")
            return False
        return self.broker.buy(symbol, price, quantity, note)

    def sell(self, symbol: str, quantity: int, note: str = "") -> bool:
        price = self._get_current_price(symbol)
        if price <= 0:
            print(f"Cannot sell {symbol}: Invalid price {price}")
            return False
        return self.broker.sell(symbol, price, quantity, note)

    def run_daily(self) -> None:
        """
        每日运行一次策略逻辑
        """
        print(f"--- Running Paper Trading for {self.current_date} ---")
        
        # 1. 刷新数据
        # self.loader.load_all(self.stk_pool) # 已经在外部做，或者这里强制刷新
        
        # 清空价格缓存
        self._price_cache = {}
        
        # 2. 策略初始化 (注入 Context)
        if hasattr(self.strategy, 'setup'):
            # 这里注入 self 作为 context 的 engine
            self.strategy.setup(self)
        else:
            self.strategy.initialize(self)
            
        # 3. 执行策略逻辑
        if hasattr(self.strategy, 'handle_data'):
            self.strategy.handle_data()
        else:
            self.strategy.handle_day(self)
            
        print("--- Daily Run Completed ---")

    def run_loop(self, interval_minutes: int = 5, start_time: str = "09:30", end_time: str = "15:00", max_runs: Optional[int] = None) -> None:
        start_t = datetime.strptime(start_time, "%H:%M").time()
        end_t = datetime.strptime(end_time, "%H:%M").time()
        runs = 0
        while True:
            now = datetime.now()
            self.current_date = now.date()
            if not self._is_trading_day(self.current_date):
                if max_runs is not None and runs >= max_runs:
                    break
                time_module.sleep(60)
                continue
            if now.time() < start_t:
                sleep_seconds = max(1, int((datetime.combine(self.current_date, start_t) - now).total_seconds()))
                time_module.sleep(sleep_seconds)
                continue
            if now.time() > end_t:
                if max_runs is not None and runs >= max_runs:
                    break
                time_module.sleep(60)
                continue
            self.run_daily()
            runs += 1
            if max_runs is not None and runs >= max_runs:
                break
            time_module.sleep(max(1, interval_minutes * 60))

    def _is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5
