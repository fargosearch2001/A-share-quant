"""
月线趋势与估值轮动策略
基于 Pandas 向量化计算指标，事件驱动回测
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

from src.strategy.base import Strategy
from src.indicators.ta import sma, macd, bollinger_bands


class MonthlyTrendDividendRotation(Strategy):
    def __init__(self, 
                 ma_month_window: int = 60,
                 boll_window: int = 20,
                 dividend_buy_threshold: float = 0.045,
                 dividend_sell_thresholds: Dict[float, float] = {0.037: 0.5, 0.035: 0.66, 0.030: 1.0}):
        super().__init__()
        self.ma_month_window = ma_month_window
        self.boll_window = boll_window
        self.dividend_buy_threshold = dividend_buy_threshold
        self.dividend_sell_thresholds = dividend_sell_thresholds
        
        # 预计算的信号表: symbol -> DataFrame (index=date)
        self.signals: Dict[str, pd.DataFrame] = {}

    def initialize(self) -> None:
        """
        预计算所有技术指标和信号
        """
        print("Initializing strategy: Pre-calculating indicators...")
        for symbol in self.ctx.stk_pool:
            daily_df = self.get_data(symbol, "daily")
            weekly_df = self.get_data(symbol, "weekly")
            monthly_df = self.get_data(symbol, "monthly")
            
            if daily_df.empty or weekly_df.empty or monthly_df.empty:
                continue
                
            # --- 1. 月线指标 ---
            # MA60
            monthly_df["ma60"] = sma(monthly_df["close"], self.ma_month_window)
            # MA5, 10, 20, 30
            for w in [5, 10, 20, 30]:
                monthly_df[f"ma{w}"] = sma(monthly_df["close"], w)
            # MACD
            _, _, monthly_df["macd_bar"] = macd(monthly_df["close"])
            
            # --- 2. 周线指标 ---
            # MA60, 20, 30
            weekly_df["ma60"] = sma(weekly_df["close"], 60)
            weekly_df["ma20"] = sma(weekly_df["close"], 20)
            weekly_df["ma30"] = sma(weekly_df["close"], 30)
            
            # --- 3. 日线指标 ---
            # BOLL
            _, daily_df["boll_mid"], _ = bollinger_bands(daily_df["close"], self.boll_window)
            
            # --- 4. 信号生成与对齐 ---
            # 辅助函数: 安全扩展到日线
            def expand_to_daily(src_df, target_index):
                return src_df.reindex(target_index, method='ffill')

            # 准备信号表
            sig_df = pd.DataFrame(index=daily_df.index)
            sig_df["close"] = daily_df["close"]
            sig_df["boll_mid"] = daily_df["boll_mid"]
            sig_df["dividend_yield"] = daily_df["dividend_yield"]
            
            # 扩展月线指标
            m_aligned = expand_to_daily(monthly_df, daily_df.index)
            sig_df["ma60_month"] = m_aligned["ma60"]
            sig_df["macd_bar_month"] = m_aligned["macd_bar"]
            sig_df["ma5_month"] = m_aligned["ma5"]
            sig_df["ma10_month"] = m_aligned["ma10"]
            sig_df["ma20_month"] = m_aligned["ma20"]
            sig_df["ma30_month"] = m_aligned["ma30"]
            
            # 扩展周线指标
            w_aligned = expand_to_daily(weekly_df, daily_df.index)
            sig_df["ma60_week"] = w_aligned["ma60"]
            sig_df["ma20_week"] = w_aligned["ma20"]
            sig_df["ma30_week"] = w_aligned["ma30"]
            sig_df["close_week"] = w_aligned["close"] # 上周收盘价
            
            # --- 计算信号逻辑 ---
            
            # 信号 A: 月线反转
            # 条件: 日收盘 > 月MA60 (使用最近的MA60作为参考)
            # 且 之前是跌破状态 (上月收盘 < 上月MA60)
            sig_df["signal_A_condition"] = (sig_df["close"] > sig_df["ma60_month"]) & \
                                           (m_aligned["close"] < m_aligned["ma60"])
                                           
            # 信号 A2: BOLL 回踩
            # close 在 [0.97 * mid, 1.01 * mid]
            sig_df["signal_A_pullback"] = (sig_df["close"] >= sig_df["boll_mid"] * 0.97) & \
                                          (sig_df["close"] <= sig_df["boll_mid"] * 1.01)
            
            # 信号 B: 趋势调整结束
            # 1. 月线多头排列
            monthly_trend = (sig_df["ma5_month"] > sig_df["ma10_month"]) & \
                            (sig_df["ma10_month"] > sig_df["ma20_month"]) & \
                            (sig_df["ma20_month"] > sig_df["ma30_month"])
            # 2. 月线调整 (MACD < 0) -> 实际上策略说的是 MACD bar 转正
            macd_turning_red = (sig_df["macd_bar_month"] > 0)
            
            # 3. 周线突破
            week_break = (sig_df["close"] > sig_df["ma60_week"])
            
            # 4. 周线均线金叉 (20上穿60, 30上穿60)
            week_cross = (sig_df["ma20_week"] > sig_df["ma60_week"]) & (sig_df["ma30_week"] > sig_df["ma60_week"])
            
            sig_df["signal_B_condition"] = monthly_trend & macd_turning_red & week_break & week_cross
            
            self.signals[symbol] = sig_df

    def handle_data(self) -> None:
        """
        每日交易逻辑
        """
        current_date = pd.Timestamp(self.now)
        
        for symbol in self.ctx.stk_pool:
            # 获取该股今日信号
            if symbol not in self.signals:
                continue
            try:
                # 使用 asof 查找最近的信号 (处理停牌日)
                if current_date not in self.signals[symbol].index:
                    continue
                
                sig = self.signals[symbol].loc[current_date]
            except KeyError:
                continue
                
            # 0. 仓位与股息
            current_pos = self.ctx.positions.get(symbol, 0)
            dy = sig["dividend_yield"]
            
            # 1. 卖出逻辑 (估值驱动)
            if current_pos > 0:
                self._handle_sell(symbol, dy, current_pos)
            
            # 2. 买入逻辑
            # 只有当现金充足且没有满仓该股时 (这里简单假设只要有钱就买)
            if self.ctx.cash > 0: # 简化判断
                buy_signal = False
                note = ""
                
                # 信号 A
                if sig["signal_A_condition"] and sig["signal_A_pullback"]:
                    buy_signal = True
                    note = "Signal A: Trend Start + Pullback"
                    
                # 信号 B
                elif sig["signal_B_condition"]:
                    buy_signal = True
                    note = "Signal B: Trend Correction End"
                    
                # 股息率门槛
                if buy_signal and dy >= self.dividend_buy_threshold:
                    # 执行买入
                    # 使用 target percent 简化资金管理: 每次分配 10% 总资金
                    self.order_target(symbol, 0.1, note)

    def _handle_sell(self, symbol, dy, current_pos):
        """
        根据股息率阶梯减仓
        """
        if dy < 0.030:
            self.sell(symbol, current_pos, "Valuation Sell: Clear (DY < 3%)")
