"""
股票列表数据模块
从 AkShare 获取A股股票列表
"""

import os
# 禁用代理
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import akshare as ak
from typing import Dict

# 尝试从 AkShare 获取股票列表，如果失败则使用预设列表
_STOCK_LIST = None

def get_a_stock_list() -> Dict[str, str]:
    """
    获取A股股票列表，返回 {代码: 名称} 的字典
    """
    global _STOCK_LIST
    
    if _STOCK_LIST is not None:
        return _STOCK_LIST
    
    try:
        # 获取A股股票列表
        df = ak.stock_info_a_code_name()
        _STOCK_LIST = dict(zip(df['code'], df['name']))
        print(f"成功从 AkShare 获取 {len(_STOCK_LIST)} 只A股股票")
        return _STOCK_LIST
    except Exception as e:
        print(f"从 AkShare 获取股票列表失败: {e}")
        # 使用预设的常用股票列表
        _STOCK_LIST = {
            # 沪深主板
            '600000.SS': '浦发银行',
            '600016.SS': '民生银行',
            '600019.SS': '宝钢股份',
            '600028.SS': '中国石化',
            '600030.SS': '中信证券',
            '600036.SS': '招商银行',
            '600048.SS': '保利发展',
            '600050.SS': '中国联通',
            '600104.SS': '上汽集团',
            '600176.SS': '中国巨石',
            '600309.SS': '万华化学',
            '600519.SS': '贵州茅台',
            '600547.SS': '山东黄金',
            '600690.SS': '海尔智家',
            '600887.SS': '伊利股份',
            '600900.SS': '长江电力',
            '601006.SS': '大秦铁路',
            '601066.SS': '中信建投',
            '601088.SS': '中国神华',
            '601166.SS': '兴业银行',
            '601288.SS': '农业银行',
            '601318.SS': '中国平安',
            '601328.SS': '交通银行',
            '601398.SS': '工商银行',
            '601601.SS': '中国太保',
            '601668.SS': '中国建筑',
            '601688.SS': '中国船舶',
            '601728.SS': '中国电信',
            '601766.SS': '中国中车',
            '601857.SS': '中国石油',
            '601888.SS': '中国中铁',
            '601985.SS': '中国核电',
            '601988.SS': '中国银行',
            '601989.SS': '中国重工',
            '601919.SS': '中远海控',
            
            # 深圳主板
            '000001.SZ': '平安银行',
            '000002.SZ': '万科A',
            '000063.SZ': '中兴通讯',
            '000333.SZ': '美的集团',
            '000338.SZ': '潍柴动力',
            '000429.SZ': '粤高速A',
            '000538.SZ': '云南白药',
            '000568.SZ': '泸州老窖',
            '000651.SZ': '格力电器',
            '000661.SZ': '长春高新',
            '000858.SZ': '五粮液',
            '000876.SZ': '新希望',
            '000895.SZ': '系数控',
            '000938.SZ': '紫光股份',
            
            # 创业板
            '300001.SZ': '睿创微纳',
            '300015.SZ': '爱尔眼科',
            '300059.SZ': '东方财富',
            '300122.SZ': '智飞生物',
            '300124.SZ': '汇川技术',
            '300142.SZ': '沃森生物',
            '300750.SZ': '宁德时代',
            '300896.SZ': '爱美客',
            
            # 科创板
            '688001.SS': '华兴源创',
            '688002.SS': '天准科技',
            '688005.SS': '容百科技',
            '688006.SS': '华大基因',
            '688008.SS': '澜起科技',
            '688009.SS': '心脉医疗',
            '688012.SS': '中微公司',
            '688185.SS': '康希诺',
            '688317.SS': '科创板',
            '688981.SS': '中芯国际',
        }
        print(f"使用预设股票列表，共 {len(_STOCK_LIST)} 只股票")
        return _STOCK_LIST


def search_stocks(keyword: str) -> list:
    """
    搜索股票，支持代码或名称模糊匹配
    """
    stock_list = get_a_stock_list()
    keyword = keyword.upper().strip()
    
    results = []
    for code, name in stock_list.items():
        # 去掉后缀进行匹配
        code_simple = code.replace('.SS', '').replace('.SZ', '')
        if keyword in code_simple or keyword in name:
            results.append({
                'code': code,
                'name': name,
                'display': f"{code_simple} - {name}"
            })
    
    # 按代码排序
    results.sort(key=lambda x: x['code'])
    return results[:20]  # 最多返回20个结果
