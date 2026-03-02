"""
数据加载与处理模块
负责从多个数据源加载数据、计算股息、重采样生成周/月线数据
支持的数据源：AkShare (东方财富), BaoStock (证券宝)
"""

import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import DataConfig

# 尝试导入各个数据源
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("警告: akshare 未安装，将跳过该数据源")

try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False
    print("警告: baostock 未安装，将跳过该数据源")

# 禁用代理以避免连接问题
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''


class DataLoader:
    def __init__(self, data_config: DataConfig):
        self.config = data_config
        self.daily_data: Dict[str, pd.DataFrame] = {}
        self.weekly_data: Dict[str, pd.DataFrame] = {}
        self.monthly_data: Dict[str, pd.DataFrame] = {}
        self.dividend_data: Dict[str, pd.DataFrame] = {}
        self.baostock_logged_in = False
    
    def _fetch_with_retry(self, func, max_retries=3, delay=1, *args, **kwargs):
        """
        带重试机制的数据获取函数
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (ConnectionError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = delay * (attempt + 1)  # 递增延迟
                    print(f"  重试 {attempt + 1}/{max_retries}，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                else:
                    raise e
    
    def _convert_code_for_baostock(self, symbol: str) -> Tuple[str, str]:
        """
        将股票代码转换为 baostock 格式
        返回: (股票代码, 市场代码)
        """
        code = symbol.split(".")[0]
        if symbol.endswith(".SS") or code.startswith("6"):
            return f"sh.{code}", "sh"
        else:
            return f"sz.{code}", "sz"
    
    def _fetch_from_akshare(self, code: str, start_date: str = "20100101") -> Optional[pd.DataFrame]:
        """
        从 AkShare 获取数据，尝试多个接口
        按顺序尝试：stock_zh_a_daily -> stock_zh_a_hist_tx -> stock_zh_a_hist
        优先使用新浪财经，成功后不再尝试其他接口
        """
        if not AKSHARE_AVAILABLE:
            return None
        
        # 方法1: stock_zh_a_daily (新浪财经) - 优先
        try:
            print(f"  尝试 akshare.stock_zh_a_daily (新浪财经)...")
            # 需要转换代码格式：sh600000 或 sz000001
            market_code = f"sh{code}" if code.startswith("6") else f"sz{code}"
            df = self._fetch_with_retry(
                ak.stock_zh_a_daily,
                max_retries=2,
                delay=1,
                symbol=market_code,
                adjust="qfq"
            )
            if df is not None and not df.empty:
                print(f"  ✓ akshare.stock_zh_a_daily 成功")
                return df
        except Exception as e:
            print(f"  ✗ akshare.stock_zh_a_daily 失败: {str(e)[:60]}")
        
        # 方法2: stock_zh_a_hist_tx (腾讯财经) - 备选1
        try:
            print(f"  尝试 akshare.stock_zh_a_hist_tx (腾讯财经)...")
            df = self._fetch_with_retry(
                ak.stock_zh_a_hist_tx,
                max_retries=2,
                delay=1,
                symbol=code,
                period="daily",
                adjust="qfq"
            )
            if df is not None and not df.empty:
                print(f"  ✓ akshare.stock_zh_a_hist_tx 成功")
                return df
        except Exception as e:
            print(f"  ✗ akshare.stock_zh_a_hist_tx 失败: {str(e)[:60]}")
        
        # 方法3: stock_zh_a_hist (东方财富) - 备选2
        try:
            print(f"  尝试 akshare.stock_zh_a_hist (东方财富)...")
            df = self._fetch_with_retry(
                ak.stock_zh_a_hist,
                max_retries=2,
                delay=2,
                symbol=code,
                period="daily",
                start_date=start_date,
                adjust="qfq"
            )
            if df is not None and not df.empty:
                print(f"  ✓ akshare.stock_zh_a_hist 成功")
                return df
        except Exception as e:
            print(f"  ✗ akshare.stock_zh_a_hist 失败: {str(e)[:60]}")
        
        # 所有 akshare 接口都失败
        return None
    
    def _fetch_from_baostock(self, symbol: str, start_date: str = "2010-01-01") -> Optional[pd.DataFrame]:
        """
        从 BaoStock (证券宝) 获取数据
        """
        if not BAOSTOCK_AVAILABLE:
            return None
        
        try:
            # 登录 baostock (只需要登录一次)
            if not self.baostock_logged_in:
                lg = bs.login()
                if lg.error_code != '0':
                    print(f"  ✗ BaoStock 登录失败: {lg.error_msg}")
                    return None
                self.baostock_logged_in = True
            
            print(f"  尝试使用 BaoStock (证券宝) 接口...")
            bs_code, market = self._convert_code_for_baostock(symbol)
            
            # 获取数据
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,preclose,volume,amount,adjustflag",
                start_date=start_date,
                end_date=datetime.now().strftime("%Y-%m-%d"),
                frequency="d",
                adjustflag="3"  # 前复权
            )
            
            if rs.error_code != '0':
                print(f"  ✗ BaoStock 接口失败: {rs.error_msg}")
                return None
            
            # 转换为 DataFrame
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                print(f"  ✗ BaoStock 返回空数据")
                return None
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换数据类型
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 重命名列以匹配标准格式
            df = df.rename(columns={
                'date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'amount': 'amount'
            })
            
            # 只保留需要的列
            df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            df = df.set_index('date').sort_index()
            
            print(f"  ✓ BaoStock 接口成功，获取 {len(df)} 条数据")
            return df
            
        except Exception as e:
            print(f"  ✗ BaoStock 接口异常: {str(e)[:80]}")
            return None
    
    def _fetch_stock_data_multiple_sources(self, code: str, symbol: str, start_date: str = "20100101") -> pd.DataFrame:
        """
        尝试多个数据源获取股票数据
        按优先级顺序尝试：AkShare -> BaoStock
        """
        # 转换日期格式
        start_date_bs = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        
        # 方法1: 尝试 AkShare
        df = self._fetch_from_akshare(code, start_date)
        if df is not None and not df.empty:
            return df
        
        # 方法2: 尝试 BaoStock
        df = self._fetch_from_baostock(symbol, start_date_bs)
        if df is not None and not df.empty:
            return df
        
        # 所有数据源都失败
        raise Exception(f"无法从任何数据源获取 {symbol} 的数据。请检查网络连接或稍后重试。")

    
    def load_all(self, symbols: List[str]) -> None:
        """
        加载指定股票列表的所有数据
        """
        print("=" * 60)
        print("数据源状态:")
        print(f"  - AkShare (东方财富): {'可用' if AKSHARE_AVAILABLE else '未安装'}")
        print(f"  - BaoStock (证券宝): {'可用' if BAOSTOCK_AVAILABLE else '未安装'}")
        print("=" * 60)
        
        if not AKSHARE_AVAILABLE and not BAOSTOCK_AVAILABLE:
            raise Exception("错误: 没有可用的数据源！请安装 akshare 或 baostock")
        
        success_count = 0
        fail_count = 0
        
        for symbol in symbols:
            print(f"\nLoading data for {symbol}...")
            # 提取纯数字代码
            code = symbol.split(".")[0]
            
            # 1. 获取日线数据 (前复权)
            try:
                # 尝试多个数据源
                df = self._fetch_stock_data_multiple_sources(code, symbol, start_date="20100101")
                if df.empty:
                    print(f"Warning: No data for {symbol}")
                    fail_count += 1
                    continue
                
                # 请求成功后添加延迟，避免请求过快
                time.sleep(0.3)
                    
                # 重命名列（统一列名格式）
                if "日期" in df.columns:
                    # akshare 返回的中文列名
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
                elif "date" in df.columns and df.index.name != "date":
                    # baostock 或其他数据源已经有 date 列但还不是索引
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                # 如果已经是 date 索引，确保列名正确
                if df.index.name == "date" or isinstance(df.index, pd.DatetimeIndex):
                    # 确保列名是英文
                    column_mapping = {}
                    if "开盘" in df.columns:
                        column_mapping["开盘"] = "open"
                    if "收盘" in df.columns:
                        column_mapping["收盘"] = "close"
                    if "最高" in df.columns:
                        column_mapping["最高"] = "high"
                    if "最低" in df.columns:
                        column_mapping["最低"] = "low"
                    if "成交量" in df.columns:
                        column_mapping["成交量"] = "volume"
                    if "成交额" in df.columns:
                        column_mapping["成交额"] = "amount"
                    if column_mapping:
                        df = df.rename(columns=column_mapping)
                
                # 2. 获取分红数据并计算股息率
                # 注意：分红数据主要从 akshare 获取，如果 akshare 不可用则跳过
                div_df = pd.DataFrame(columns=["除权除息日", "派息"])
                if AKSHARE_AVAILABLE:
                    try:
                        div_df = self._fetch_with_retry(
                            ak.stock_history_dividend_detail,
                            max_retries=2,
                            delay=1,
                            symbol=code,
                            indicator="分红"
                        )
                        time.sleep(0.3)  # 添加延迟
                    except Exception as e:
                        print(f"  Warning: 无法获取 {symbol} 的分红数据: {str(e)[:60]}")
                        div_df = pd.DataFrame(columns=["除权除息日", "派息"])
                # 预处理分红数据
                if not div_df.empty and "除权除息日" in div_df.columns:
                    div_df["除权除息日"] = pd.to_datetime(div_df["除权除息日"], errors='coerce')
                    div_df = div_df.dropna(subset=["除权除息日"]).sort_values("除权除息日")
                    # 转换为每股分红 (原数据通常为每10股)
                    if "派息" in div_df.columns:
                        div_df["dividend_per_share"] = div_df["派息"] / 10.0
                    else:
                        div_df["dividend_per_share"] = 0.0
                else:
                    div_df = pd.DataFrame(columns=["除权除息日", "dividend_per_share"])
                self.dividend_data[symbol] = div_df
                
                # 计算每日的滚动年度分红 (Trailing 12M Dividends)
                # 优化: 创建连续日历索引以包含非交易日的分红
                if not div_df.empty and "除权除息日" in div_df.columns and "dividend_per_share" in div_df.columns:
                    full_idx = pd.date_range(start=df.index.min(), end=df.index.max())
                    daily_div_full = pd.Series(0.0, index=full_idx)
                    
                    for _, row in div_df.iterrows():
                        d_date = row["除权除息日"]
                        if pd.notna(d_date) and d_date >= full_idx.min() and d_date <= full_idx.max():
                            daily_div_full.loc[d_date] += row["dividend_per_share"]
                    
                    # 在连续日历上计算滚动和
                    rolling_div_full = daily_div_full.rolling(window='365D', min_periods=1).sum()
                    
                    # 对齐回交易日索引
                    rolling_div = rolling_div_full.reindex(df.index, method='ffill')
                    
                    # 计算股息率 = 滚动年度分红 / 当前收盘价
                    df["dividend_yield"] = rolling_div / df["close"]
                else:
                    # 如果没有分红数据，股息率为 0
                    df["dividend_yield"] = 0.0
                
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
                
                print(f"  ✓ 成功加载 {symbol} 的数据")
                success_count += 1
                
            except Exception as e:
                print(f"  ✗ 加载 {symbol} 失败: {e}")
                fail_count += 1
                # 不打印完整堆栈跟踪，只打印错误信息
                continue
        
        # 输出统计信息
        print(f"\n{'='*60}")
        print(f"数据加载完成: 成功 {success_count} 只, 失败 {fail_count} 只")
        print(f"{'='*60}")
        
        if fail_count > 0:
            print("\n⚠️  提示: 如果接口持续失败，可以:")
            print("  1. 检查网络连接")
            print("  2. 稍后重试（可能是接口临时限制）")
            print("  3. 确保已安装所有数据源: pip install akshare baostock")
        
        # 退出 baostock 登录
        if self.baostock_logged_in and BAOSTOCK_AVAILABLE:
            bs.logout()

    def get_data(self, symbol: str, freq: str = "daily") -> pd.DataFrame:
        if freq == "daily":
            return self.daily_data.get(symbol, pd.DataFrame())
        elif freq == "weekly":
            return self.weekly_data.get(symbol, pd.DataFrame())
        elif freq == "monthly":
            return self.monthly_data.get(symbol, pd.DataFrame())
        return pd.DataFrame()
