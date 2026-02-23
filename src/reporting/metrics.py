"""
回测结果指标计算
"""

import math
import pandas as pd
import numpy as np
from typing import Dict, List, Deque
from collections import deque

from src.data.models import EquityPoint, TradeRecord


def compute_metrics(equity_curve: List[EquityPoint], trades: List[TradeRecord], initial_cash: float) -> Dict[str, float]:
    """
    计算回测核心指标
    """
    if not equity_curve:
        return {}
        
    # 转换为 DataFrame
    df = pd.DataFrame([{"date": p.date, "total_assets": p.total_assets} for p in equity_curve])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    
    # 1. 收益率
    final_equity = df["total_assets"].iloc[-1]
    total_return = (final_equity - initial_cash) / initial_cash
    
    # 年化收益率 (假设250个交易日)
    days = (df.index[-1] - df.index[0]).days
    if days > 0:
        annual_return = (1 + total_return) ** (365 / days) - 1
    else:
        annual_return = 0.0
        
    # 2. 最大回撤
    equity_series = df["total_assets"]
    roll_max = equity_series.cummax()
    drawdown = (equity_series - roll_max) / roll_max
    max_dd = drawdown.min() # 负数
    
    # 3. 波动率 (日收益率标准差 * sqrt(250))
    daily_returns = equity_series.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(250)
    
    # 4. 夏普比率 (无风险利率假设 0.03)
    sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0.0

    # 5. 胜率计算 (基于 FIFO 撮合)
    win_rate = _calculate_win_rate(trades)
    
    return {
        "总收益率": total_return,
        "年化收益率": annual_return,
        "最大回撤": max_dd,
        "波动率": volatility,
        "夏普比率": sharpe,
        "胜率": win_rate,
        "交易次数": len(trades)
    }

def _calculate_win_rate(trades: List[TradeRecord]) -> float:
    """
    计算胜率 (盈利交易次数 / 总平仓交易次数)
    使用 FIFO 方法匹配买卖记录
    """
    if not trades:
        return 0.0
        
    # symbol -> list of [price, quantity]
    long_positions: Dict[str, Deque[List[float]]] = {}
    closed_profits: List[float] = []
    
    for t in trades:
        if t.action == "BUY":
            if t.symbol not in long_positions:
                long_positions[t.symbol] = deque()
            long_positions[t.symbol].append([t.price, t.quantity])
            
        elif t.action == "SELL":
            if t.symbol not in long_positions or not long_positions[t.symbol]:
                continue
                
            qty_to_sell = t.quantity
            sell_price = t.price
            
            while qty_to_sell > 0 and long_positions[t.symbol]:
                buy_record = long_positions[t.symbol][0] # FIFO: take first
                buy_price = buy_record[0]
                buy_qty = buy_record[1]
                
                matched_qty = min(qty_to_sell, buy_qty)
                
                # 计算这部分匹配的盈亏
                profit = (sell_price - buy_price) * matched_qty
                closed_profits.append(profit)
                
                # 更新剩余数量
                qty_to_sell -= matched_qty
                buy_record[1] -= matched_qty
                
                if buy_record[1] <= 0:
                    long_positions[t.symbol].popleft()
                    
    if not closed_profits:
        return 0.0
        
    winning_trades = sum(1 for p in closed_profits if p > 0)
    return winning_trades / len(closed_profits)
