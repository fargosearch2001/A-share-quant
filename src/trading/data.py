
import pandas as pd
import sys
from datetime import datetime, time
from typing import Optional, Dict
from src.data.loader import DataLoader
from src.config import DataConfig
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("警告: akshare 未安装，模拟盘实时行情不可用")
if AKSHARE_AVAILABLE and sys.version_info >= (3, 13):
    AKSHARE_AVAILABLE = False
    print("警告: 当前 Python 版本与 akshare 不兼容，已禁用实时行情")

class RealTimeDataLoader(DataLoader):
    def __init__(self, data_config: DataConfig):
        super().__init__(data_config)
        self._spot_cache: Optional[pd.DataFrame] = None
        self._spot_cache_time: Optional[datetime] = None

    def _refresh_spot_cache(self):
        """刷新实时行情缓存 (1分钟有效期)"""
        if not AKSHARE_AVAILABLE:
            return
        now = datetime.now()
        if self._spot_cache is None or self._spot_cache_time is None or (now - self._spot_cache_time).seconds > 60:
            print("Refreshing real-time spot data...")
            try:
                self._spot_cache = ak.stock_zh_a_spot_em()
                self._spot_cache_time = now
            except Exception as e:
                print(f"Error refreshing spot data: {e}")

    def get_current_price(self, symbol: str) -> float:
        """
        获取实时/最新价格
        """
        if not AKSHARE_AVAILABLE:
            return 0.0
        code = symbol.split(".")[0]
        
        # 1. 尝试从 akshare 日线接口获取今日收盘价 (如果已收盘)
        # 这通常比 spot 接口慢，但数据更准。为了性能，我们优先用 spot 接口 (假设在盘中或刚收盘)
        
        # 使用批量接口获取所有行情
        self._refresh_spot_cache()
        
        if self._spot_cache is not None:
            # akshare spot 接口返回的代码列通常是 6位数字
            row = self._spot_cache[self._spot_cache["代码"] == code]
            if not row.empty:
                return float(row.iloc[0]["最新价"])
        
        return 0.0

    def get_data(self, symbol: str, freq: str = "daily") -> pd.DataFrame:
        """
        获取数据，并尝试追加今日实时数据（如果历史数据中没有）
        """
        # 确保加载了历史数据
        if symbol not in self.daily_data:
            self.load_all([symbol])
            
        df = self.daily_data.get(symbol, pd.DataFrame()).copy()
        
        if df.empty:
            return df
            
        last_date = df.index[-1].date()
        today = datetime.now().date()
        
        # 如果历史数据没包含今天，尝试追加
        if last_date < today:
            current_price = self.get_current_price(symbol)
            if current_price > 0:
                # 构造临时行
                new_row = pd.DataFrame({
                    "open": [current_price],
                    "high": [current_price],
                    "low": [current_price],
                    "close": [current_price],
                    "volume": [0]
                }, index=[pd.Timestamp(today)])
                
                # 简单处理：如果 index 重复则覆盖，否则追加
                # 但这里明确 last_date < today，所以是追加
                df = pd.concat([df, new_row])
                
        return df
