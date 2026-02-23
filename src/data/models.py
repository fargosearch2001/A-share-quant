"""
数据模型定义
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class TradeRecord:
    """交易记录"""
    date: date
    symbol: str
    action: str  # BUY, SELL
    price: float
    quantity: int
    commission: float
    note: str = ""


@dataclass
class EquityPoint:
    """权益曲线点"""
    date: date
    total_assets: float
    cash: float
    market_value: float
