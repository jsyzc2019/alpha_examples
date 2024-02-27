"""
一次生成多套特征，之后在`demo_html.py`中将用于比较多特征之间区别
"""
import os
import sys

from pathlib import Path

# 修改当前目录到上层目录，方便跨不同IDE中使用
pwd = str(Path(__file__).parents[1])
os.chdir(pwd)
sys.path.append(pwd)
print("pwd:", os.getcwd())
# ====================
import inspect
from datetime import datetime

from expr_codegen.codes import sources_to_exprs
from expr_codegen.tool import ExprTool
from loguru import logger

# 导入OPEN等特征
from sympy_define import *  # noqa

import polars as pl


def _code_block_1():
    # 不能提前filter的代码，filter会导致数据错误

    # 这里用未复权的价格更合适
    DOJI = four_price_doji(open, high, low, close)
    NEXT_DOJI = ts_delay(DOJI, -1)

    # 远期收益率
    RETURN_OO_1 = ts_delay(OPEN, -2) / ts_delay(OPEN, -1) - 1
    # RETURN_OO_2 = ts_delay(OPEN, -3) / ts_delay(OPEN, -1) - 1
    RETURN_OO_5 = ts_delay(OPEN, -6) / ts_delay(OPEN, -1) - 1
    RETURN_OO_10 = ts_delay(OPEN, -11) / ts_delay(OPEN, -1) - 1
    RETURN_OC_1 = ts_delay(CLOSE, -1) / ts_delay(OPEN, -1) - 1
    RETURN_CC_1 = ts_delay(CLOSE, -1) / CLOSE - 1
    RETURN_CO_1 = ts_delay(OPEN, -1) / CLOSE - 1


def _code_block_2():
    # filter后计算的代码

    # 多个特征，用来进行比较
    # FEATURE_01 = -abs_(cs_standardize_zscore(cs_winsorize_mad(ts_std_dev(ts_returns(CLOSE, 1), 5))))
    # FEATURE_02 = -abs_(cs_standardize_zscore(cs_winsorize_mad(ts_std_dev(ts_returns(CLOSE, 1), 10))))
    # FEATURE_03 = -abs_(cs_standardize_zscore(cs_winsorize_mad(ts_std_dev(ts_returns(CLOSE, 1), 20))))

    FEATURE_01 = ts_rank(CLOSE, 5)
    # FEATURE_02 = cs_neutralize_residual_multiple(ts_rank(CLOSE, 20) ** 3, ts_rank(CLOSE, 20), True)
    # FEATURE_03 = ts_rank(CLOSE, 5)


def code_to_string(code_block):
    source = inspect.getsource(code_block)
    raw, exprs_dict = sources_to_exprs(globals().copy(), source, safe=False)

    # 生成代码
    codes, G = ExprTool().all(exprs_dict, style='polars', template_file='template.py.j2',
                              replace=True, regroup=True, format=True,
                              date='date', asset='asset',
                              # 复制了需要使用的函数，还复制了最原始的表达式
                              extra_codes=(raw,))
    return codes


# ======================================
# 保存代码到指定文件
output_file = 'research/output1.py'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(code_to_string(_code_block_1))

# 保存代码到指定文件
output_file = 'research/output2.py'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(code_to_string(_code_block_2))

logger.info('转码完成')
# =======================================
# %% 生成因子
# 由于读写多，推荐放到内存盘
DATA_PATH = r'M:\data3\T1\data.parquet'
FEATURE_PATH = r'M:\data3\T1\feature.parquet'

df = pl.read_parquet(DATA_PATH)
df = df.rename({'time': 'date', 'code': 'asset', 'money': 'amount'})
# 提前过滤
df = df.filter(
    pl.col('date') > datetime(2018, 1, 1),  # 过滤要测试用的数据时间范围
    pl.col('paused') == 0,  # 过滤停牌
)
df = df.with_columns([
    # 后复权
    (pl.col(['open', 'high', 'low', 'close']) * pl.col('factor')).name.map(lambda x: x.upper()),
    # 成交额与成交量对数处理
    pl.col('amount').log1p().alias('LOG_AMOUNT'),
    pl.col('volume').log1p().alias('LOG_VOLUME'),
    # 添加常数列，也许后面用得上
    pl.lit(1).alias('ONE'),
    pl.lit(0).alias('ZERO'),
]).fill_nan(None)  # nan填充成null
logger.info('数据加载完成')

from research.output1 import main

df = main(df)

# st不参与后面的计算，也可以设置只计算中证500等
df = df.filter(~pl.col('is_st'))

from research.output2 import main

df = main(df)
# 明天涨停或跌停，过滤掉
df = df.filter(~pl.col('NEXT_DOJI'))

logger.info('特征计算完成')
# 推荐保存到内存盘中
df.write_parquet(FEATURE_PATH)
logger.info('特征保存完成')