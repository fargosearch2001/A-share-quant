"""
技术指标库 (基于 Pandas)
"""

import pandas as pd
try:
    import pandas_ta as ta
    _HAS_TA = True
except Exception:
    _HAS_TA = False


def sma(series: pd.Series, window: int) -> pd.Series:
    if _HAS_TA:
        return ta.sma(series, length=window)
    return series.rolling(window=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    if _HAS_TA:
        return ta.ema(series, length=window)
    return series.ewm(span=window, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    if _HAS_TA:
        macd_df = ta.macd(series, fast=fast, slow=slow, signal=signal)
        if macd_df is None or macd_df.empty:
            return series * 0, series * 0, series * 0
        dif = macd_df.iloc[:, 0]
        dea = macd_df.iloc[:, 2]
        macd_bar = macd_df.iloc[:, 1] * 2
        return dif, dea, macd_bar
    exp1 = ema(series, fast)
    exp2 = ema(series, slow)
    dif = exp1 - exp2
    dea = ema(dif, signal)
    macd_bar = (dif - dea) * 2
    return dif, dea, macd_bar


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    if _HAS_TA:
        bbands = ta.bbands(series, length=window, std=num_std)
        if bbands is None or bbands.empty:
            return series * 0, series * 0, series * 0
        lower = bbands.iloc[:, 0]
        mid = bbands.iloc[:, 1]
        upper = bbands.iloc[:, 2]
        return upper, mid, lower
    mid = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = mid + (std * num_std)
    lower = mid - (std * num_std)
    return upper, mid, lower
