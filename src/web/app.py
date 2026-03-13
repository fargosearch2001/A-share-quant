"""
量化回测系统 Web 可视化界面
基于 Streamlit 和 Plotly 构建
"""

import sys
import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import date, datetime

# 添加项目根目录到 sys.path，确保能导入 src 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.config import BacktestConfig, DataConfig, STOCK_POOL, get_stock_display_name
from src.data.loader import DataLoader
from src.data.stock_list import get_a_stock_list, search_stocks
from src.backtest.engine import BacktestEngine
from src.strategy.monthly_trend_rotation import MonthlyTrendDividendRotation
from src.strategy.double_ma import DoubleMAStrategy
from src.strategy.combined import CombinedStrategy
from src.reporting.metrics import compute_metrics
from src.indicators.ta import bollinger_bands
from src.trading.data import RealTimeDataLoader
from src.trading.broker import SimulatedBroker
from src.trading.engine import PaperTradingEngine
from src.trading.vnpy_runner import start_vnpy_engine

try:
    from src.backtest.backtrader_engine import BacktraderEngine
    BACKTRADER_AVAILABLE = True
except Exception:
    BACKTRADER_AVAILABLE = False

try:
    import pyfolio as pf
    PYFOLIO_AVAILABLE = True
except Exception:
    PYFOLIO_AVAILABLE = False

if not hasattr(np, "NINF"):
    np.NINF = -np.inf
if not hasattr(np, "PINF"):
    np.PINF = np.inf

try:
    import vnpy
    VNPY_AVAILABLE = True
except Exception:
    VNPY_AVAILABLE = False


# --- 页面配置 ---
st.set_page_config(
    page_title="投滚量化回测系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 样式优化 ---
st.markdown("""
<style>
    /* 全局字体与背景 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    .stApp {
        background-color: #f8fafc;
    }
    
    /* 侧边栏美化 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
        box-shadow: 4px 0 24px rgba(0,0,0,0.02);
    }
    
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* 标题与文字颜色 */
    h1, h2, h3 {
        color: #0f172a;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    p, span, div {
        color: #334155;
    }

    /* 卡片容器通用样式 */
    .card-container {
        background: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #f1f5f9;
        margin-bottom: 20px;
    }
    
    /* 顶部 Hero 区域 */
    .app-hero {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        border-radius: 16px;
        padding: 32px;
        color: #ffffff;
        box-shadow: 0 10px 30px -10px rgba(37, 99, 235, 0.5);
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }
    
    .app-hero::after {
        content: "";
        position: absolute;
        top: 0;
        right: 0;
        width: 300px;
        height: 100%;
        background: radial-gradient(circle at top right, rgba(255,255,255,0.1) 0%, transparent 60%);
        pointer-events: none;
    }
    
    .app-title {
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 8px;
        color: #ffffff;
    }
    
    .app-subtitle {
        font-size: 16px;
        opacity: 0.9;
        color: #dbeafe;
        font-weight: 500;
    }
    
    /* 标签 Chips */
    .chip-row {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        align-items: center;
        margin-top: 16px;
    }
    
    .chip {
        background: rgba(255, 255, 255, 0.15);
        backdrop-filter: blur(8px);
        color: #ffffff;
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* 核心指标卡片 */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }
    
    .metric-card {
        background: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #f1f5f9;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.05);
    }
    
    .metric-label {
        font-size: 13px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.2;
    }
    
    .value-positive { color: #16a34a; }
    .value-negative { color: #dc2626; }
    .value-neutral { color: #334155; }

    /* 输入框与按钮美化 */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
        border-color: #e2e8f0;
        background-color: #ffffff;
    }
    
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
        border: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    .stButton > button[kind="primary"] {
        background: #2563eb;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #1d4ed8;
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
        transform: translateY(-1px);
    }

    /* 表格样式 */
    div[data-testid="stTable"] {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
    
    thead tr th {
        background-color: #f8fafc !important;
        color: #475569 !important;
        font-weight: 600 !important;
    }
    
    /* Plotly 图表容器 */
    .chart-container {
        background: #ffffff;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #f1f5f9;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)


# --- 数据加载 (支持动态股票池) ---
# 由于需要支持用户动态添加股票，不使用缓存
def get_data_loader(stock_pool: list, request_delay_seconds: float):
    """
    初始化并加载数据
    """
    data_config = DataConfig(request_delay_seconds=request_delay_seconds)
    loader = DataLoader(data_config)
    print(f"Web: Loading data for {len(stock_pool)} stocks...")
    loader.load_all(stock_pool)
    return loader

def build_equal_weight_baseline(loader: DataLoader, stocks: list, start_date: date, end_date: date) -> pd.Series:
    close_series = []
    for symbol in stocks:
        df = loader.get_data(symbol, "daily")
        if df is None or df.empty or "close" not in df.columns:
            continue
        mask = (df.index.date >= start_date) & (df.index.date <= end_date)
        series = df.loc[mask, "close"].astype(float)
        if series.empty:
            continue
        close_series.append(series)
    if not close_series:
        return pd.Series(dtype=float)
    df_close = pd.concat(close_series, axis=1).sort_index()
    df_close = df_close.dropna(how="all")
    if df_close.empty:
        return pd.Series(dtype=float)
    df_close = df_close.ffill()
    first_valid = df_close.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else np.nan)
    norm = df_close.divide(first_valid, axis=1)
    baseline = norm.mean(axis=1)
    return baseline

def build_benchmark_series(code: str, request_delay_seconds: float, start_date: date, end_date: date) -> pd.Series:
    if not code:
        return pd.Series(dtype=float)
    data_config = DataConfig(request_delay_seconds=request_delay_seconds)
    loader = DataLoader(data_config)
    try:
        loader.load_all([code])
    except Exception:
        return pd.Series(dtype=float)
    df = loader.get_data(code, "daily")
    if df is None or df.empty or "close" not in df.columns:
        return pd.Series(dtype=float)
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    series = df.loc[mask, "close"].astype(float)
    return series

def resolve_stock_name(symbol: str, stock_list: dict) -> str:
    code = symbol.split(".")[0]
    if code in stock_list:
        return stock_list[code]
    display = get_stock_display_name(symbol)
    if " - " in display:
        return display.split(" - ", 1)[1]
    return "未知"

def build_trade_pnl(trades: list, stock_list: dict) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    trades_sorted = sorted(trades, key=lambda t: (t.date, t.action))
    positions = {}
    rows = []
    for trade in trades_sorted:
        if trade.action == "BUY":
            lots = positions.setdefault(trade.symbol, [])
            per_commission = trade.commission / trade.quantity if trade.quantity else 0.0
            lots.append({
                "qty": trade.quantity,
                "price": trade.price,
                "date": trade.date,
                "commission": per_commission
            })
        elif trade.action == "SELL":
            lots = positions.get(trade.symbol, [])
            qty_left = trade.quantity
            sell_commission = trade.commission / trade.quantity if trade.quantity else 0.0
            while qty_left > 0 and lots:
                lot = lots[0]
                qty = min(qty_left, lot["qty"])
                buy_commission = lot["commission"] * qty
                sell_comm = sell_commission * qty
                cost = lot["price"] * qty
                pnl = (trade.price - lot["price"]) * qty - buy_commission - sell_comm
                hold_days = (trade.date - lot["date"]).days if trade.date and lot["date"] else 0
                stock_name = resolve_stock_name(trade.symbol, stock_list)
                rows.append({
                    "股票": trade.symbol,
                    "股票名称": stock_name,
                    "买入日": lot["date"],
                    "卖出日": trade.date,
                    "数量": qty,
                    "买入价": lot["price"],
                    "卖出价": trade.price,
                    "持仓天数": hold_days,
                    "盈亏": pnl,
                    "收益率": pnl / cost if cost else 0.0
                })
                lot["qty"] -= qty
                qty_left -= qty
                if lot["qty"] == 0:
                    lots.pop(0)
    return pd.DataFrame(rows)

def resample_kline(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    rule = "W-FRI" if freq == "weekly" else "M"
    agg_map = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }
    if "dividend_yield" in df.columns:
        agg_map["dividend_yield"] = "last"
    resampled = df.resample(rule).agg(agg_map)
    resampled = resampled.dropna(subset=["close"])
    return resampled

def get_cached_kline(symbol: str, freq: str):
    store = st.session_state.get("last_kline_data", {})
    sym_store = store.get(symbol, {})
    return sym_store.get(freq, pd.DataFrame())

def render_backtest_report(
    engine,
    loader,
    metrics,
    stock_list,
    initial_cash,
    selected_stocks,
    start_date,
    end_date,
    benchmark_mode,
    benchmark_code,
    request_delay_seconds,
    backtest_engine,
    strategy_name,
    strategy_params
):
    st.markdown("### 📊 核心绩效指标")
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    def style_metric(label, value, is_percent=True, color_judge=False):
        fmt_val = f"{value:.2%}" if is_percent else f"{value:.4f}"
        color_class = "value-neutral"
        if color_judge:
            if value > 0: color_class = "value-positive"
            elif value < 0: color_class = "value-negative"
        return f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {color_class}">{fmt_val}</div>
        </div>
        """
    with col1:
        st.markdown(style_metric("年化收益", metrics.get("年化收益率", 0), True, True), unsafe_allow_html=True)
    with col2:
        st.markdown(style_metric("最大回撤", metrics.get("最大回撤", 0), True, True), unsafe_allow_html=True)
    with col3:
        st.markdown(style_metric("夏普比率", metrics.get("夏普比率", 0), False, False), unsafe_allow_html=True)
    with col4:
        st.markdown(style_metric("胜率", metrics.get("胜率", 0), True, False), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("### 📈 账户权益曲线")
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    if engine.equity_curve:
        df_equity = pd.DataFrame([{"Date": p.date, "Total Assets": p.total_assets} for p in engine.equity_curve])
        df_equity["Date"] = pd.to_datetime(df_equity["Date"])
        baseline_series = pd.Series(dtype=float)
        if benchmark_mode == "股票池等权":
            baseline_series = build_equal_weight_baseline(loader, selected_stocks, start_date, end_date)
        elif benchmark_mode in ["大盘指数", "指定代码"]:
            baseline_series = build_benchmark_series(benchmark_code, request_delay_seconds, start_date, end_date)
        line_cols = ["Total Assets"]
        color_map = {"Total Assets": "#2563eb"}
        if baseline_series is not None and not baseline_series.empty:
            baseline_series = baseline_series.sort_index()
            base_value = baseline_series.dropna().iloc[0] if not baseline_series.dropna().empty else None
            if base_value:
                baseline_norm = baseline_series / base_value
                df_equity = df_equity.sort_values("Date")
                df_equity["Benchmark"] = baseline_norm.reindex(df_equity["Date"]).ffill().values * initial_cash
                line_cols.append("Benchmark")
                color_map["Benchmark"] = "#f97316"
        if len(line_cols) == 1:
            df_equity["Baseline"] = initial_cash
            line_cols.append("Baseline")
            color_map["Baseline"] = "#94a3b8"
        if benchmark_mode in ["大盘指数", "指定代码"] and (baseline_series is None or baseline_series.empty):
            st.info("基准指数数据未获取到，将使用初始资金作为基准。")
        fig = px.line(df_equity, x="Date", y=line_cols, 
                      labels={"value": "资产净值", "variable": "曲线类型"},
                      color_discrete_map=color_map)
        if engine.trades:
            trade_markers = pd.DataFrame([
                {"Date": t.date, "Action": t.action} for t in engine.trades
            ])
            trade_markers["Date"] = pd.to_datetime(trade_markers["Date"])
            equity_series = df_equity.set_index("Date")["Total Assets"].sort_index()
            trade_markers["Equity"] = trade_markers["Date"].apply(lambda d: equity_series.asof(d))
            buy_markers = trade_markers[trade_markers["Action"] == "BUY"]
            sell_markers = trade_markers[trade_markers["Action"] == "SELL"]
            if not buy_markers.empty:
                fig.add_scatter(
                    x=buy_markers["Date"],
                    y=buy_markers["Equity"],
                    mode="markers",
                    name="买入",
                    marker=dict(color="#16a34a", size=8, symbol="triangle-up")
                )
            if not sell_markers.empty:
                fig.add_scatter(
                    x=sell_markers["Date"],
                    y=sell_markers["Equity"],
                    mode="markers",
                    name="卖出",
                    marker=dict(color="#dc2626", size=8, symbol="triangle-down")
                )
        fig.update_layout(
            xaxis_title="",
            yaxis_title="总资产",
            legend_title="",
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#0f172a")
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("没有生成权益数据，可能是回测区间内没有交易日或数据缺失。")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.markdown("### 📝 交易明细")
        if engine.trades:
            df_trades = pd.DataFrame([
                {
                    "日期": t.date,
                    "股票代码": t.symbol,
                    "股票名称": resolve_stock_name(t.symbol, stock_list),
                    "操作": t.action,
                    "价格": f"{t.price:.2f}",
                    "数量": t.quantity,
                    "佣金": f"{t.commission:.2f}",
                    "备注": t.note
                }
                for t in engine.trades
            ])
            def color_action(val):
                color = '#dcfce7' if val == 'BUY' else '#fee2e2'
                return f'background-color: {color}; color: #0f172a; font-weight: 500'
            st.dataframe(df_trades.style.applymap(color_action, subset=['操作']), use_container_width=True)
        else:
            st.info("回测期间无交易记录。")
    with col_right:
        st.markdown("### 📑 结果摘要")
        df_metrics = pd.DataFrame(list(metrics.items()), columns=["指标", "数值"])
        def fmt_val(row):
            k, v = row["指标"], row["数值"]
            if "收益率" in k or "回撤" in k or "胜率" in k:
                return f"{v:.2%}"
            elif "次数" in k:
                return f"{int(v)}"
            else:
                return f"{v:.4f}"
        df_metrics["数值"] = df_metrics.apply(fmt_val, axis=1)
        st.table(df_metrics)
    if engine.trades:
        if backtest_engine == "Backtrader" and strategy_name == "月线趋势与估值轮动":
            buy_threshold = strategy_params.get("dividend_buy_threshold", 0.045)
            sell_threshold_50 = strategy_params.get("dividend_sell_threshold_50", 0.0375)
            sell_threshold_clear = strategy_params.get("dividend_sell_threshold_clear", 0.033)
            trigger_rows = []
            for t in engine.trades:
                df_dy = loader.get_data(t.symbol, "daily")
                dy_val = None
                if df_dy is not None and not df_dy.empty and "dividend_yield" in df_dy.columns:
                    dy_val = float(df_dy["dividend_yield"].asof(pd.Timestamp(t.date)))
                reason = t.note
                if "DY Reduce" in t.note:
                    reason = "股息率低于减仓阈值"
                elif "DY Clear" in t.note:
                    reason = "股息率低于清仓阈值"
                elif "Trend Buy" in t.note:
                    reason = "信号触发且股息率满足买入阈值"
                trigger_rows.append({
                    "日期": t.date,
                    "股票代码": t.symbol,
                    "股票名称": resolve_stock_name(t.symbol, stock_list),
                    "操作": t.action,
                    "股息率": f"{dy_val:.2%}" if dy_val is not None else "-",
                    "买入阈值": f"{buy_threshold:.2%}",
                    "减仓阈值": f"{sell_threshold_50:.2%}",
                    "清仓阈值": f"{sell_threshold_clear:.2%}",
                    "触发原因": reason
                })
            if trigger_rows:
                st.markdown("### 🧾 触发明细")
                df_trigger = pd.DataFrame(trigger_rows)
                st.dataframe(df_trigger, use_container_width=True)
        st.markdown("### 📍 交易信号回放")
        trade_symbols = sorted({t.symbol for t in engine.trades})
        symbol_options = []
        symbol_lookup = {}
        for s in trade_symbols:
            name = resolve_stock_name(s, stock_list)
            display = f"{s} - {name}"
            symbol_options.append(display)
            symbol_lookup[display] = s
        chart_col_left, chart_col_right = st.columns([2, 1])
        with chart_col_right:
            selected_display = st.selectbox("选择股票", options=symbol_options, index=0, key="trade_kline_symbol")
            kline_freq = st.selectbox("K线周期", options=["日线", "周线", "月线"], index=0, key="trade_kline_freq")
            show_boll = st.toggle("显示BOLL", value=True, key="trade_kline_boll")
            ma_options = {
                "日线": [5, 10, 20, 30, 60, 120, 250],
                "周线": [5, 10, 20, 30, 60, 120, 250],
                "月线": [20, 30, 60]
            }
            default_ma = ma_options.get(kline_freq, [5, 10, 20])
            selected_ma = st.multiselect(
                "叠加均线",
                options=ma_options.get(kline_freq, []),
                default=default_ma,
                key="trade_kline_ma"
            )
        with chart_col_left:
            selected_symbol = symbol_lookup.get(selected_display, trade_symbols[0])
            freq_map = {"日线": "daily", "周线": "weekly", "月线": "monthly"}
            freq_key = freq_map.get(kline_freq, "daily")
            df_k = get_cached_kline(selected_symbol, freq_key)
            if df_k is None or df_k.empty:
                df_k = loader.get_data(selected_symbol, freq_key)
            if (df_k is None or df_k.empty) and freq_key in ["weekly", "monthly"]:
                df_daily = get_cached_kline(selected_symbol, "daily")
                if df_daily is None or df_daily.empty:
                    df_daily = loader.get_data(selected_symbol, "daily")
                df_k = resample_kline(df_daily, freq_key)
            if df_k is None or df_k.empty:
                st.warning("该股票在所选周期没有数据")
            else:
                fig_k = build_kline_chart(df_k, engine.trades, selected_symbol, show_boll, selected_ma)
                st.plotly_chart(fig_k, use_container_width=True)
    pnl_df = build_trade_pnl(engine.trades, stock_list)
    if not pnl_df.empty:
        st.markdown("### 🎨 交易风格分析")
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        pnl_df["结果"] = np.where(pnl_df["盈亏"] >= 0, "盈利", "亏损")
        win_rate = (pnl_df["盈亏"] > 0).mean()
        profit_sum = pnl_df.loc[pnl_df["盈亏"] > 0, "盈亏"].sum()
        loss_sum = pnl_df.loc[pnl_df["盈亏"] < 0, "盈亏"].sum()
        profit_factor = profit_sum / abs(loss_sum) if loss_sum else np.inf
        avg_hold = pnl_df["持仓天数"].mean()
        expectation = pnl_df["盈亏"].mean()
        style_col1, style_col2, style_col3, style_col4 = st.columns(4)
        with style_col1:
            st.metric("平均单笔盈亏", f"{expectation:,.2f}")
        with style_col2:
            st.metric("盈亏比", f"{profit_factor:.2f}" if np.isfinite(profit_factor) else "∞")
        with style_col3:
            st.metric("胜率(单笔)", f"{win_rate:.2%}")
        with style_col4:
            st.metric("平均持仓天数", f"{avg_hold:.1f}")
        st.markdown("---")
        chart_left, chart_right = st.columns(2)
        with chart_left:
            fig_pnl = px.histogram(
                pnl_df,
                x="盈亏",
                color="结果",
                nbins=30,
                color_discrete_map={"盈利": "#16a34a", "亏损": "#dc2626"},
                title="单笔盈亏分布"
            )
            fig_pnl.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#0f172a"),
                title_x=0.02
            )
            st.plotly_chart(fig_pnl, use_container_width=True)
        with chart_right:
            pnl_df_sorted = pnl_df.sort_values("卖出日")
            fig_time = px.bar(
                pnl_df_sorted,
                x="卖出日",
                y="盈亏",
                color="结果",
                color_discrete_map={"盈利": "#16a34a", "亏损": "#dc2626"},
                title="单笔盈亏时间序列"
            )
            fig_time.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#0f172a"),
                title_x=0.02
            )
            st.plotly_chart(fig_time, use_container_width=True)
        st.markdown("#### 📜 单笔盈亏明细")
        st.dataframe(pnl_df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    if PYFOLIO_AVAILABLE and engine.equity_curve:
        returns = pd.DataFrame([{"Date": p.date, "Total Assets": p.total_assets} for p in engine.equity_curve])
        returns["Date"] = pd.to_datetime(returns["Date"])
        returns = returns.set_index("Date")["Total Assets"].pct_change().dropna()
        if not returns.empty:
            pf_stats = pf.timeseries.perf_stats(returns)
            pf_df = pd.DataFrame(pf_stats).reset_index()
            pf_df.columns = ["英文指标", "数值"]
            pf_df["中文指标"] = pf_df["英文指标"].map(PYFOLIO_METRIC_CN).fillna(pf_df["英文指标"])
            pf_df = pf_df[["中文指标", "英文指标", "数值"]]
            st.markdown("### 🧩 Pyfolio 深度分析")
            st.table(pf_df)
            st.markdown("### 📈 Pyfolio 可视化")
            cum_returns = (1 + returns).cumprod()
            drawdown = cum_returns / cum_returns.cummax() - 1
            rolling_sharpe = returns.rolling(60).mean() / returns.rolling(60).std() * np.sqrt(252)
            chart_left, chart_right = st.columns(2)
            with chart_left:
                fig_cum = px.line(
                    cum_returns,
                    title="累计收益曲线",
                    labels={"index": "日期", "value": "累计净值"}
                )
                fig_cum.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#0f172a"),
                    title_x=0.02
                )
                st.plotly_chart(fig_cum, use_container_width=True)
            with chart_right:
                fig_dd = px.area(
                    drawdown,
                    title="回撤曲线",
                    labels={"index": "日期", "value": "回撤"}
                )
                fig_dd.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#0f172a"),
                    title_x=0.02
                )
                st.plotly_chart(fig_dd, use_container_width=True)
            fig_roll = px.line(
                rolling_sharpe,
                title="滚动夏普（60日）",
                labels={"index": "日期", "value": "夏普"}
            )
            fig_roll.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#0f172a"),
                title_x=0.02
            )
            st.plotly_chart(fig_roll, use_container_width=True)

def build_kline_chart(df: pd.DataFrame, trades: list, symbol: str, show_boll: bool = True, ma_windows: list | None = None) -> go.Figure:
    fig = go.Figure()
    if df is None or df.empty:
        return fig
    df = df.sort_index()
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K线"
        )
    )
    if ma_windows:
        for window in ma_windows:
            if window <= 1:
                continue
            ma = df["close"].rolling(window=window).mean()
            fig.add_trace(go.Scatter(
                x=df.index,
                y=ma,
                mode="lines",
                name=f"MA{window}",
                line=dict(width=1)
            ))
    if show_boll:
        upper, mid, lower = bollinger_bands(df["close"], window=20)
        fig.add_trace(go.Scatter(x=df.index, y=upper, mode="lines", name="BOLL上轨", line=dict(color="#f59e0b", width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=mid, mode="lines", name="BOLL中轨", line=dict(color="#64748b", width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=lower, mode="lines", name="BOLL下轨", line=dict(color="#f59e0b", width=1)))
    if trades:
        close_series = df["close"]
        buy_dates = [t.date for t in trades if t.symbol == symbol and t.action == "BUY"]
        sell_dates = [t.date for t in trades if t.symbol == symbol and t.action == "SELL"]
        if buy_dates:
            buy_prices = [close_series.asof(pd.Timestamp(d)) for d in buy_dates]
            fig.add_trace(go.Scatter(
                x=buy_dates,
                y=buy_prices,
                mode="markers",
                name="买入",
                marker=dict(symbol="triangle-up", color="#16a34a", size=10)
            ))
        if sell_dates:
            sell_prices = [close_series.asof(pd.Timestamp(d)) for d in sell_dates]
            fig.add_trace(go.Scatter(
                x=sell_dates,
                y=sell_prices,
                mode="markers",
                name="卖出",
                marker=dict(symbol="triangle-down", color="#dc2626", size=10)
            ))
    fig.update_layout(
        template="plotly_white",
        xaxis_title="",
        yaxis_title="价格",
        legend_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#0f172a")
    )
    return fig

BENCHMARK_INDEX_OPTIONS = {
    "沪深300": "000300.SS",
    "上证指数": "000001.SS",
    "中证500": "000905.SS",
    "深证成指": "399001.SZ",
    "创业板指": "399006.SZ"
}

PYFOLIO_METRIC_CN = {
    "Annual return": "年化收益率",
    "Cumulative returns": "累计收益率",
    "Annual volatility": "年化波动率",
    "Sharpe ratio": "夏普比率",
    "Calmar ratio": "卡玛比率",
    "Stability": "稳定性",
    "Max drawdown": "最大回撤",
    "Omega ratio": "Omega比率",
    "Sortino ratio": "索提诺比率",
    "Skew": "偏度",
    "Kurtosis": "峰度",
    "Tail ratio": "尾部风险比率",
    "Daily value at risk": "日VaR",
    "Alpha": "Alpha",
    "Beta": "Beta"
}

STOCK_LIST_CACHE_PATH = os.path.join(project_root, "data", "stock_list_cache.json")

def load_cached_stock_list() -> dict:
    if os.path.exists(STOCK_LIST_CACHE_PATH):
        try:
            with open(STOCK_LIST_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}

def save_cached_stock_list(stock_list: dict) -> None:
    os.makedirs(os.path.dirname(STOCK_LIST_CACHE_PATH), exist_ok=True)
    with open(STOCK_LIST_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(stock_list, f, ensure_ascii=False)

def render_stock_pool_sidebar():
    if 'editable_stock_pool' not in st.session_state:
        st.session_state.editable_stock_pool = list(STOCK_POOL)
    col_left, col_right = st.columns([6, 1])
    with col_left:
        st.subheader("股票池")
    with col_right:
        refresh_stock_list = st.button("更新", use_container_width=True, key="refresh_stock_list")
    raw_stock_list = load_cached_stock_list()
    if refresh_stock_list or not raw_stock_list:
        try:
            raw_stock_list = get_a_stock_list()
            if raw_stock_list:
                save_cached_stock_list(raw_stock_list)
                if refresh_stock_list:
                    st.success("股票池已更新")
        except Exception as e:
            if refresh_stock_list:
                st.error(f"更新失败: {e}")
    all_stocks = {}
    for code, name in raw_stock_list.items():
        suffix_code = code
        if "." not in code:
            suffix_code = f"{code}.SS" if code.startswith("6") else f"{code}.SZ"
        all_stocks[suffix_code] = name
    for code in st.session_state.editable_stock_pool:
        if code not in all_stocks:
            all_stocks[code] = code.split('.')[0]
    def get_display_name(code):
        name = all_stocks.get(code)
        if name is None:
            display = get_stock_display_name(code)
            if " - " in display:
                name = display.split(" - ", 1)[1]
            else:
                name = code.split('.')[0]
        return f"{code.split('.')[0]} - {name}"
    display_options = [get_display_name(code) for code in all_stocks.keys()]
    display_to_code = {get_display_name(code): code for code in all_stocks.keys()}
    default_display = [get_display_name(code) for code in st.session_state.editable_stock_pool]
    selected_stocks_display = st.multiselect(
        "选择股票",
        options=display_options,
        default=default_display,
        key="stock_pool_multiselect",
        help="支持输入代码/名称后回车筛选添加"
    )
    selected_stocks = [display_to_code[d] for d in selected_stocks_display if d in display_to_code]
    st.session_state.editable_stock_pool = selected_stocks
    st.caption(f"当前股票池: {len(st.session_state.editable_stock_pool)} 只股票")
    return selected_stocks

def render_backtest_sidebar(selected_stocks):
    st.header("回测参数设置")
    backtest_options = ["Backtrader", "内置"] if BACKTRADER_AVAILABLE else ["内置"]
    backtest_engine = st.selectbox("回测引擎", options=backtest_options, index=0, key="backtest_engine")
    st.subheader("策略配置")
    strategy_mode = st.radio(
        "策略模式",
        ["单一策略", "组合策略（分仓管理）"],
        horizontal=True,
        help="组合策略：同时运行两个策略，各自管理分配的资金"
    )
    if backtest_engine == "Backtrader" and strategy_mode != "单一策略":
        st.error("Backtrader 仅支持单一策略")
        st.stop()
    fund_ratio_a = 0.5
    fund_ratio_b = 0.5
    if strategy_mode == "单一策略":
        strategy_name = st.selectbox(
            "选择策略",
            options=["月线趋势与估值轮动", "双均线策略 (20/60)"],
            index=0
        )
    else:
        st.markdown("---")
        st.markdown("**📊 组合策略配置**")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### 策略 A")
            strategy_a_name = st.selectbox(
                "策略A",
                options=["月线趋势与估值轮动", "双均线策略 (20/60)"],
                index=0,
                key="strategy_a"
            )
            fund_ratio_a = st.slider(
                "策略A资金比例",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.1,
                key="fund_a",
                help="策略A占总资金的比例，设为0可禁用该策略"
            )
            st.caption(f"💰 资金占比: {fund_ratio_a:.0%}")
        with col_b:
            st.markdown("### 策略 B")
            strategy_b_name = st.selectbox(
                "策略B",
                options=["月线趋势与估值轮动", "双均线策略 (20/60)"],
                index=1,
                key="strategy_b"
            )
            if fund_ratio_a >= 1.0:
                fund_ratio_b = 0.0
            elif fund_ratio_a <= 0.0:
                fund_ratio_b = 1.0
            else:
                fund_ratio_b = 1.0 - fund_ratio_a
            st.caption(f"💰 资金占比: {fund_ratio_b:.0%}")
        if fund_ratio_a == 0 and fund_ratio_b == 0:
            st.error("❌ 错误：两个策略的资金占比不能同时为0！")
            st.stop()
        if strategy_a_name == strategy_b_name and fund_ratio_a > 0 and fund_ratio_b > 0:
            st.warning("⚠️ 注意：两个策略相同，会产生重复信号")
        strategy_name = "组合策略"
    strategy_params = {}
    strategy_params_a = {}
    strategy_params_b = {}
    if strategy_mode == "单一策略":
        if strategy_name == "月线趋势与估值轮动":
            st.info("策略逻辑：月线MA60趋势 + 股息率估值轮动 + 周线辅助")
            div_threshold = st.number_input("买入股息率阈值", value=0.045, step=0.001, format="%.3f", 
                                           help="股息率需达到此阈值才能买入")
            strategy_params["dividend_buy_threshold"] = div_threshold
            st.subheader("信号A：月线突破后BOLL回踩参数")
            boll_pullback_lower = st.number_input(
                "BOLL回踩下限（中轨倍数）", 
                value=0.95, 
                min_value=0.80, 
                max_value=1.00, 
                step=0.01, 
                format="%.2f",
                help="月线收盘价 >= BOLL中轨 × 此值（默认0.95，即中轨的95%）"
            )
            boll_pullback_upper = st.number_input(
                "BOLL回踩上限（中轨倍数）", 
                value=1.05, 
                min_value=1.00, 
                max_value=1.20, 
                step=0.01, 
                format="%.2f",
                help="月线收盘价 <= BOLL中轨 × 此值（默认1.05，即中轨的105%）"
            )
            strategy_params["boll_pullback_lower"] = boll_pullback_lower
            strategy_params["boll_pullback_upper"] = boll_pullback_upper
            st.caption(f"📊 回踩范围：BOLL中轨 × [{boll_pullback_lower:.2f}, {boll_pullback_upper:.2f}]")
            st.subheader("卖出策略：股息率阶梯减仓")
            div_sell_50 = st.number_input(
                "减仓50%阈值（股息率）", 
                value=0.0375, 
                step=0.0005, 
                format="%.4f",
                help="股息率低于此值时，卖出一半仓位（默认3.75%）"
            )
            div_sell_clear = st.number_input(
                "清仓阈值（股息率）", 
                value=0.033, 
                step=0.0005, 
                format="%.4f",
                help="股息率低于此值时，全部清仓（默认3.3%，必须小于减仓阈值）"
            )
            if div_sell_clear >= div_sell_50:
                st.error(f"⚠️ 清仓阈值 ({div_sell_clear:.2%}) 必须小于减仓阈值 ({div_sell_50:.2%})")
            else:
                st.success(f"✅ 参数设置正确：清仓阈值 ({div_sell_clear:.2%}) < 减仓阈值 ({div_sell_50:.2%})")
            strategy_params["dividend_sell_threshold_50"] = div_sell_50
            strategy_params["dividend_sell_threshold_clear"] = div_sell_clear
            st.caption(f"📉 卖出逻辑：DY < {div_sell_50:.2%} 减仓50% | DY < {div_sell_clear:.2%} 清仓")
        elif strategy_name == "双均线策略 (20/60)":
            st.info("策略逻辑：短期均线上穿长期均线买入，下穿卖出")
            short_window = st.number_input("短期窗口", value=20, step=1)
            long_window = st.number_input("长期窗口", value=60, step=1)
            strategy_params["short_window"] = short_window
            strategy_params["long_window"] = long_window
    if strategy_mode == "组合策略（分仓管理）":
        st.markdown("---")
        st.markdown("### 策略A 参数配置")
        if strategy_a_name == "月线趋势与估值轮动":
            with st.expander("策略A：月线趋势与估值轮动 参数", expanded=True):
                div_threshold_a = st.number_input("策略A - 买入股息率阈值", value=0.045, step=0.001, format="%.3f", 
                                               key="div_a", help="股息率需达到此阈值才能买入")
                boll_lower_a = st.number_input("策略A - BOLL回踩下限", value=0.95, min_value=0.80, max_value=1.00, 
                                              step=0.01, format="%.2f", key="boll_lower_a")
                boll_upper_a = st.number_input("策略A - BOLL回踩上限", value=1.05, min_value=1.00, max_value=1.20, 
                                              step=0.01, format="%.2f", key="boll_upper_a")
                div_sell_50_a = st.number_input("策略A - 减仓50%阈值", value=0.0375, step=0.0005, format="%.4f", key="div_sell_50_a")
                div_sell_clear_a = st.number_input("策略A - 清仓阈值", value=0.033, step=0.0005, format="%.4f", key="div_sell_clear_a")
                strategy_params_a = {
                    "name": "MonthlyTrendDividendRotation",
                    "dividend_buy_threshold": div_threshold_a,
                    "boll_pullback_lower": boll_lower_a,
                    "boll_pullback_upper": boll_upper_a,
                    "dividend_sell_threshold_50": div_sell_50_a,
                    "dividend_sell_threshold_clear": div_sell_clear_a
                }
        else:
            with st.expander("策略A：双均线策略 参数", expanded=True):
                short_a = st.number_input("策略A - 短期窗口", value=20, step=1, key="short_a")
                long_a = st.number_input("策略A - 长期窗口", value=60, step=1, key="long_a")
                strategy_params_a = {
                    "name": "DoubleMAStrategy",
                    "short_window": short_a,
                    "long_window": long_a
                }
        st.markdown("### 策略B 参数配置")
        if strategy_b_name == "月线趋势与估值轮动":
            with st.expander("策略B：月线趋势与估值轮动 参数", expanded=True):
                div_threshold_b = st.number_input("策略B - 买入股息率阈值", value=0.045, step=0.001, format="%.3f", 
                                               key="div_b", help="股息率需达到此阈值才能买入")
                boll_lower_b = st.number_input("策略B - BOLL回踩下限", value=0.95, min_value=0.80, max_value=1.00, 
                                              step=0.01, format="%.2f", key="boll_lower_b")
                boll_upper_b = st.number_input("策略B - BOLL回踩上限", value=1.05, min_value=1.00, max_value=1.20, 
                                              step=0.01, format="%.2f", key="boll_upper_b")
                div_sell_50_b = st.number_input("策略B - 减仓50%阈值", value=0.0375, step=0.0005, format="%.4f", key="div_sell_50_b")
                div_sell_clear_b = st.number_input("策略B - 清仓阈值", value=0.033, step=0.0005, format="%.4f", key="div_sell_clear_b")
                strategy_params_b = {
                    "name": "MonthlyTrendDividendRotation",
                    "dividend_buy_threshold": div_threshold_b,
                    "boll_pullback_lower": boll_lower_b,
                    "boll_pullback_upper": boll_upper_b,
                    "dividend_sell_threshold_50": div_sell_50_b,
                    "dividend_sell_threshold_clear": div_sell_clear_b
                }
        else:
            with st.expander("策略B：双均线策略 参数", expanded=True):
                short_b = st.number_input("策略B - 短期窗口", value=20, step=1, key="short_b")
                long_b = st.number_input("策略B - 长期窗口", value=60, step=1, key="long_b")
                strategy_params_b = {
                    "name": "DoubleMAStrategy",
                    "short_window": short_b,
                    "long_window": long_b
                }
        st.markdown("---")
        st.markdown(f"""
        ### 💰 资金分配摘要
        - **策略A ({strategy_a_name})**: {fund_ratio_a:.0%}
        - **策略B ({strategy_b_name})**: {fund_ratio_b:.0%}
        """)
    elif strategy_name == "双均线策略 (20/60)":
        st.info("策略逻辑：短期均线上穿长期均线买入，下穿卖出")
        short_window = st.number_input("短期窗口", value=20, step=1)
        long_window = st.number_input("长期窗口", value=60, step=1)
        strategy_params["short_window"] = short_window
        strategy_params["long_window"] = long_window
    st.subheader("账户设置")
    initial_cash = st.number_input("初始资金", value=1_000_000, step=100_000)
    commission = st.number_input("手续费率", value=0.0003, step=0.0001, format="%.4f")
    st.subheader("回测区间")
    default_start = date(2019, 1, 1)
    default_end = date.today()
    start_date = st.date_input("开始日期", value=default_start)
    end_date = st.date_input("结束日期", value=default_end)
    st.subheader("基准对比")
    benchmark_mode = st.selectbox("基准类型", options=["股票池等权", "大盘指数", "指定代码"], index=1, key="benchmark_mode")
    benchmark_code = ""
    benchmark_label = ""
    if benchmark_mode == "大盘指数":
        benchmark_label = st.selectbox("指数选择", options=list(BENCHMARK_INDEX_OPTIONS.keys()), index=0, key="benchmark_index")
        benchmark_code = BENCHMARK_INDEX_OPTIONS.get(benchmark_label, "")
    if benchmark_mode == "指定代码":
        benchmark_code = st.text_input("基准代码", value="000300.SS", key="benchmark_code")
    st.subheader("数据请求间隔")
    request_delay_seconds = st.number_input("每次请求延迟(秒)", value=0.3, min_value=0.0, step=0.1, format="%.1f")
    run_btn = st.button("开始回测", type="primary", use_container_width=True)
    return {
        "selected_stocks": selected_stocks,
        "backtest_engine": backtest_engine,
        "strategy_mode": strategy_mode,
        "strategy_name": strategy_name,
        "strategy_params": strategy_params,
        "strategy_params_a": strategy_params_a,
        "strategy_params_b": strategy_params_b,
        "fund_ratio_a": fund_ratio_a,
        "fund_ratio_b": fund_ratio_b,
        "initial_cash": initial_cash,
        "commission": commission,
        "start_date": start_date,
        "end_date": end_date,
        "benchmark_mode": benchmark_mode,
        "benchmark_code": benchmark_code,
        "request_delay_seconds": request_delay_seconds,
        "run_btn": run_btn
    }

def render_paper_sidebar(selected_stocks):
    st.header("模拟盘设置")
    paper_options = ["内置"] + (["vn.py"] if VNPY_AVAILABLE else [])
    paper_engine = st.selectbox("模拟盘引擎", options=paper_options, index=0, key="paper_engine")
    st.subheader("策略配置")
    strategy_name = st.selectbox(
        "选择策略",
        options=["月线趋势与估值轮动", "双均线策略 (20/60)"],
        index=0,
        key="paper_strategy"
    )
    strategy_params = {}
    if strategy_name == "月线趋势与估值轮动":
        div_threshold = st.number_input("买入股息率阈值", value=0.045, step=0.001, format="%.3f", 
                                       key="paper_div", help="股息率需达到此阈值才能买入")
        boll_pullback_lower = st.number_input(
            "BOLL回踩下限（中轨倍数）", 
            value=0.95, 
            min_value=0.80, 
            max_value=1.00, 
            step=0.01, 
            format="%.2f",
            key="paper_boll_lower",
            help="月线收盘价 >= BOLL中轨 × 此值"
        )
        boll_pullback_upper = st.number_input(
            "BOLL回踩上限（中轨倍数）", 
            value=1.05, 
            min_value=1.00, 
            max_value=1.20, 
            step=0.01, 
            format="%.2f",
            key="paper_boll_upper",
            help="月线收盘价 <= BOLL中轨 × 此值"
        )
        div_sell_50 = st.number_input(
            "减仓50%阈值（股息率）", 
            value=0.0375, 
            step=0.0005, 
            format="%.4f",
            key="paper_div_sell_50"
        )
        div_sell_clear = st.number_input(
            "清仓阈值（股息率）", 
            value=0.033, 
            step=0.0005, 
            format="%.4f",
            key="paper_div_sell_clear"
        )
        strategy_params = {
            "dividend_buy_threshold": div_threshold,
            "boll_pullback_lower": boll_pullback_lower,
            "boll_pullback_upper": boll_pullback_upper,
            "dividend_sell_threshold_50": div_sell_50,
            "dividend_sell_threshold_clear": div_sell_clear
        }
    else:
        short_window = st.number_input("短期窗口", value=20, step=1, key="paper_short")
        long_window = st.number_input("长期窗口", value=60, step=1, key="paper_long")
        strategy_params["short_window"] = short_window
        strategy_params["long_window"] = long_window
    st.subheader("模拟账户")
    account_file = st.text_input("账户文件", value="paper_account.json", key="paper_account_file")
    initial_cash = st.number_input("初始资金", value=100_000.0, step=10_000.0, key="paper_initial_cash")
    st.subheader("运行控制")
    interval_minutes = st.number_input("循环间隔（分钟）", value=5, min_value=1, step=1, key="paper_interval")
    start_time = st.text_input("开始时间", value="09:30", key="paper_start_time")
    end_time = st.text_input("结束时间", value="15:00", key="paper_end_time")
    max_runs = st.number_input("最大运行次数（0为不限制）", value=0, min_value=0, step=1, key="paper_max_runs")
    run_once_btn = st.button("运行一次", type="primary", use_container_width=True)
    run_loop_btn = st.button("开始循环", use_container_width=True)
    return {
        "selected_stocks": selected_stocks,
        "paper_engine": paper_engine,
        "strategy_name": strategy_name,
        "strategy_params": strategy_params,
        "account_file": account_file,
        "initial_cash": initial_cash,
        "run_once_btn": run_once_btn,
        "run_loop_btn": run_loop_btn,
        "interval_minutes": interval_minutes,
        "start_time": start_time,
        "end_time": end_time,
        "max_runs": max_runs
    }

with st.sidebar:
    st.header("功能模块")
    module_select = st.radio("选择模块", ["回测", "模拟盘"], horizontal=True)
    st.markdown("---")
    selected_stocks = render_stock_pool_sidebar()
    st.markdown("---")
    if module_select == "回测":
        backtest_params = render_backtest_sidebar(selected_stocks)
        paper_params = None
    else:
        paper_params = render_paper_sidebar(selected_stocks)
        backtest_params = None

if module_select == "回测":
    run_btn = backtest_params["run_btn"]
    selected_stocks = backtest_params["selected_stocks"]
    backtest_engine = backtest_params["backtest_engine"]
    strategy_mode = backtest_params["strategy_mode"]
    strategy_name = backtest_params["strategy_name"]
    strategy_params = backtest_params["strategy_params"]
    strategy_params_a = backtest_params["strategy_params_a"]
    strategy_params_b = backtest_params["strategy_params_b"]
    fund_ratio_a = backtest_params["fund_ratio_a"]
    fund_ratio_b = backtest_params["fund_ratio_b"]
    initial_cash = backtest_params["initial_cash"]
    commission = backtest_params["commission"]
    start_date = backtest_params["start_date"]
    end_date = backtest_params["end_date"]
    benchmark_mode = backtest_params["benchmark_mode"]
    benchmark_code = backtest_params["benchmark_code"]
    request_delay_seconds = backtest_params["request_delay_seconds"]

    hero_title = "投滚量化回测系统"
    hero_subtitle = "面向策略验证的可视化回测与风险分析"
    
    st.markdown(
        f"""
        <div class="app-hero">
            <div>
                <div class="app-title">{hero_title}</div>
                <div class="app-subtitle">{hero_subtitle}</div>
            </div>
            <div class="chip-row">
                <div class="chip">
                    <span>⚡</span> 引擎: {backtest_engine}
                </div>
                <div class="chip">
                    <span>🎯</span> 策略: {strategy_name}
                </div>
                <div class="chip">
                    <span>📦</span> 股票池: {len(selected_stocks)} 只
                </div>
                <div class="chip">
                    <span>📅</span> 区间: {start_date} ~ {end_date}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    last_result = st.session_state.get("last_backtest_result")
    if run_btn:
        if not selected_stocks:
            st.error("请至少选择一只股票！")
            st.stop()
        with st.spinner("🚀 正在执行回测计算..."):
            loader = get_data_loader(selected_stocks, request_delay_seconds)
            backtest_config = BacktestConfig(
                initial_cash=initial_cash,
                commission_rate=commission,
                slippage=0.001
            )
            if backtest_engine == "Backtrader":
                engine = BacktraderEngine(
                    config=backtest_config,
                    loader=loader,
                    stk_pool=selected_stocks,
                    strategy_name=strategy_name,
                    strategy_params=strategy_params
                )
            else:
                if strategy_mode == "单一策略":
                    if strategy_name == "月线趋势与估值轮动":
                        strategy = MonthlyTrendDividendRotation(
                            dividend_buy_threshold=strategy_params["dividend_buy_threshold"],
                            dividend_sell_threshold_50=strategy_params.get("dividend_sell_threshold_50", 0.0375),
                            dividend_sell_threshold_clear=strategy_params.get("dividend_sell_threshold_clear", 0.033),
                            boll_pullback_lower=strategy_params.get("boll_pullback_lower", 0.95),
                            boll_pullback_upper=strategy_params.get("boll_pullback_upper", 1.05)
                        )
                    else:
                        strategy = DoubleMAStrategy(
                            short_window=strategy_params["short_window"],
                            long_window=strategy_params["long_window"]
                        )
                else:
                    if strategy_params_a["name"] == "MonthlyTrendDividendRotation":
                        strategy_a = MonthlyTrendDividendRotation(
                            dividend_buy_threshold=strategy_params_a["dividend_buy_threshold"],
                            dividend_sell_threshold_50=strategy_params_a.get("dividend_sell_threshold_50", 0.0375),
                            dividend_sell_threshold_clear=strategy_params_a.get("dividend_sell_threshold_clear", 0.033),
                            boll_pullback_lower=strategy_params_a.get("boll_pullback_lower", 0.95),
                            boll_pullback_upper=strategy_params_a.get("boll_pullback_upper", 1.05)
                        )
                    else:
                        strategy_a = DoubleMAStrategy(
                            short_window=strategy_params_a["short_window"],
                            long_window=strategy_params_a["long_window"]
                        )
                    if strategy_params_b["name"] == "MonthlyTrendDividendRotation":
                        strategy_b = MonthlyTrendDividendRotation(
                            dividend_buy_threshold=strategy_params_b["dividend_buy_threshold"],
                            dividend_sell_threshold_50=strategy_params_b.get("dividend_sell_threshold_50", 0.0375),
                            dividend_sell_threshold_clear=strategy_params_b.get("dividend_sell_threshold_clear", 0.033),
                            boll_pullback_lower=strategy_params_b.get("boll_pullback_lower", 0.95),
                            boll_pullback_upper=strategy_params_b.get("boll_pullback_upper", 1.05)
                        )
                    else:
                        strategy_b = DoubleMAStrategy(
                            short_window=strategy_params_b["short_window"],
                            long_window=strategy_params_b["long_window"]
                        )
                    strategy = CombinedStrategy(
                        strategy_a=strategy_a,
                        strategy_b=strategy_b,
                        fund_ratio_a=fund_ratio_a,
                        fund_ratio_b=fund_ratio_b
                    )
                engine = BacktestEngine(
                    config=backtest_config,
                    loader=loader,
                    strategy=strategy,
                    stk_pool=selected_stocks
                )
            try:
                engine.run(start_date, end_date)
                try:
                    stock_list = get_a_stock_list()
                except Exception:
                    stock_list = {}
                metrics = compute_metrics(engine.equity_curve, engine.trades, initial_cash)
                st.session_state["last_backtest_result"] = {
                    "engine": engine,
                    "loader": loader,
                    "metrics": metrics,
                    "stock_list": stock_list,
                    "params": backtest_params
                }
                trade_symbols = {t.symbol for t in engine.trades}
                kline_cache = {}
                for symbol in trade_symbols:
                    daily_df = loader.get_data(symbol, "daily")
                    weekly_df = loader.get_data(symbol, "weekly")
                    if weekly_df is None or weekly_df.empty:
                        weekly_df = resample_kline(daily_df, "weekly")
                    monthly_df = loader.get_data(symbol, "monthly")
                    if monthly_df is None or monthly_df.empty:
                        monthly_df = resample_kline(daily_df, "monthly")
                    kline_cache[symbol] = {
                        "daily": daily_df,
                        "weekly": weekly_df,
                        "monthly": monthly_df
                    }
                st.session_state["last_kline_data"] = kline_cache
                last_result = st.session_state["last_backtest_result"]
                
                st.markdown("### 📊 核心绩效指标")
                st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                
                def style_metric(label, value, is_percent=True, color_judge=False):
                    fmt_val = f"{value:.2%}" if is_percent else f"{value:.4f}"
                    color_class = "value-neutral"
                    if color_judge:
                        if value > 0: color_class = "value-positive"
                        elif value < 0: color_class = "value-negative"
                    return f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value {color_class}">{fmt_val}</div>
                    </div>
                    """
                
                with col1:
                    st.markdown(style_metric("年化收益", metrics.get("年化收益率", 0), True, True), unsafe_allow_html=True)
                with col2:
                    st.markdown(style_metric("最大回撤", metrics.get("最大回撤", 0), True, True), unsafe_allow_html=True)
                with col3:
                    st.markdown(style_metric("夏普比率", metrics.get("夏普比率", 0), False, False), unsafe_allow_html=True)
                with col4:
                    st.markdown(style_metric("胜率", metrics.get("胜率", 0), True, False), unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("### 📈 账户权益曲线")
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                if engine.equity_curve:

                    df_equity = pd.DataFrame([{"Date": p.date, "Total Assets": p.total_assets} for p in engine.equity_curve])
                    df_equity["Date"] = pd.to_datetime(df_equity["Date"])
                    baseline_series = pd.Series(dtype=float)
                    if benchmark_mode == "股票池等权":
                        baseline_series = build_equal_weight_baseline(loader, selected_stocks, start_date, end_date)
                    elif benchmark_mode in ["大盘指数", "指定代码"]:
                        baseline_series = build_benchmark_series(benchmark_code, request_delay_seconds, start_date, end_date)
                    line_cols = ["Total Assets"]
                    color_map = {"Total Assets": "#2563eb"}
                    if baseline_series is not None and not baseline_series.empty:
                        baseline_series = baseline_series.sort_index()
                        base_value = baseline_series.dropna().iloc[0] if not baseline_series.dropna().empty else None
                        if base_value:
                            baseline_norm = baseline_series / base_value
                            df_equity = df_equity.sort_values("Date")
                            df_equity["Benchmark"] = baseline_norm.reindex(df_equity["Date"]).ffill().values * initial_cash
                            line_cols.append("Benchmark")
                            color_map["Benchmark"] = "#f97316"
                    if len(line_cols) == 1:
                        df_equity["Baseline"] = initial_cash
                        line_cols.append("Baseline")
                        color_map["Baseline"] = "#94a3b8"
                    if benchmark_mode in ["大盘指数", "指定代码"] and (baseline_series is None or baseline_series.empty):
                        st.info("基准指数数据未获取到，将使用初始资金作为基准。")
                    fig = px.line(df_equity, x="Date", y=line_cols, 
                                  labels={"value": "资产净值", "variable": "曲线类型"},
                                  color_discrete_map=color_map)
                    if engine.trades:
                        trade_markers = pd.DataFrame([
                            {"Date": t.date, "Action": t.action} for t in engine.trades
                        ])
                        trade_markers["Date"] = pd.to_datetime(trade_markers["Date"])
                        equity_series = df_equity.set_index("Date")["Total Assets"].sort_index()
                        trade_markers["Equity"] = trade_markers["Date"].apply(lambda d: equity_series.asof(d))
                        buy_markers = trade_markers[trade_markers["Action"] == "BUY"]
                        sell_markers = trade_markers[trade_markers["Action"] == "SELL"]
                        if not buy_markers.empty:
                            fig.add_scatter(
                                x=buy_markers["Date"],
                                y=buy_markers["Equity"],
                                mode="markers",
                                name="买入",
                                marker=dict(color="#16a34a", size=8, symbol="triangle-up")
                            )
                        if not sell_markers.empty:
                            fig.add_scatter(
                                x=sell_markers["Date"],
                                y=sell_markers["Equity"],
                                mode="markers",
                                name="卖出",
                                marker=dict(color="#dc2626", size=8, symbol="triangle-down")
                            )
                    fig.update_layout(
                        xaxis_title="",
                        yaxis_title="总资产",
                        legend_title="",
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#0f172a")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("没有生成权益数据，可能是回测区间内没有交易日或数据缺失。")
                
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")

                col_left, col_right = st.columns([2, 1])
                with col_left:
                    st.markdown("### 📝 交易明细")
                    if engine.trades:
                        df_trades = pd.DataFrame([
                            {
                                "日期": t.date,
                                "股票代码": t.symbol,
                                "股票名称": resolve_stock_name(t.symbol, stock_list),
                                "操作": t.action,
                                "价格": f"{t.price:.2f}",
                                "数量": t.quantity,
                                "佣金": f"{t.commission:.2f}",
                                "备注": t.note
                            }
                            for t in engine.trades
                        ])
                        def color_action(val):
                            color = '#dcfce7' if val == 'BUY' else '#fee2e2'
                            return f'background-color: {color}; color: #0f172a; font-weight: 500'
                        st.dataframe(df_trades.style.applymap(color_action, subset=['操作']), use_container_width=True)
                    else:
                        st.info("回测期间无交易记录。")
                with col_right:
                    st.markdown("### 📑 结果摘要")
                    df_metrics = pd.DataFrame(list(metrics.items()), columns=["指标", "数值"])
                    def fmt_val(row):
                        k, v = row["指标"], row["数值"]
                        if "收益率" in k or "回撤" in k or "胜率" in k:
                            return f"{v:.2%}"
                        elif "次数" in k:
                            return f"{int(v)}"
                        else:
                            return f"{v:.4f}"
                    df_metrics["数值"] = df_metrics.apply(fmt_val, axis=1)
                    st.table(df_metrics)

                if engine.trades:
                    if backtest_engine == "Backtrader" and strategy_name == "月线趋势与估值轮动":
                        buy_threshold = strategy_params.get("dividend_buy_threshold", 0.045)
                        sell_threshold_50 = strategy_params.get("dividend_sell_threshold_50", 0.0375)
                        sell_threshold_clear = strategy_params.get("dividend_sell_threshold_clear", 0.033)
                        trigger_rows = []
                        for t in engine.trades:
                            df_dy = loader.get_data(t.symbol, "daily")
                            dy_val = None
                            if df_dy is not None and not df_dy.empty and "dividend_yield" in df_dy.columns:
                                dy_val = float(df_dy["dividend_yield"].asof(pd.Timestamp(t.date)))
                            reason = t.note
                            if "DY Reduce" in t.note:
                                reason = "股息率低于减仓阈值"
                            elif "DY Clear" in t.note:
                                reason = "股息率低于清仓阈值"
                            elif "Trend Buy" in t.note:
                                reason = "信号触发且股息率满足买入阈值"
                            trigger_rows.append({
                                "日期": t.date,
                                "股票代码": t.symbol,
                                "股票名称": resolve_stock_name(t.symbol, stock_list),
                                "操作": t.action,
                                "股息率": f"{dy_val:.2%}" if dy_val is not None else "-",
                                "买入阈值": f"{buy_threshold:.2%}",
                                "减仓阈值": f"{sell_threshold_50:.2%}",
                                "清仓阈值": f"{sell_threshold_clear:.2%}",
                                "触发原因": reason
                            })
                        if trigger_rows:
                            st.markdown("### 🧾 触发明细")
                            df_trigger = pd.DataFrame(trigger_rows)
                            st.dataframe(df_trigger, use_container_width=True)
                    st.markdown("### 📍 交易信号回放")
                    trade_symbols = sorted({t.symbol for t in engine.trades})
                    symbol_options = []
                    symbol_lookup = {}
                    for s in trade_symbols:
                        name = resolve_stock_name(s, stock_list)
                        display = f"{s} - {name}"
                        symbol_options.append(display)
                        symbol_lookup[display] = s
                    chart_col_left, chart_col_right = st.columns([2, 1])
                    with chart_col_right:
                        selected_display = st.selectbox("选择股票", options=symbol_options, index=0, key="trade_kline_symbol")
                        kline_freq = st.selectbox("K线周期", options=["日线", "周线", "月线"], index=0, key="trade_kline_freq")
                        show_boll = st.toggle("显示BOLL", value=True, key="trade_kline_boll")
                        ma_options = {
                            "日线": [5, 10, 20, 30, 60, 120, 250],
                            "周线": [5, 10, 20, 30, 60, 120, 250],
                            "月线": [20, 30, 60]
                        }
                        default_ma = ma_options.get(kline_freq, [5, 10, 20])
                        selected_ma = st.multiselect(
                            "叠加均线",
                            options=ma_options.get(kline_freq, []),
                            default=default_ma,
                            key="trade_kline_ma"
                        )
                    with chart_col_left:
                        selected_symbol = symbol_lookup.get(selected_display, trade_symbols[0])
                        freq_map = {"日线": "daily", "周线": "weekly", "月线": "monthly"}
                        freq_key = freq_map.get(kline_freq, "daily")
                        df_k = loader.get_data(selected_symbol, freq_key)
                        if (df_k is None or df_k.empty) and freq_key in ["weekly", "monthly"]:
                            df_daily = loader.get_data(selected_symbol, "daily")
                            df_k = resample_kline(df_daily, freq_key)
                        if df_k is None or df_k.empty:
                            st.warning("该股票在所选周期没有数据")
                        else:
                            fig_k = build_kline_chart(df_k, engine.trades, selected_symbol, show_boll, selected_ma)
                            st.plotly_chart(fig_k, use_container_width=True)
                
                pnl_df = build_trade_pnl(engine.trades, stock_list)
                if not pnl_df.empty:
                    st.markdown("### 🎨 交易风格分析")
                    st.markdown('<div class="card-container">', unsafe_allow_html=True)
                    
                    pnl_df["结果"] = np.where(pnl_df["盈亏"] >= 0, "盈利", "亏损")
                    win_rate = (pnl_df["盈亏"] > 0).mean()
                    profit_sum = pnl_df.loc[pnl_df["盈亏"] > 0, "盈亏"].sum()
                    loss_sum = pnl_df.loc[pnl_df["盈亏"] < 0, "盈亏"].sum()
                    profit_factor = profit_sum / abs(loss_sum) if loss_sum else np.inf
                    avg_hold = pnl_df["持仓天数"].mean()
                    expectation = pnl_df["盈亏"].mean()
                    
                    style_col1, style_col2, style_col3, style_col4 = st.columns(4)
                    with style_col1:
                        st.metric("平均单笔盈亏", f"{expectation:,.2f}")
                    with style_col2:
                        st.metric("盈亏比", f"{profit_factor:.2f}" if np.isfinite(profit_factor) else "∞")
                    with style_col3:
                        st.metric("胜率(单笔)", f"{win_rate:.2%}")
                    with style_col4:
                        st.metric("平均持仓天数", f"{avg_hold:.1f}")
                    
                    st.markdown("---")
                    
                    chart_left, chart_right = st.columns(2)
                    with chart_left:
                        fig_pnl = px.histogram(
                            pnl_df,
                            x="盈亏",
                            color="结果",
                            nbins=30,
                            color_discrete_map={"盈利": "#16a34a", "亏损": "#dc2626"},
                            title="单笔盈亏分布"
                        )
                        fig_pnl.update_layout(
                            template="plotly_white",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#0f172a"),
                            title_x=0.02
                        )
                        st.plotly_chart(fig_pnl, use_container_width=True)
                    with chart_right:
                        pnl_df_sorted = pnl_df.sort_values("卖出日")
                        fig_time = px.bar(
                            pnl_df_sorted,
                            x="卖出日",
                            y="盈亏",
                            color="结果",
                            color_discrete_map={"盈利": "#16a34a", "亏损": "#dc2626"},
                            title="单笔盈亏时间序列"
                        )
                        fig_time.update_layout(
                            template="plotly_white",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#0f172a"),
                            title_x=0.02
                        )
                        st.plotly_chart(fig_time, use_container_width=True)
                    
                    st.markdown("#### 📜 单笔盈亏明细")
                    st.dataframe(pnl_df, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if PYFOLIO_AVAILABLE and engine.equity_curve:
                    returns = df_equity.set_index("Date")["Total Assets"].pct_change().dropna()
                    if not returns.empty:
                        pf_stats = pf.timeseries.perf_stats(returns)
                        pf_df = pd.DataFrame(pf_stats).reset_index()
                        pf_df.columns = ["英文指标", "数值"]
                        pf_df["中文指标"] = pf_df["英文指标"].map(PYFOLIO_METRIC_CN).fillna(pf_df["英文指标"])
                        pf_df = pf_df[["中文指标", "英文指标", "数值"]]
                        st.markdown("### 🧩 Pyfolio 深度分析")
                        st.table(pf_df)
                        st.markdown("### 📈 Pyfolio 可视化")
                        cum_returns = (1 + returns).cumprod()
                        drawdown = cum_returns / cum_returns.cummax() - 1
                        rolling_sharpe = returns.rolling(60).mean() / returns.rolling(60).std() * np.sqrt(252)
                        chart_left, chart_right = st.columns(2)
                        with chart_left:
                            fig_cum = px.line(
                                cum_returns,
                                title="累计收益曲线",
                                labels={"index": "日期", "value": "累计净值"}
                            )
                            fig_cum.update_layout(
                                template="plotly_white",
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#0f172a"),
                                title_x=0.02
                            )
                            st.plotly_chart(fig_cum, use_container_width=True)
                        with chart_right:
                            fig_dd = px.area(
                                drawdown,
                                title="回撤曲线",
                                labels={"index": "日期", "value": "回撤"}
                            )
                            fig_dd.update_layout(
                                template="plotly_white",
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#0f172a"),
                                title_x=0.02
                            )
                            st.plotly_chart(fig_dd, use_container_width=True)
                        fig_roll = px.line(
                            rolling_sharpe,
                            title="滚动夏普（60日）",
                            labels={"index": "日期", "value": "夏普"}
                        )
                        fig_roll.update_layout(
                            template="plotly_white",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#0f172a"),
                            title_x=0.02
                        )
                        st.plotly_chart(fig_roll, use_container_width=True)

            except Exception as e:
                st.error(f"回测发生错误: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
    if not run_btn and last_result:
        cached_params = last_result["params"]
        engine = last_result["engine"]
        loader = last_result["loader"]
        metrics = last_result["metrics"]
        stock_list = last_result["stock_list"]
        initial_cash = cached_params["initial_cash"]
        selected_stocks = cached_params["selected_stocks"]
        start_date = cached_params["start_date"]
        end_date = cached_params["end_date"]
        benchmark_mode = cached_params["benchmark_mode"]
        benchmark_code = cached_params["benchmark_code"]
        request_delay_seconds = cached_params["request_delay_seconds"]
        backtest_engine = cached_params["backtest_engine"]
        strategy_name = cached_params["strategy_name"]
        strategy_params = cached_params["strategy_params"]
        render_backtest_report(
            engine=engine,
            loader=loader,
            metrics=metrics,
            stock_list=stock_list,
            initial_cash=initial_cash,
            selected_stocks=selected_stocks,
            start_date=start_date,
            end_date=end_date,
            benchmark_mode=benchmark_mode,
            benchmark_code=benchmark_code,
            request_delay_seconds=request_delay_seconds,
            backtest_engine=backtest_engine,
            strategy_name=strategy_name,
            strategy_params=strategy_params
        )
    if not run_btn and not last_result:
        st.info("👈 请在左侧侧边栏设置参数并点击“开始回测”")
        st.markdown("""
        ### 系统功能说明
        1. **月线趋势与估值轮动策略**
           - **核心思想**: 结合技术面（月线趋势）与基本面（股息率估值）进行轮动。
           - **买入条件**: 月线突破 MA60 + BOLL 回踩 + 周线金叉 + 股息率 > 4.5%。
           - **卖出条件**: 股息率下降导致估值过高时分批止盈。
        2. **双均线策略**
           - **核心思想**: 经典的趋势跟踪策略。
           - **逻辑**: 短期均线上穿长期均线做多，下穿平仓。
        ### 使用指南
        1. 在左侧选择**股票池**（默认全选）。
        2. 选择**策略**并调整对应参数。
        3. 设置**回测区间**和**初始资金**。
        4. 点击**开始回测**按钮查看报告。
        """)
else:
    st.title("🧪 模拟盘")
    selected_stocks = paper_params["selected_stocks"]
    paper_engine = paper_params["paper_engine"]
    strategy_name = paper_params["strategy_name"]
    strategy_params = paper_params["strategy_params"]
    account_file = paper_params["account_file"]
    initial_cash = paper_params["initial_cash"]
    run_once_btn = paper_params["run_once_btn"]
    run_loop_btn = paper_params["run_loop_btn"]
    interval_minutes = paper_params["interval_minutes"]
    start_time = paper_params["start_time"]
    end_time = paper_params["end_time"]
    max_runs = paper_params["max_runs"]
    st.caption(f"股票池: {len(selected_stocks)} 只 | 引擎: {paper_engine} | 账户文件: {account_file} | 运行时间: {start_time} ~ {end_time}")
    if run_once_btn or run_loop_btn:
        if not selected_stocks:
            st.error("请至少选择一只股票！")
            st.stop()
        with st.spinner("正在加载数据并执行模拟盘..."):
            if paper_engine == "vn.py":
                if not VNPY_AVAILABLE:
                    st.error("未检测到 vn.py 依赖")
                    st.stop()
                start_vnpy_engine()
                st.success("vn.py 引擎已初始化")
            else:
                loader = RealTimeDataLoader(DataConfig())
                loader.load_all(selected_stocks)
                if strategy_name == "月线趋势与估值轮动":
                    strategy = MonthlyTrendDividendRotation(
                        dividend_buy_threshold=strategy_params["dividend_buy_threshold"],
                        dividend_sell_threshold_50=strategy_params["dividend_sell_threshold_50"],
                        dividend_sell_threshold_clear=strategy_params["dividend_sell_threshold_clear"],
                        boll_pullback_lower=strategy_params["boll_pullback_lower"],
                        boll_pullback_upper=strategy_params["boll_pullback_upper"]
                    )
                else:
                    strategy = DoubleMAStrategy(
                        short_window=strategy_params["short_window"],
                        long_window=strategy_params["long_window"]
                    )
                broker = SimulatedBroker(account_file=account_file, initial_cash=initial_cash)
                engine = PaperTradingEngine(
                    strategy=strategy,
                    broker=broker,
                    loader=loader,
                    stk_pool=selected_stocks
                )
                if run_loop_btn:
                    loop_max_runs = max_runs if max_runs > 0 else None
                    engine.run_loop(
                        interval_minutes=interval_minutes,
                        start_time=start_time,
                        end_time=end_time,
                        max_runs=loop_max_runs
                    )
                else:
                    engine.run_daily()
            st.success("模拟盘执行完成")
    if paper_engine == "vn.py":
        st.info("vn.py 模拟盘需要配置网关与账户后才可显示持仓与交易")
    else:
        broker = SimulatedBroker(account_file=account_file, initial_cash=initial_cash)
        positions = broker.get_positions()
        trades = broker.trades
        cash = broker.get_cash()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("可用资金", f"{cash:,.2f}")
        with col2:
            st.metric("持仓数量", f"{len(positions)}")
        with col3:
            st.metric("交易次数", f"{len(trades)}")
        st.subheader("持仓明细")
        if positions:
            df_positions = pd.DataFrame([{"股票代码": k, "数量": v} for k, v in positions.items()])
            st.dataframe(df_positions, use_container_width=True)
        else:
            st.info("暂无持仓")
        st.subheader("交易记录")
        if trades:
            df_trades = pd.DataFrame(trades)
            st.dataframe(df_trades, use_container_width=True)
        else:
            st.info("暂无交易记录")
