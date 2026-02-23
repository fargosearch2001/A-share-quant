"""
回测引擎
负责资金管理、订单撮合、持仓维护
"""
import pandas as pd
from typing import Dict, List, Any
from datetime import date, datetime

from src.config import BacktestConfig
from src.data.loader import DataLoader
from src.strategy.base import Strategy
from src.data.models import TradeRecord, EquityPoint


class BacktestEngine:
    def __init__(self, 
                 config: BacktestConfig, 
                 loader: DataLoader, 
                 strategy: Strategy,
                 stk_pool: List[str]):
        self.config = config
        self.loader = loader
        self.strategy = strategy
        self.stk_pool = stk_pool
        
        # 账户状态
        self.cash = config.initial_cash
        self.positions: Dict[str, int] = {}  # symbol -> quantity
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[EquityPoint] = []
        
        self.current_date: date = date.min

    def run(self, start_date: date, end_date: date) -> None:
        """运行回测"""
        print(f"Starting backtest from {start_date} to {end_date}...")
        
        # 1. 策略初始化 (注入 Context)
        if hasattr(self.strategy, 'setup'):
            self.strategy.setup(self)
        else:
            # 兼容旧代码
            self.strategy.initialize(self)
        
        # 2. 生成交易日历 (取所有股票交易日的并集)
        all_dates = set()
        for symbol in self.stk_pool:
            df = self.loader.get_data(symbol, "daily")
            if not df.empty:
                # 筛选在回测区间内的日期
                mask = (df.index.date >= start_date) & (df.index.date <= end_date)
                all_dates.update(df[mask].index.date)
                
        trade_dates = sorted(list(all_dates))
        print(f"Total trading days: {len(trade_dates)}")
        
        # 3. 按日循环
        for d in trade_dates:
            self.current_date = d
            
            # 每日开盘前处理 (暂无)
            
            # 盘中/收盘策略逻辑
            if hasattr(self.strategy, 'handle_data'):
                self.strategy.handle_data()
            else:
                # 兼容旧代码
                self.strategy.handle_day(self)
            
            # 每日结算
            self._settle_equity()

    def _settle_equity(self) -> None:
        """每日收盘结算权益"""
        market_value = 0.0
        for symbol, qty in self.positions.items():
            price = self._get_current_price(symbol)
            if price:
                market_value += price * qty
            else:
                # 如果停牌，沿用最近收盘价 (需优化，这里简化处理为0或忽略)
                # 实际上应该取最近有效价格。
                # 由于 loader.get_data 返回的是完整 DataFrame，我们可以用 asof 查找
                price = self._get_last_price(symbol)
                if price:
                    market_value += price * qty
        
        total_assets = self.cash + market_value
        self.equity_curve.append(EquityPoint(
            date=self.current_date,
            total_assets=total_assets,
            cash=self.cash,
            market_value=market_value
        ))

    def _get_current_price(self, symbol: str) -> float:
        """获取当前日期收盘价"""
        df = self.loader.get_data(symbol, "daily")
        try:
            # 必须是当天的价格
            # pd.Timestamp(self.current_date)
            ts = pd.Timestamp(self.current_date)
            if ts in df.index:
                return df.loc[ts]["close"]
        except Exception:
            pass
        return None

    def _get_last_price(self, symbol: str) -> float:
        """获取最近有效收盘价 (处理停牌)"""
        df = self.loader.get_data(symbol, "daily")
        try:
            ts = pd.Timestamp(self.current_date)
            # asof 查找 <= ts 的最近索引
            idx = df.index.asof(ts)
            if idx is not None:
                return df.loc[idx]["close"]
        except Exception:
            pass
        return None

    def get_position(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def get_cash(self) -> float:
        return self.cash

    def buy(self, symbol: str, quantity: int, note: str = "") -> bool:
        """执行买入"""
        if quantity <= 0:
            return False
            
        price = self._get_current_price(symbol)
        if not price:
            # print(f"Cannot buy {symbol} on {self.current_date}: No price")
            return False
            
        # 考虑滑点
        exec_price = price * (1 + self.config.slippage)
        cost = exec_price * quantity
        commission = cost * self.config.commission_rate
        total_cost = cost + commission
        
        if self.cash >= total_cost:
            self.cash -= total_cost
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            self.trades.append(TradeRecord(
                date=self.current_date,
                symbol=symbol,
                action="BUY",
                price=exec_price,
                quantity=quantity,
                commission=commission,
                note=note
            ))
            # print(f"BUY {symbol} {quantity} @ {exec_price:.2f} on {self.current_date}")
            return True
        return False

    def sell(self, symbol: str, quantity: int, note: str = "") -> bool:
        """执行卖出"""
        if quantity <= 0:
            return False
            
        current_pos = self.positions.get(symbol, 0)
        if current_pos < quantity:
            quantity = current_pos # 卖出全部可用
            
        price = self._get_current_price(symbol)
        if not price:
            return False
            
        # 考虑滑点
        exec_price = price * (1 - self.config.slippage)
        revenue = exec_price * quantity
        commission = revenue * self.config.commission_rate
        net_revenue = revenue - commission
        
        self.cash += net_revenue
        self.positions[symbol] -= quantity
        if self.positions[symbol] == 0:
            del self.positions[symbol]
            
        self.trades.append(TradeRecord(
            date=self.current_date,
            symbol=symbol,
            action="SELL",
            price=exec_price,
            quantity=quantity,
            commission=commission,
            note=note
        ))
        # print(f"SELL {symbol} {quantity} @ {exec_price:.2f} on {self.current_date}")
        return True
