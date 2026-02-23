"""
量化回测系统 Web 可视化界面
基于 Streamlit 和 Plotly 构建
"""

import sys
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

# 添加项目根目录到 sys.path，确保能导入 src 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.config import BacktestConfig, DataConfig, STOCK_POOL
from src.data.loader import DataLoader
from src.backtest.engine import BacktestEngine
from src.strategy.monthly_trend_rotation import MonthlyTrendDividendRotation
from src.strategy.double_ma import DoubleMAStrategy
from src.reporting.metrics import compute_metrics


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
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #333;
    }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
</style>
""", unsafe_allow_html=True)


# --- 数据加载 (缓存) ---
@st.cache_resource
def get_data_loader():
    """
    初始化并加载数据 (缓存结果，避免重复加载)
    """
    data_config = DataConfig()
    loader = DataLoader(data_config)
    # 这里可以添加一个进度条，但在 cache 函数内部比较难控制
    # 简单起见，直接加载
    print("Web: Loading data...")
    loader.load_all(STOCK_POOL)
    return loader

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("回测参数设置")
    
    # 1. 股票池
    st.subheader("股票池")
    selected_stocks = st.multiselect(
        "选择回测股票",
        options=STOCK_POOL,
        default=STOCK_POOL,
        help="默认加载配置文件中的白马股池"
    )
    
    # 2. 策略选择
    st.subheader("策略配置")
    strategy_name = st.selectbox(
        "选择策略",
        options=["月线趋势与估值轮动", "双均线策略 (20/60)"],
        index=0
    )
    
    # 策略参数动态展示
    strategy_params = {}
    if strategy_name == "月线趋势与估值轮动":
        st.info("策略逻辑：月线MA60趋势 + 股息率估值轮动 + 周线辅助")
        div_threshold = st.number_input("买入股息率阈值", value=0.045, step=0.001, format="%.3f")
        strategy_params["dividend_buy_threshold"] = div_threshold
    elif strategy_name == "双均线策略 (20/60)":
        st.info("策略逻辑：短期均线上穿长期均线买入，下穿卖出")
        short_window = st.number_input("短期窗口", value=20, step=1)
        long_window = st.number_input("长期窗口", value=60, step=1)
        strategy_params["short_window"] = short_window
        strategy_params["long_window"] = long_window
    
    # 3. 资金与费率
    st.subheader("账户设置")
    initial_cash = st.number_input("初始资金", value=1_000_000, step=100_000)
    commission = st.number_input("手续费率", value=0.0003, step=0.0001, format="%.4f")
    
    # 4. 时间范围
    st.subheader("回测区间")
    start_date = st.date_input("开始日期", value=date(2018, 1, 1))
    end_date = st.date_input("结束日期", value=date.today())
    
    run_btn = st.button("开始回测", type="primary", use_container_width=True)

# --- 主页面逻辑 ---
st.title("📈 投滚量化回测系统")

if run_btn:
    if not selected_stocks:
        st.error("请至少选择一只股票！")
        st.stop()
        
    # 1. 获取数据
    with st.spinner("正在加载数据与初始化策略..."):
        loader = get_data_loader()
        
        # 2. 初始化配置
        backtest_config = BacktestConfig(
            initial_cash=initial_cash,
            commission_rate=commission,
            slippage=0.001
        )
        
        # 3. 初始化策略
        if strategy_name == "月线趋势与估值轮动":
            strategy = MonthlyTrendDividendRotation(
                dividend_buy_threshold=strategy_params["dividend_buy_threshold"]
            )
        else:
            strategy = DoubleMAStrategy(
                short_window=strategy_params["short_window"],
                long_window=strategy_params["long_window"]
            )
            
        # 4. 运行回测
        engine = BacktestEngine(
            config=backtest_config,
            loader=loader,
            strategy=strategy,
            stk_pool=selected_stocks # 使用用户选择的股票池
        )
        
        try:
            # 捕获标准输出以避免打印到终端干扰
            engine.run(start_date, end_date)
            
            # 5. 计算指标
            metrics = compute_metrics(engine.equity_curve, engine.trades, initial_cash)
            
            # --- 结果展示 ---
            
            # A. 核心指标卡片
            col1, col2, col3, col4 = st.columns(4)
            
            def style_metric(label, value, is_percent=True, color_judge=False):
                fmt_val = f"{value:.2%}" if is_percent else f"{value:.4f}"
                color_class = ""
                if color_judge:
                    if value > 0: color_class = "positive"
                    elif value < 0: color_class = "negative"
                
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
                
            st.divider()
            
            # B. 权益曲线图
            st.subheader("收益曲线")
            if engine.equity_curve:
                df_equity = pd.DataFrame([{"Date": p.date, "Total Assets": p.total_assets} for p in engine.equity_curve])
                df_equity["Date"] = pd.to_datetime(df_equity["Date"])
                
                # 计算基准收益 (简单用第一只股票的涨跌幅作为参考，或者画一条水平线)
                # 这里简单画一条初始资金线
                df_equity["Baseline"] = initial_cash
                
                fig = px.line(df_equity, x="Date", y=["Total Assets", "Baseline"], 
                              labels={"value": "资产净值", "variable": "曲线类型"},
                              color_discrete_map={"Total Assets": "#2E86C1", "Baseline": "#E74C3C"})
                
                fig.update_layout(xaxis_title="", yaxis_title="总资产", legend_title="")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("没有生成权益数据，可能是回测区间内没有交易日或数据缺失。")
            
            # C. 详细数据
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.subheader("交易记录")
                if engine.trades:
                    df_trades = pd.DataFrame([
                        {
                            "日期": t.date,
                            "股票代码": t.symbol,
                            "操作": t.action,
                            "价格": f"{t.price:.2f}",
                            "数量": t.quantity,
                            "佣金": f"{t.commission:.2f}",
                            "备注": t.note
                        }
                        for t in engine.trades
                    ])
                    # 样式高亮
                    def color_action(val):
                        color = '#d4edda' if val == 'BUY' else '#f8d7da' # green/red light
                        return f'background-color: {color}'
                        
                    st.dataframe(df_trades.style.applymap(color_action, subset=['操作']), use_container_width=True)
                else:
                    st.info("回测期间无交易记录。")
                    
            with col_right:
                st.subheader("回测结果摘要")
                df_metrics = pd.DataFrame(list(metrics.items()), columns=["指标", "数值"])
                # 格式化数值
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
                
        except Exception as e:
            st.error(f"回测发生错误: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

else:
    st.info("👈 请在左侧侧边栏设置参数并点击“开始回测”")
    
    # 首页展示一些静态信息或说明
    st.markdown("""
    ### 系统功能说明
    
    本系统支持以下策略回测：
    
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
