"""
全局配置模块
"""

from dataclasses import dataclass


@dataclass
class BacktestConfig:
    """
    回测参数配置
    """
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003  # 万三佣金
    slippage: float = 0.001          # 千一滑点 (双向)
    trade_lot: int = 100             # 最小交易单位


@dataclass
class DataConfig:
    """
    数据源配置
    """
    csv_path: str = "data"           # 数据文件目录
    date_format: str = "%Y-%m-%d"    # 日期格式


# 策略 Demo 中的固定股票池
# 注意: AkShare 使用 6 位数字代码
STOCK_POOL = [
    '000001.SZ', '000538.SZ', '003816.SZ', 
    '601985.SS', '600690.SS', '601066.SS', 
    '600030.SS', '600309.SS', '600036.SS', 
    '600887.SS', '000333.SZ', '000651.SZ', 
    '601728.SS', '600886.SS', '601857.SS', 
    '601919.SS', '600519.SS', '000858.SZ'
]
