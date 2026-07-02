"""Constants for the 源通水务 integration."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sxxhynet"
NAME = "源通水务"

CONF_WATER_NUMBER = "water_number"
CONF_CODE = "code"

API_BASE = "http://www.sxxhynet.cn"
API_ENDPOINT = f"{API_BASE}/Wxcx.aspx"

STORAGE_KEY = "sxxhynet_data"
STORAGE_VERSION = 1

# 阶梯水价 (需要根据源通水务实际价格调整)
TIER_LEVEL_1 = 144   # m³ - 第2档起始用水量
TIER_LEVEL_2 = 207   # m³ - 第3档起始用水量
TIER_PRICE_1 = 3.05  # 元/m³ - 第1档水价
TIER_PRICE_2 = 4.00  # 元/m³ - 第2档水价
TIER_PRICE_3 = 5.00  # 元/m³ - 第3档水价
