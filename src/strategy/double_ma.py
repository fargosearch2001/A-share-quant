"""
双均线策略 (演示用)
当短期均线上穿长期均线时买入，下穿时卖出
"""
import pandas as pd
from src.strategy.base import Strategy
from src.indicators.ta import sma


class DoubleMAStrategy(Strategy):
    def __init__(self, short_window: int = 20, long_window: int = 60):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window

    def initialize(self):
        """预计算均线"""
        print("Initializing Double MA Strategy...")
        self.ma_data = {}
        
        for symbol in self.ctx.stk_pool:
            df = self.get_data(symbol, "daily")
            if df.empty:
                continue
                
            # 计算指标
            df["short_ma"] = sma(df["close"], self.short_window)
            df["long_ma"] = sma(df["close"], self.long_window)
            
            # 生成信号
            # 金叉: 短线上穿长线
            # 死叉: 短线下穿长线
            # 同样需要对齐到当日可见
            df["golden_cross"] = (df["short_ma"] > df["long_ma"]) & (df["short_ma"].shift(1) <= df["long_ma"].shift(1))
            df["death_cross"] = (df["short_ma"] < df["long_ma"]) & (df["short_ma"].shift(1) >= df["long_ma"].shift(1))
            
            self.ma_data[symbol] = df

    def handle_data(self):
        """每日交易逻辑"""
        for symbol in self.ctx.stk_pool:
            if symbol not in self.ma_data:
                continue
                
            df = self.ma_data[symbol]
            current_date = pd.Timestamp(self.now)
            
            if current_date not in df.index:
                continue
                
            today_sig = df.loc[current_date]
            
            current_pos = self.ctx.positions.get(symbol, 0)
            
            # 1. 卖出信号
            if today_sig["death_cross"] and current_pos > 0:
                self.sell(symbol, current_pos, "Death Cross")
                
            # 2. 买入信号
            elif today_sig["golden_cross"] and current_pos == 0:
                # 全仓买入 (演示用，平均分配资金)
                # 假设只买一只
                # self.order_target(symbol, 0.9, "Golden Cross")
                # 或者如果有10只股，每只买 10%
                self.order_target(symbol, 0.1, "Golden Cross")
