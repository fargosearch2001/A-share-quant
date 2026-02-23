"""
通用策略基类
提供标准化接口，简化策略开发
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd


class Context:
    """
    策略上下文，封装回测引擎的功能
    """
    def __init__(self, engine: Any):
        self._engine = engine

    @property
    def current_date(self):
        return self._engine.current_date

    @property
    def cash(self) -> float:
        return self._engine.cash

    @property
    def positions(self) -> Dict[str, int]:
        return self._engine.positions
        
    @property
    def stk_pool(self) -> List[str]:
        return self._engine.stk_pool

    def get_data(self, symbol: str, freq: str = "daily") -> pd.DataFrame:
        """获取全量历史数据"""
        return self._engine.loader.get_data(symbol, freq)
        
    def get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        return self._engine._get_current_price(symbol)

    def buy(self, symbol: str, quantity: int, note: str = "") -> bool:
        """买入"""
        return self._engine.buy(symbol, quantity, note)

    def sell(self, symbol: str, quantity: int, note: str = "") -> bool:
        """卖出"""
        return self._engine.sell(symbol, quantity, note)
        
    def order_target_percent(self, symbol: str, target_percent: float, note: str = "") -> bool:
        """
        按目标仓位下单
        target_percent: 目标仓位占总资产比例 (0.0 ~ 1.0)
        """
        if target_percent < 0 or target_percent > 1:
            print(f"Error: Target percent {target_percent} out of range [0, 1]")
            return False
            
        price = self.get_current_price(symbol)
        if not price or price <= 0:
            return False
            
        # 计算总资产
        total_assets = self.cash
        for s, qty in self.positions.items():
            p = self.get_current_price(s) or 0
            total_assets += p * qty
            
        target_value = total_assets * target_percent
        current_qty = self.positions.get(symbol, 0)
        current_value = current_qty * price
        
        diff_value = target_value - current_value
        
        # 最小交易单位 100
        diff_qty = int(diff_value / price / 100) * 100
        
        if diff_qty > 0:
            return self.buy(symbol, diff_qty, f"{note} (Target {target_percent:.1%})")
        elif diff_qty < 0:
            return self.sell(symbol, abs(diff_qty), f"{note} (Target {target_percent:.1%})")
        return True


class Strategy(ABC):
    def __init__(self):
        self.ctx: Optional[Context] = None

    def setup(self, engine: Any):
        """引擎调用的初始化方法"""
        self.ctx = Context(engine)
        self.initialize()

    def initialize(self) -> None:
        """
        [用户重写] 策略初始化
        通常用于预计算指标
        """
        pass

    def handle_data(self) -> None:
        """
        [用户重写] 每日交易逻辑
        """
        pass
        
    # --- 便捷属性与方法 ---
    
    @property
    def now(self):
        return self.ctx.current_date
        
    def buy(self, symbol: str, quantity: int, note: str = ""):
        return self.ctx.buy(symbol, quantity, note)
        
    def sell(self, symbol: str, quantity: int, note: str = ""):
        return self.ctx.sell(symbol, quantity, note)
        
    def order_target(self, symbol: str, percent: float, note: str = ""):
        return self.ctx.order_target_percent(symbol, percent, note)
        
    def get_data(self, symbol: str, freq: str = "daily"):
        return self.ctx.get_data(symbol, freq)
