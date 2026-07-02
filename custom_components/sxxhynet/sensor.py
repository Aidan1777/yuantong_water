"""Sensor platform for 源通水务 integration with persistent storage."""
from __future__ import annotations

import asyncio
import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_WATER_NUMBER,
    CONF_CODE,
    API_ENDPOINT,
    TIER_LEVEL_1,
    TIER_LEVEL_2,
    TIER_PRICE_1,
    TIER_PRICE_2,
    TIER_PRICE_3,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the 源通水务 sensor platform."""
    config = {**entry.data, **entry.options}
    entry_data = hass.data[DOMAIN][entry.entry_id]

    coordinator = SxxhynetCoordinator(hass, config, entry_data)
    await coordinator.async_config_entry_first_refresh()

    sensor = SxxhynetSensor(coordinator, config)

    entry_data["coordinator"] = coordinator
    entry_data["entities"] = [sensor]

    async_add_entities([sensor], True)


class SxxhynetCoordinator(DataUpdateCoordinator):
    """Coordinator for 源通水务 data with persistence."""

    def __init__(self, hass: HomeAssistant, config: dict, entry_data: dict):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=6),
        )
        self.config = config
        self._water_number = config[CONF_WATER_NUMBER]
        self._code = config.get(CONF_CODE, "")
        self._session: aiohttp.ClientSession | None = None
        self._entry_data = entry_data
        self._stored_data = entry_data.get("stored_data", {})
        self._cache_data = self._stored_data.get(self._water_number, {})

    async def _async_update_data(self) -> dict | None:
        """Fetch data from 源通水务, fall back to cache on failure."""
        try:
            data = await asyncio.wait_for(self._do_fetch(), timeout=30)
            if data:
                await self._save_to_storage(data)
                _LOGGER.info("源通水务数据更新成功: %s", data.get("date", ""))
                return data
        except asyncio.TimeoutError:
            _LOGGER.warning("源通水务连接超时，使用缓存数据")
        except Exception as ex:
            _LOGGER.warning("源通水务请求失败 (%s)，使用缓存数据", ex)

        if self._cache_data:
            _LOGGER.info("使用缓存的源通水务数据 (缓存: %s)", self._cache_data.get("date", "unknown"))
            return dict(self._cache_data)

        raise UpdateFailed("源通水务: 无法获取数据且无缓存")

    async def _do_fetch(self) -> dict | None:
        if self._session is None:
            self._session = aiohttp.ClientSession()

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.73(0x18004921) NetType/WIFI Language/zh_CN",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        }

        # Step 1: GET /Auth.aspx
        async with self._session.get(
            "http://www.sxxhynet.cn/Auth.aspx",
            headers=headers,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            cookies = resp.cookies
            session_id = cookies.get("ASP.NET_SessionId", "")
            if not session_id:
                _LOGGER.warning("无法获取 SessionId")
                return None

        # Step 2: GET Wxcx.aspx with code
        if not self._code:
            _LOGGER.warning("未配置 code，无法请求")
            return None

        api_url = f"{API_ENDPOINT}?code={self._code}&state=STATE"
        cookie_header = f"ASP.NET_SessionId={session_id}"

        async with self._session.get(
            api_url, headers={**headers, "Cookie": cookie_header},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            html = await resp.text()
            viewstate = _extract_input(html, "__VIEWSTATE")
            viewstategenerator = _extract_input(html, "__VIEWSTATEGENERATOR")
            eventvalidation = _extract_input(html, "__EVENTVALIDATION")

            if not viewstate or not eventvalidation:
                _LOGGER.warning("VIEWSTATE 为空，code 可能已过期")
                return None

        # Step 3: POST query
        post_data = {
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstategenerator,
            "__EVENTVALIDATION": eventvalidation,
            "DropDownList1": self._water_number,
            "btncx": "查询",
        }
        post_headers = {
            **headers,
            "Cookie": cookie_header,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "http://www.sxxhynet.cn",
            "Referer": api_url,
        }
        async with self._session.post(
            api_url, headers=post_headers, data=post_data,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("POST 查询返回 %s", resp.status)
                return None
            result_html = await resp.text()

        parsed = _parse_response(result_html)
        processed = _process_data(parsed, self._water_number)
        return processed

    async def _save_to_storage(self, data: dict) -> None:
        store = self._entry_data["store"]
        stored = self._entry_data["stored_data"]
        stored[self._water_number] = data
        self._cache_data = data
        await store.async_save(stored)
        _LOGGER.debug("数据已持久化到 HA 存储")


# ——— 纯函数工具 ———

def _extract_input(html: str, name: str) -> str | None:
    m = re.search(rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([^"]*)"', html)
    return m.group(1) if m else None


def _extract_numeric(html: str, name: str) -> float:
    v = _extract_input(html, name)
    try:
        return float(v) if v else 0
    except (ValueError, TypeError):
        return 0


def _extract_table_data(html: str) -> list[dict]:
    tm = re.search(r'<table[^>]*id="GridView1"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not tm:
        return []
    rows = re.findall(r'<tr>(.*?)</tr>', tm.group(1), re.DOTALL)
    data = []
    for row in rows[1:]:
        cells = re.findall(r'<td>(.*?)</td>', row, re.DOTALL)
        if len(cells) >= 5:
            data.append({
                "month": cells[0].strip(),
                "base_reading": cells[1].strip(),
                "usage": float(cells[2].strip()) if cells[2].strip() else 0,
                "amount": float(cells[3].strip()) if cells[3].strip() else 0,
                "status": cells[4].strip(),
            })
    return data


def _parse_response(html: str) -> dict:
    return {
        "usage": _extract_numeric(html, "txtsyl"),
        "amount": _extract_numeric(html, "txtysje"),
        "penalty": _extract_numeric(html, "txtznj"),
        "last_balance": _extract_numeric(html, "txtsyjy"),
        "current_balance": _extract_numeric(html, "txtqfje"),
        "wechat_amount": _extract_numeric(html, "wxjnje"),
        "name": _extract_input(html, "txtxm") or "",
        "address": _extract_input(html, "txtdz") or "",
        "phone": _extract_input(html, "txtdh") or "",
        "area": _extract_input(html, "txtyhpq") or "",
        "table_data": _extract_table_data(html),
    }


def _process_data(data: dict, water_number: str) -> dict:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    daylist, monthlist, yearlist = [], [], []

    for row in data.get("table_data", []):
        month = row["month"]
        usage = row["usage"]
        amount = row["amount"]
        monthlist.append({"month": month, "monthEleNum": usage, "monthEleCost": amount})

        try:
            year = int(month[:4])
            mon = int(month[4:6])
            dm = calendar.monthrange(year, mon)[1]
            du = round(usage / dm, 2) if dm else 0
            dc = round(amount / dm, 2) if dm else 0
            for d in range(1, dm + 1):
                ds = f"{year}-{mon:02d}-{d:02d}"
                daylist.append({"day": ds, "dayEleNum": du, "dayEleCost": dc})
        except Exception:
            pass

    year_map = {}
    for m in monthlist:
        y = m["month"][:4]
        if y not in year_map:
            year_map[y] = {"year": y, "yearEleNum": 0, "yearEleCost": 0}
        year_map[y]["yearEleNum"] += m["monthEleNum"]
        year_map[y]["yearEleCost"] += m["monthEleCost"]

    yearlist = sorted(year_map.values(), key=lambda x: x["year"], reverse=True)
    daylist.sort(key=lambda x: x["day"], reverse=True)
    monthlist.sort(key=lambda x: x["month"], reverse=True)

    balance = data.get("current_balance", 0)
    if daylist:
        recent = daylist[:7]
        avg_cost = sum(d["dayEleCost"] for d in recent) / max(len(recent), 1)
        estimated = round(balance / avg_cost) if avg_cost > 0 else 0
    else:
        estimated = 0

    return {
        "water_number": water_number,
        "date": now_str,
        "balance": balance,
        "usage": data.get("usage", 0),
        "amount": data.get("amount", 0),
        "penalty": data.get("penalty", 0),
        "last_balance": data.get("last_balance", 0),
        "wechat_amount": data.get("wechat_amount", 0),
        "name": data.get("name", ""),
        "address": data.get("address", ""),
        "phone": data.get("phone", ""),
        "area": data.get("area", ""),
        "daylist": daylist,
        "monthlist": monthlist,
        "yearlist": yearlist,
        "estimated_days": estimated,
    }


# ——— Entity ———

class SxxhynetSensor(SensorEntity):
    """源通水务 sensor — uses persistent cache, won't break on code expiry."""

    def __init__(self, coordinator: SxxhynetCoordinator, config: dict):
        self.coordinator = coordinator
        water_number = config.get(CONF_WATER_NUMBER, "unknown")
        self._attr_unique_id = f"sxxhynet_{water_number}"
        self._attr_name = f"源通水务 {water_number}"
        self._attr_icon = "mdi:water"
        self._attr_native_unit_of_measurement = "元"

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get("balance", 0)
        return 0

    @property
    def available(self):
        return True  # 始终可用

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {}

        if self.coordinator.data:
            data = self.coordinator.data
            attrs.update({
                "water_number": data.get("water_number", ""),
                "date": data.get("date", ""),
                "balance": data.get("balance", 0),
                "usage": data.get("usage", 0),
                "amount": data.get("amount", 0),
                "penalty": data.get("penalty", 0),
                "last_balance": data.get("last_balance", 0),
                "wechat_amount": data.get("wechat_amount", 0),
                "name": data.get("name", ""),
                "address": data.get("address", ""),
                "phone": data.get("phone", ""),
                "area": data.get("area", ""),
                "daylist": data.get("daylist", []),
                "monthlist": data.get("monthlist", []),
                "yearlist": data.get("yearlist", []),
                "estimated_days": data.get("estimated_days", 0),
                "数据源": "源通水务",
                "最后同步日期": data.get("date", ""),
                "数据状态": "实时" if self.coordinator.last_update_success else "缓存",
            })

            cd = datetime.now()
            attrs["计费标准"] = {
                "计费标准": "年阶梯",
                "第1档水量": TIER_LEVEL_1,
                "第2档水量": TIER_LEVEL_2,
                "第1档水价": TIER_PRICE_1,
                "第2档水价": TIER_PRICE_2,
                "第3档水价": TIER_PRICE_3,
                "阶梯起始日期": f"{cd.year}.01.01",
                "阶梯结束日期": f"{cd.year}.12.31",
            }
        else:
            attrs.update({
                "数据源": "源通水务",
                "最后同步日期": "暂无数据",
                "数据状态": "无缓存",
                "计费标准": {"计费标准": "年阶梯"},
            })

        return attrs

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
