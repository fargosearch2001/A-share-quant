
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

class Broker(ABC):
    @abstractmethod
    def get_cash(self) -> float:
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, int]:
        pass

    @abstractmethod
    def buy(self, symbol: str, price: float, quantity: int, note: str = "") -> bool:
        pass

    @abstractmethod
    def sell(self, symbol: str, price: float, quantity: int, note: str = "") -> bool:
        pass

class SimulatedBroker(Broker):
    def __init__(self, account_file: str = "paper_account.json", initial_cash: float = 100000.0):
        self.account_file = account_file
        self.initial_cash = initial_cash
        self._load_account()

    def _load_account(self):
        if os.path.exists(self.account_file):
            with open(self.account_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.cash = data.get("cash", 0.0)
                self.positions = data.get("positions", {})
                self.trades = data.get("trades", [])
        else:
            self.cash = self.initial_cash
            self.positions = {}
            self.trades = []
            self._save_account()

    def _save_account(self):
        data = {
            "cash": self.cash,
            "positions": self.positions,
            "trades": self.trades,
            "updated_at": datetime.now().isoformat()
        }
        with open(self.account_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def get_cash(self) -> float:
        return self.cash

    def get_positions(self) -> Dict[str, int]:
        return self.positions

    def buy(self, symbol: str, price: float, quantity: int, note: str = "") -> bool:
        cost = price * quantity
        if self.cash >= cost:
            self.cash -= cost
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            self._record_trade("BUY", symbol, price, quantity, note)
            self._save_account()
            print(f"[SIM BUY] {symbol} {quantity} @ {price:.2f} | Cash left: {self.cash:.2f}")
            return True
        else:
            print(f"[SIM FAIL] Not enough cash to buy {symbol}. Need {cost:.2f}, have {self.cash:.2f}")
            return False

    def sell(self, symbol: str, price: float, quantity: int, note: str = "") -> bool:
        current_qty = self.positions.get(symbol, 0)
        if current_qty >= quantity:
            revenue = price * quantity
            self.cash += revenue
            self.positions[symbol] -= quantity
            if self.positions[symbol] == 0:
                del self.positions[symbol]
            self._record_trade("SELL", symbol, price, quantity, note)
            self._save_account()
            print(f"[SIM SELL] {symbol} {quantity} @ {price:.2f} | Cash: {self.cash:.2f}")
            return True
        else:
            print(f"[SIM FAIL] Not enough positions to sell {symbol}. Have {current_qty}, need {quantity}")
            return False

    def _record_trade(self, action: str, symbol: str, price: float, quantity: int, note: str):
        self.trades.append({
            "time": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "note": note
        })
