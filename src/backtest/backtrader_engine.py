import backtrader as bt
import pandas as pd
from datetime import date
from typing import Dict, List, Optional

from src.config import BacktestConfig
from src.data.models import TradeRecord, EquityPoint
from src.strategy.monthly_trend_rotation import MonthlyTrendDividendRotation


class _BacktraderRecorder(bt.Strategy):
    params = dict(trade_lot=100, target_percent=0.1)

    def __init__(self):
        self.equity_curve: List[EquityPoint] = []
        self.trades: List[TradeRecord] = []
        self._last_equity_date: Optional[date] = None

    def _record_equity(self):
        dt = self.datas[0].datetime.date(0)
        if self._last_equity_date == dt:
            return
        total_assets = float(self.broker.getvalue())
        cash = float(self.broker.getcash())
        market_value = total_assets - cash
        self.equity_curve.append(EquityPoint(dt, total_assets, cash, market_value))
        self._last_equity_date = dt

    def notify_order(self, order):
        if order.status != order.Completed:
            return
        action = "BUY" if order.isbuy() else "SELL"
        symbol = order.data._name
        note = order.info.get("note", "")
        size = int(abs(order.executed.size))
        self.trades.append(
            TradeRecord(
                date=order.data.datetime.date(0),
                symbol=symbol,
                action=action,
                price=float(order.executed.price),
                quantity=size,
                commission=float(order.executed.comm),
                note=note
            )
        )

    def _calc_target_size(self, data):
        price = float(data.close[0])
        if price <= 0:
            return 0
        cash = float(self.broker.getcash())
        target_cash = cash * float(self.p.target_percent)
        raw_size = int(target_cash / price)
        lots = raw_size // int(self.p.trade_lot)
        return int(lots * int(self.p.trade_lot))


class BacktraderDoubleMAStrategy(_BacktraderRecorder):
    params = dict(short_window=20, long_window=60, trade_lot=100, target_percent=0.1)

    def __init__(self):
        super().__init__()
        self._ma_short: Dict[str, bt.Indicator] = {}
        self._ma_long: Dict[str, bt.Indicator] = {}
        for data in self.datas:
            self._ma_short[data._name] = bt.indicators.SMA(data.close, period=self.p.short_window)
            self._ma_long[data._name] = bt.indicators.SMA(data.close, period=self.p.long_window)

    def next(self):
        self._record_equity()
        for data in self.datas:
            ma_short = self._ma_short[data._name]
            ma_long = self._ma_long[data._name]
            if len(data) < self.p.long_window:
                continue
            pos = self.getposition(data).size
            if pos == 0 and ma_short[0] > ma_long[0]:
                size = self._calc_target_size(data)
                if size > 0:
                    self.buy(data=data, size=size, exectype=bt.Order.Market, info=dict(note="DoubleMA Buy"))
            elif pos > 0 and ma_short[0] < ma_long[0]:
                self.sell(data=data, size=pos, exectype=bt.Order.Market, info=dict(note="DoubleMA Sell"))


class BacktraderMonthlyTrendStrategy(_BacktraderRecorder):
    params = dict(
        signals=None,
        dividend_buy_threshold=0.045,
        dividend_sell_threshold_50=0.0375,
        dividend_sell_threshold_clear=0.033,
        trade_lot=100,
        target_percent=0.2
    )

    def __init__(self):
        super().__init__()
        self._signals = self.p.signals or {}
        self._sold_half: Dict[str, bool] = {}

    def next(self):
        self._record_equity()
        dt = pd.Timestamp(self.datas[0].datetime.date(0))
        for data in self.datas:
            symbol = data._name
            if symbol not in self._signals:
                continue
            sig_df = self._signals[symbol]
            if dt not in sig_df.index:
                continue
            sig = sig_df.loc[dt]
            dy = float(sig.get("dividend_yield", 0))
            pos = self.getposition(data).size
            if pos > 0:
                if dy < self.p.dividend_sell_threshold_clear or dy < self.p.dividend_sell_threshold_50:
                    if not self._sold_half.get(symbol, False):
                        target_pos = int(pos * 0.5)
                        sell_qty = pos - target_pos
                        lot = int(self.p.trade_lot)
                        sell_qty = int(sell_qty // lot * lot)
                        if sell_qty > 0:
                            self.sell(data=data, size=sell_qty, exectype=bt.Order.Market, info=dict(note="DY Reduce"))
                            self._sold_half[symbol] = True
                            continue
                    self.sell(data=data, size=pos, exectype=bt.Order.Market, info=dict(note="DY Clear"))
                    self._sold_half.pop(symbol, None)
                    continue
                self._sold_half.pop(symbol, None)
            if pos == 0:
                if bool(sig.get("signal_A_condition", False)) or bool(sig.get("signal_B_condition", False)):
                    if dy >= self.p.dividend_buy_threshold:
                        size = self._calc_target_size(data)
                        if size > 0:
                            self.buy(data=data, size=size, exectype=bt.Order.Market, info=dict(note="Trend Buy"))
                            self._sold_half.pop(symbol, None)


class BacktraderEngine:
    def __init__(
        self,
        config: BacktestConfig,
        loader,
        stk_pool: List[str],
        strategy_name: str,
        strategy_params: Dict
    ):
        self.config = config
        self.loader = loader
        self.stk_pool = stk_pool
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params
        self.equity_curve: List[EquityPoint] = []
        self.trades: List[TradeRecord] = []

    def _build_signals(self) -> Dict[str, pd.DataFrame]:
        class _FakeEngine:
            def __init__(self, loader, stk_pool):
                self.loader = loader
                self.stk_pool = stk_pool
                self.current_date = date.min
                self.cash = 0.0
                self.positions = {}

        strategy = MonthlyTrendDividendRotation(
            dividend_buy_threshold=self.strategy_params.get("dividend_buy_threshold", 0.045),
            dividend_sell_threshold_50=self.strategy_params.get("dividend_sell_threshold_50", 0.0375),
            dividend_sell_threshold_clear=self.strategy_params.get("dividend_sell_threshold_clear", 0.033),
            boll_pullback_lower=self.strategy_params.get("boll_pullback_lower", 0.95),
            boll_pullback_upper=self.strategy_params.get("boll_pullback_upper", 1.05)
        )
        strategy.setup(_FakeEngine(self.loader, self.stk_pool))
        return strategy.signals

    def run(self, start_date: date, end_date: date) -> None:
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.config.initial_cash)
        cerebro.broker.setcommission(commission=self.config.commission_rate)

        for symbol in self.stk_pool:
            df = self.loader.get_data(symbol, "daily")
            if df.empty:
                continue
            mask = (df.index.date >= start_date) & (df.index.date <= end_date)
            df = df.loc[mask].copy()
            if df.empty:
                continue
            data = bt.feeds.PandasData(dataname=df, name=symbol)
            cerebro.adddata(data)

        if self.strategy_name == "月线趋势与估值轮动":
            signals = self._build_signals()
            cerebro.addstrategy(
                BacktraderMonthlyTrendStrategy,
                signals=signals,
                dividend_buy_threshold=self.strategy_params.get("dividend_buy_threshold", 0.045),
                dividend_sell_threshold_50=self.strategy_params.get("dividend_sell_threshold_50", 0.0375),
                dividend_sell_threshold_clear=self.strategy_params.get("dividend_sell_threshold_clear", 0.033),
                trade_lot=self.config.trade_lot,
                target_percent=self.strategy_params.get("target_percent", 0.2)
            )
        else:
            cerebro.addstrategy(
                BacktraderDoubleMAStrategy,
                short_window=self.strategy_params.get("short_window", 20),
                long_window=self.strategy_params.get("long_window", 60),
                trade_lot=self.config.trade_lot,
                target_percent=self.strategy_params.get("target_percent", 0.1)
            )

        results = cerebro.run()
        if not results:
            return
        strat = results[0]
        self.equity_curve = list(strat.equity_curve)
        self.trades = list(strat.trades)
