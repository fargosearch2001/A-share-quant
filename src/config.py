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

# 股票代码到名称的映射
STOCK_NAMES = {
    '000001.SZ': '平安银行',
    '000538.SZ': '云南白药',
    '003816.SZ': '中国广核',
    '601985.SS': '中国核电',
    '600690.SS': '海尔智家',
    '601066.SS': '中信建投',
    '600030.SS': '中信证券',
    '600309.SS': '万华化学',
    '600036.SS': '招商银行',
    '600887.SS': '伊利股份',
    '000333.SZ': '美的集团',
    '000651.SZ': '格力电器',
    '601728.SS': '中国电信',
    '600886.SS': '国投电力',
    '601857.SS': '中国石油',
    '601919.SS': '中远海控',
    '600519.SS': '贵州茅台',
    '000858.SZ': '五粮液'
}

def get_stock_display_name(code: str) -> str:
    """
    获取股票的显示名称（代码 - 名称）
    """
    name = STOCK_NAMES.get(code, '未知')
    return f"{code} - {name}"