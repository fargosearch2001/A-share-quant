### **量化策略开发说明书 v1.0**

**策略名称:** 月线趋势与估值轮动策略
**策略类型:** 多因子选股 / 择时交易策略
**股票池:** 固定股票池（白名单），共19只股票（见下文）。

------

#### **1. 基础数据准备**

- **数据精度:**
  - 日线数据（前复权）: 用于计算周线、月线指标。
  - 周线数据（前复权）: 用于条件4的判断。
  - 月线数据（前复权）: 用于主要趋势判断。
- **关键字段:**
  - `close`: 收盘价
  - `high`: 最高价
  - `low`: 最低价
  - `volume`: 成交量
- **固定股票池（List`stk_pool`）:**
  `['000001.SZ', '000538.SZ', '003816.SZ', '601985.SS', '600690.SS', '601066.SS', '600030.SS', '600309.SS', '600036.SS', '600887.SS', '000333.SZ', '000651.SZ', '601728.SS', '600886.SS', '601857.SS', '601919.SS', '600519.SS', '000858.SZ']` (需确认交易所代码后缀)

------

#### **2. 策略逻辑分解与量化因子定义**

我们将您的策略分解为三个核心模块：**买入信号模块（含两种模式）**、**卖出/减仓信号模块**和**仓位管理模块**。

##### **2.1 模块一：买入信号 A —— “低位启动”模式**

该模式用于捕捉长期下跌后，可能开启新一轮上涨周期的股票。

- **触发条件 (必须同时满足 AND):**
  1. **股票范围筛选:** `stock in stk_pool`
  2. **月线首次突破60月均线:**
     - 定义 `MA60_MONTH` = 过去60个月的月线`close`的简单移动平均。
     - **首次突破逻辑:** 这是一个关键点。我们需要定义一个“观察窗口”来确认“首次”。
       - 条件 A (当前突破): `当月close > MA60_MONTH` 且 `当月low <= MA60_MONTH` (确保是实体或影线突破，不完全等同于“收盘价完全站上”，但更精确。根据您的描述“月线柱子即收盘价完全站上”，可以简化为 `当月close > MA60_MONTH` 且 `当月open` 也大于 `MA60_MONTH`，但这会过滤掉下影线突破。建议采用`当月close > MA60_MONTH`且`当月low < MA60_MONTH`，表示收盘确认站上）。
       - 条件 B (前期跌破): 在过去的N个月内（例如N=6或12），存在至少一个月线`close` < `MA60_MONTH`。更严格的“首次”定义是：**上月**的`close` < `MA60_MONTH`，而**本月**`close` > `MA60_MONTH`。这样信号最清晰。
       - **量化定义:** `REF(close_monthly, 1) < REF(MA60_MONTH, 1) AND close_monthly > MA60_MONTH`
  3. **月线收盘价确认:** 为了满足“完全站上”，可以增加条件 `close_monthly > MA60_MONTH` （已包含在上一步）。
- **建仓时机 (在上述条件触发后):**
  - **指标:** 前复权价格的日线布林带（Bollinger Bands，常用参数20,2）。
  - **触发逻辑:** 等待价格回调。
  - **量化定义:** 当`日线close` 回踩至 `BOLL_MID` (即20日线) 附近。
    - “偏上一点” : `close` 在 `BOLL_MID * 1.01` 和 `BOLL_MID` 之间。
    - “中轨” : `close` 在 `BOLL_MID * 0.99` 和 `BOLL_MID * 1.01` 之间。
    - “偏下一点” : `close` 在 `BOLL_MID * 0.99` 和 `BOLL_MID * 0.97` 之间。
  - **执行:** 当价格进入预设的回踩区间时，**买入部分仓位**（具体仓位由模块三决定）。

##### **2.2 模块二：买入信号 B —— “上升趋势调整结束”模式**

该模式用于捕捉处于上升主趋势中，完成月线级别调整后，重启上涨的股票。

- **前提背景判断 (用于筛选处于上升通道且可能调整的股票):**
  1. **已站上60月线:** `close_monthly > MA60_MONTH` (连续多个月，例如至少3个月)。
  2. **均线多头排列:** `MA5_MONTH > MA10_MONTH > MA20_MONTH > MA30_MONTH` (表示长期均线在抬升)。
- **调整信号 (出现以下情况，说明可能开始调整):**
  1. **月线MACD绿柱:** `MACD_bar_MONTH < 0`。其中 `MACD_bar_MONTH = DIFF - DEA`。
- **调整结束信号 (买入触发条件，必须同时满足 AND):**
  1. **周线价格突破:** 前复权周线收盘价 `close_weekly` 首次突破 `MA60_WEEK` (过去60周收盘价的简单移动平均)。(首次突破逻辑类似月线，可用`REF(close_weekly,1) < REF(MA60_WEEK,1) AND close_weekly > MA60_WEEK`)。
  2. **周线均线金叉:** `MA20_WEEK` 上穿 `MA60_WEEK` 且 `MA30_WEEK` 上穿 `MA60_WEEK`。 (技术上为“两次金叉”，增强信号可靠性)。
  3. **月线MACD转正:** `MACD_bar_MONTH > 0`。这是一个滞后确认信号，表示空头能量衰竭，多头开始主导。
- **执行:** 当上述三个条件同时满足时，**买入部分仓位**（具体仓位由模块三决定）。

##### **2.3 模块三：估值面（股息率）仓位管理模块**

此模块是贯穿始终的仓位调整依据，适用于所有持仓股票。

- **因子定义:**

  - `Dividend_per_Share` = 去年一年的现金分红总额 / 总股本 (需手动录入或从财报获取)。
  - `Dividend_Yield` = `Dividend_per_Share` / `当前前复权股价`。

- **动态仓位调整逻辑 (基于股息率):**

  | 条件          | 操作                     | 量化逻辑                                     |
  | :------------ | :----------------------- | :------------------------------------------- |
  | **买入/加仓** | `Dividend_Yield >= 4.5%` | 符合基本面要求，可作为买入或加仓的信号之一。 |
  | **警戒线**    | `Dividend_Yield < 3.7%`  | **卖出一半**。减仓至原持仓市值的50%。        |
  | **减仓线**    | `Dividend_Yield < 3.5%`  | **卖出三分之二**。减仓至原持仓市值的33%。    |
  | **清仓线**    | `Dividend_Yield < 3.0%`  | **清仓**。卖出所有该股票持仓。               |

  *注：减仓操作是阶梯式的。例如，当股息率从4%降到3.6%时，触发“卖出一半”；若继续降到3.4%，则触发“卖出三分之二”，此时是在剩余一半的基础上再卖出三分之二，最终仓位约为初始的1/6。请与开发确认是**整体仓位的比例**还是**当前持仓的比例**。此处建议采用**当前持仓的比例**，即：新仓位 = 原仓位 * (1 - 卖出比例)。*

------

#### **3. 策略执行流程（伪代码）**

python

```
# 初始化
stk_pool = [...]
holdings = {} # 记录持仓股票及数量
dividend_data = {} # 记录每只股票的年每股分红

# 每日运行
for stock in stk_pool:
    # 0. 更新股息率
    dy = dividend_data[stock] / get_current_price(stock)
    
    # 1. 检查估值卖出条件 (优先级最高)
    if stock in holdings:
        if dy < 0.03:
            sell_all(stock)
        elif dy < 0.035:
            sell_percent(stock, 2/3) # 卖出当前持仓的2/3
        elif dy < 0.037:
            sell_percent(stock, 0.5) # 卖出当前持仓的一半
        # else: 持有或考虑加仓
            
    # 2. 检查买入信号 (仅在未持仓或持仓可加仓时)
    if stock not in holdings or can_add_position_logic(stock):
        buy_signal_A = check_signal_A(stock) # 低位启动
        buy_signal_B = check_signal_B(stock) # 调整结束
        
        # 如果满足任一买入信号，且估值达标
        if (buy_signal_A or buy_signal_B) and dy >= 0.045:
            # 如果是信号A，还需等待日线回踩BOLL中轨
            if buy_signal_A:
                if is_price_around_boll_mid(stock, level='daily'):
                    buy_partial(stock)
            else: # 信号B，直接买入
                buy_partial(stock)

# 辅助函数定义
def check_signal_A(stock):
    # 获取月线数据
    ma60_month = get_ma(stock, 60, 'monthly')
    close_month = get_price(stock, 'monthly')
    close_month_yesterday = get_price(stock, 'monthly', offset=-1)
    
    # 条件: 昨日收盘 < 60月线 AND 今日收盘 > 60月线
    return (close_month_yesterday < ma60_month_yesterday) and (close_month > ma60_month)

def check_signal_B(stock):
    # 1. 背景判断: 月线多头 (简化处理，可增加)
    # 2. 周线突破60周线
    ma60_week = get_ma(stock, 60, 'weekly')
    close_week = get_price(stock, 'weekly')
    close_week_yesterday = get_price(stock, 'weekly', offset=-1)
    cond_week_break = (close_week_yesterday < ma60_week_yesterday) and (close_week > ma60_week)
    
    # 3. 周线20、30上穿60
    ma20_week = get_ma(stock, 20, 'weekly')
    ma30_week = get_ma(stock, 30, 'weekly')
    cond_week_cross = (ma20_week > ma60_week) and (ma30_week > ma60_week) and \
                      (ma20_week_yesterday <= ma60_week_yesterday) and (ma30_week_yesterday <= ma60_week_yesterday) # 确保是当天刚上穿
    
    # 4. 月线MACD转正
    macd_month = get_macd(stock, 'monthly')
    cond_macd_pos = (macd_month['bar'] > 0) and (macd_month['bar_yesterday'] <= 0)
    
    return cond_week_break and cond_week_cross and cond_macd_pos

def is_price_around_boll_mid(stock, level='daily'):
    boll_mid = get_boll_mid(stock, 20, level) # 即20日线
    price = get_price(stock, level)
    
    # 定义在mid线上下1%范围内
    lower_bound = boll_mid * 0.99
    upper_bound = boll_mid * 1.01
    return lower_bound <= price <= upper_bound
```



#### **4. 注意事项与风险提示**

1. **数据对齐:** 确保在计算月线、周线指标时，使用的是相应周期的前复权数据。不同周期数据之间切换时，要注意价格的连续性和复权处理的一致性。
2. **“首次”的定义:** 上述逻辑中使用了最简单的“昨日不满足，今日满足”来定义“首次”。在实际回测中，可能需要考虑更长的过滤期（例如过去N个月内没有出现过满足条件的情况），以减少信号频繁出现的可能。
3. **未来函数:** `Dividend_per_Share` 使用的是“去年一年的分红额”，这在当年分红方案公布后就可以确定，但在回测时，需要确保使用分红方案公告日之后的数据，而不是简单使用全年的 hindsight data。
4. **交易成本与滑点:** 该策略交易频率较低（月线级别），但回测时仍需考虑佣金和印花税。
5. **参数优化:** 文中的参数（如60月线、20/30/60周线、4.5%/3.7%股息率阈值）是基于您的经验设定，在实盘或回测前，建议进行稳定性测试。