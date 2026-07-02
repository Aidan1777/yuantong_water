# 源通水务 - Home Assistant 集成

## ✨ 功能特性

- ✅ 查询水表余额、累计用水量、欠费金额
- ✅ 获取用户信息（姓名、地址、电话）
- ✅ 月度/年度用水统计
- ✅ 智能预测余额可用天数
- ✅ 阶梯水价展示
- ✅ 数据持久化缓存（网络异常时自动使用缓存）
- ✅ 自动重试机制

## 📊 传感器实体

| 属性 | 说明 |
|---|---|
| `native_value` | 当前余额（元） |
| `water_number` | 水表号 |
| `balance` | 当前余额 |
| `usage` | 累计用水量（m³） |
| `amount` | 累计水费（元） |
| `penalty` | 滞纳金 |
| `last_balance` | 上期结余 |
| `wechat_amount` | 微信缴纳金额 |
| `name` | 用户姓名 |
| `address` | 用水地址 |
| `phone` | 联系电话 |
| `area` | 用水片区 |
| `estimated_days` | 预测可用天数 |
| `monthlist` | 月度用水明细 |
| `yearlist` | 年度用水统计 |

## 🚀 安装

### 方式一：HACS 安装

1. HACS → 集成 → 自定义仓库
2. 添加仓库地址：`https://github.com/Aidan1777/sxxhynet`
3. 搜索「源通水务」→ 下载安装
4. 重启 Home Assistant

### 方式二：手动安装

```bash
cd /path/to/homeassistant/config/custom_components
git clone https://github.com/Aidan1777/sxxhynet.git
```

## ⚙️ 配置

1. 进入 Home Assistant → 设置 → 设备与服务 → 添加集成
2. 搜索「源通水务」
3. 填写以下信息：

| 配置项 | 说明 |
|---|---|
| 水表号 | 你的水表编号 |
| Code | 微信小程序授权码（获取方式见下方） |

### 如何获取 Code

1. 使用微信打开源通水务小程序
2. 抓包工具拦截请求，找到包含 `code=` 参数的 URL
3. 将 `code` 值复制填入配置

## 📝 示例

```yaml
# configuration.yaml
sensor:
  - platform: sxxhynet
    water_number: "你的水表号"
    code: "你的code"
```

## 📈 自动化示例

```yaml
# 余额低于 50 元时发送通知
automation:
  - alias: "水表余额提醒"
    trigger:
      - platform: numeric_state
        entity_id: sensor.源通水务_你的水表号
        below: 50
    action:
      - service: notify.mobile_app_你的手机
        data:
          message: "水表余额不足 50 元，请及时充值"
```

## ⚠️ 注意事项

- Code 可能会过期，需要定期更新
- 数据每 6 小时自动更新一次
- 网络异常时自动使用缓存数据
- 建议配合自动化设置余额提醒

## 📄 许可证

MIT License