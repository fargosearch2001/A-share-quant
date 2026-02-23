"""
数据加载与处理模块
负责从 AkShare 加载数据、计算股息、重采样生成周/月线数据
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import DataConfig


class DataLoader:
    def __init__(self, data_config: DataConfig):
        self.config = data_config
        self.daily_data: Dict[str, pd.DataFrame] = {}
        self.weekly_data: Dict[str, pd.DataFrame] = {}
        self.monthly_data: Dict[str, pd.DataFrame] = {}
        self.dividend_data: Dict[str, pd.DataFrame] = {}

    def load_all(self, symbols: List[str]) -> None:
        """
        加载指定股票列表的所有数据
        """
        for symbol in symbols:
            print(f"Loading data for {symbol}...")
            # 提取纯数字代码用于 akshare
            code = symbol.split(".")[0]
            
            # 1. 获取日线数据 (前复权)
            try:
                # 默认获取从 2010 年开始的数据，确保有足够的历史用于计算 MA60 月线
                df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20100101", adjust="qfq")
                if df.empty:
                    print(f"Warning: No data for {symbol}")
                    continue
                    
                # 重命名列
                df = df.rename(columns={
                    "日期": "date",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "volume",
                    "成交额": "amount"
                })
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                
                # 2. 获取分红数据并计算股息率
                # 注意：akshare 的分红数据是“派息(税前)(元)”，通常是每10股派息
                div_df = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
                # 预处理分红数据
                div_df["除权除息日"] = pd.to_datetime(div_df["除权除息日"], errors='coerce')
                div_df = div_df.dropna(subset=["除权除息日"]).sort_values("除权除息日")
                # 转换为每股分红 (原数据通常为每10股)
                div_df["dividend_per_share"] = div_df["派息"] / 10.0
                self.dividend_data[symbol] = div_df
                
                # 计算每日的滚动年度分红 (Trailing 12M Dividends)
                # 优化: 创建连续日历索引以包含非交易日的分红
                full_idx = pd.date_range(start=df.index.min(), end=df.index.max())
                daily_div_full = pd.Series(0.0, index=full_idx)
                
                for _, row in div_df.iterrows():
                    d_date = row["除权除息日"]
                    if d_date >= full_idx.min() and d_date <= full_idx.max():
                        daily_div_full.loc[d_date] += row["dividend_per_share"]
                
                # 在连续日历上计算滚动和
                rolling_div_full = daily_div_full.rolling(window='365D', min_periods=1).sum()
                
                # 对齐回交易日索引
                rolling_div = rolling_div_full.reindex(df.index, method='ffill')
                
                # 计算股息率 = 滚动年度分红 / 当前收盘价
                df["dividend_yield"] = rolling_div / df["close"]
                
                self.daily_data[symbol] = df
                
                # 3. 生成周线
                # resample 规则: W-FRI 表示每周五结束
                weekly_df = df.resample('W-FRI').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'dividend_yield': 'last' # 使用这周最后一天的股息率
                })
                # 只有当周有数据时才保留 (去除因停牌等导致的空行，但 resample 默认不会产生空行除非全是NaN)
                weekly_df = weekly_df.dropna(subset=['close'])
                self.weekly_data[symbol] = weekly_df
                
                # 4. 生成月线
                monthly_df = df.resample('ME').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'dividend_yield': 'last'
                })
                monthly_df = monthly_df.dropna(subset=['close'])
                self.monthly_data[symbol] = monthly_df
                
            except Exception as e:
                print(f"Error loading {symbol}: {e}")
                import traceback
                traceback.print_exc()

    def get_data(self, symbol: str, freq: str = "daily") -> pd.DataFrame:
        if freq == "daily":
            return self.daily_data.get(symbol, pd.DataFrame())
        elif freq == "weekly":
            return self.weekly_data.get(symbol, pd.DataFrame())
        elif freq == "monthly":
            return self.monthly_data.get(symbol, pd.DataFrame())
        return pd.DataFrame()
