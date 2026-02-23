"""
技术指标库 (基于 Pandas)
"""

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=window, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 指标"""
    exp1 = ema(series, fast)
    exp2 = ema(series, slow)
    dif = exp1 - exp2
    dea = ema(dif, signal)
    macd_bar = (dif - dea) * 2
    return dif, dea, macd_bar


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    """布林带"""
    mid = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = mid + (std * num_std)
    lower = mid - (std * num_std)
    return upper, mid, lower
