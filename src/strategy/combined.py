"""
组合策略（分仓管理）
同时运行两个子策略，每个策略独立管理分配的资金
"""

import pandas as pd
from typing import Dict, Any, List
from src.strategy.base import Strategy


class CombinedStrategy(Strategy):
    """
    组合策略 - 分仓管理
    
    同时运行两个子策略，每个子策略独立判断买卖信号。
    两个策略共享资金账户，但通过仓位比例控制各自的使用资金。
    策略A 使用 fund_ratio_a 的仓位上限，策略B 使用 fund_ratio_b 的仓位上限。
    """
    
    def __init__(self, 
                 strategy_a: Strategy,
                 strategy_b: Strategy,
                 fund_ratio_a: float = 0.5,
                 fund_ratio_b: float = 0.5):
        super().__init__()
        
        # 参数验证
        if abs(fund_ratio_a + fund_ratio_b - 1.0) > 0.001:
            raise ValueError(f"资金比例总和必须为1，当前: {fund_ratio_a} + {fund_ratio_b} = {fund_ratio_a + fund_ratio_b}")
        
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.fund_ratio_a = fund_ratio_a
        self.fund_ratio_b = fund_ratio_b
        
        # 记录当前运行的策略（用于 Context 包装）
        self._current_strategy = None
        self._strategy_ratio = None
        
        # 各自的目标持仓（用于风控）
        self._target_positions_a: Dict[str, float] = {}  # symbol -> target ratio
        self._target_positions_b: Dict[str, float] = {}
        
    def setup(self, ctx) -> None:
        """初始化两个子策略
        
        注意：子策略的 initialize() 不接受参数，它们通过 self.ctx 访问上下文
        这里我们将 ctx 赋值给子策略的 ctx 属性
        """
        print(f"Initializing Combined Strategy: A={self.fund_ratio_a:.0%}, B={self.fund_ratio_b:.0%}")
        
        # 创建子策略的 Context 包装器
        ctx_a = SubStrategyContext(ctx, self, "A", self.fund_ratio_a)
        ctx_b = SubStrategyContext(ctx, self, "B", self.fund_ratio_b)
        
        # 初始化子策略A - 直接设置 ctx 属性，不传参数
        self.strategy_a.ctx = ctx_a
        if hasattr(self.strategy_a, 'setup'):
            self.strategy_a.setup(ctx_a)
        elif hasattr(self.strategy_a, 'initialize'):
            self.strategy_a.initialize()
        
        # 初始化子策略B - 直接设置 ctx 属性
        self.strategy_b.ctx = ctx_b
        if hasattr(self.strategy_b, 'setup'):
            self.strategy_b.setup(ctx_b)
        elif hasattr(self.strategy_b, 'initialize'):
            self.strategy_b.initialize()
    
    def handle_data(self) -> None:
        """每日交易逻辑：两个子策略分别独立处理"""
        # 策略A处理（如果占比>0）
        if self.fund_ratio_a > 0:
            self._current_strategy = "A"
            self._strategy_ratio = self.fund_ratio_a
            if hasattr(self.strategy_a, 'handle_data'):
                self.strategy_a.handle_data()
        
        # 策略B处理（如果占比>0）
        if self.fund_ratio_b > 0:
            self._current_strategy = "B"
            self._strategy_ratio = self.fund_ratio_b
            if hasattr(self.strategy_b, 'handle_data'):
                self.strategy_b.handle_data()
        
        self._current_strategy = None
        self._strategy_ratio = None
    
    def get_current_strategy(self) -> str:
        return self._current_strategy
    
    def get_strategy_ratio(self) -> float:
        return self._strategy_ratio or 0.5


class SubStrategyContext:
    """子策略的 Context 包装器"""
    
    def __init__(self, parent_ctx, combined_strategy: CombinedStrategy, 
                 strategy_id: str, fund_ratio: float):
        self._parent = parent_ctx
        self._combined = combined_strategy
        self._strategy_id = strategy_id  # "A" or "B"
        self._fund_ratio = fund_ratio
    
    @property
    def stk_pool(self):
        return self._parent.stk_pool
    
    @property
    def cash(self):
        """可用的现金（总现金）"""
        return self._parent.cash
    
    @property
    def positions(self):
        return self._parent.positions
    
    @property
    def now(self):
        return self._parent.now
    
    @property
    def current_date(self):
        """当前日期"""
        return self._parent.current_date
    
    @property
    def loader(self):
        """数据加载器"""
        return self._parent.loader
    
    def get_data(self, symbol: str, freq: str = "daily"):
        return self._parent.get_data(symbol, freq)
    
    def get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        return self._parent.get_current_price(symbol)
    
    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格（内部方法）"""
        return self._parent._get_current_price(symbol)
    
    def _get_last_price(self, symbol: str) -> float:
        """获取最近收盘价"""
        return self._parent._get_last_price(symbol)
    
    def buy(self, symbol: str, quantity: int, note: str = ""):
        """买入（带策略标记）"""
        if quantity <= 0:
            return False
        marked_note = f"[策略{self._strategy_id}-{self._fund_ratio:.0%}] {note}"
        return self._parent.buy(symbol, quantity, marked_note)
    
    def sell(self, symbol: str, quantity: int, note: str = ""):
        """卖出（带策略标记）"""
        if quantity <= 0:
            return False
        marked_note = f"[策略{self._strategy_id}-{self._fund_ratio:.0%}] {note}"
        return self._parent.sell(symbol, quantity, marked_note)
    
    def order_target(self, symbol: str, target_percent: float, note: str = ""):
        """
        目标仓位下单
        
        target_percent: 子策略想使用的仓位比例（相对于分配的资金）
        
        例如：策略A分配50%资金，想买分配资金的10%
        -> 实际应买总资金的 10% × 50% = 5%
        
        如果某个策略占比为100%，则该策略可以使用全部资金（不受限制）
        """
        # 如果某个策略占比为100%（考虑浮点数精度），则直接使用目标仓位比例
        if self._fund_ratio >= 0.99:
            # 策略占比100%，直接使用全部资金
            adjusted_percent = target_percent
        elif self._fund_ratio <= 0.01:
            # 策略占比0%，不进行任何交易
            return False
        else:
            # 按比例分配资金
            adjusted_percent = target_percent * self._fund_ratio
        
        # 直接调用父级方法
        marked_note = f"[策略{self._strategy_id}-{self._fund_ratio:.0%}] {note}"
        return self._parent.order_target(symbol, adjusted_percent, marked_note)
