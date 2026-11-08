# InkDesk · 墨台

**把关心的事，放在眼前。**

一个可自定义的桌面墨水屏看板。把行情、天气、时间与工作状态放到桌面上，抬眼即见。

当前版本：**0.3**。基于 reTerminal E1001（ESP32-S3，800×480 黑白墨水屏），包含 Mac 数据服务和设备端自研固件；已通过 48 项自动测试及用户实机验收。

## 现在可以做什么

- **本地走时**：校时后依靠设备本地时钟运行，联网取数失败也能继续走时；RTC 支持重启恢复。
- **局部刷新**：第一屏按变化区域刷新，分钟更新只动时钟数字；手动换整页和必要维护使用整屏刷新。
- **手动翻页，无自动轮播**：第一屏实时看板、Ducati 照片、兰亭集序、猫咪天气归档快照。停在其他页时不会被后台刷新打断。
- **真实数据与明确状态**：行情、北京海淀天气、Codex 项目任务和周额度；数据缺失、离线或过期有明确标记。
- **按需定制**：修改城市、采集间隔、页面渲染代码和素材，组合自己的桌面看板。目前通过配置和代码定制，尚无可视化页面编辑器。

设备按键：左白键上一页，中间白键下一页，绿色键回首页。

## 工作方式

Mac 采集数据并生成第一屏底图 → 局域网认证接口 → 设备缓存底图、独立绘制时间、刷新变化区域。第二至第四页随固件保存，离线也能手动查看；猫咪天气页是带归档时间的固定快照。

项目原名 Paper。为保持现有服务和钩子正常，Python 包名 `paper`、登录服务名 `local.paper.dashboard` 及现有工作目录保持兼容，项目品牌统一为 InkDesk「墨台」。

## 本机运行

当前开发环境为 macOS、Python 3.12、uv，使用 Homebrew 的 Cairo 和系统中文字体。

```sh
uv sync --python 3.12
# 新克隆首次运行使用示例配置，按需调整城市和端口。
cp config.example.json config.json
./run.sh --once
./run.sh
```

本机预览：<http://127.0.0.1:8766/>。已有登录服务运行时，不要重复启动或覆盖其配置。

示例配置默认关闭设备接口和云端推送。启用设备接口前需在本地创建 `runtime/firmware-bridge-token`，至少32位随机ASCII字符，文件权限600；与 `firmware/include/secrets.h` 的 token 一致，再开启 `firmware_bridge.enabled`。敏感配置参考 `.env.example` 和 `firmware/include/secrets.example.h`，不要提交实际凭证。

Codex 状态通过项目钩子接入。当前 `.codex/hooks.json` 使用原开发机绝对路径；其他机器需先改为本机路径并在 Codex 中信任，不应直接复用原路径。不会读取对话正文。

## 固件和测试

```sh
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q
# 先生成本机看板/猫咪天气预览，再打包手动页。
.venv/bin/python firmware/tools/build_archives.py
uv tool run --python 3.12 --with pip --from platformio==6.1.18 pio run -d firmware
```

完整步骤见 [固件说明](firmware/README.md)。安装工具包含原设备分区和备份校验，不能直接用于另一台设备；新设备应先确认型号、分区和完整备份，再制定安装步骤。通用上传和擦除入口默认禁用。

## 项目结构

| 路径 | 内容 |
|---|---|
| `paper/` | 数据采集、渲染、本地预览、认证接口、Codex 状态及原厂云端适配 |
| `firmware/` | ESP32-S3 本地时钟、显示传输、按键与页面管理 |
| `integrations/` | 登录启动、钩子、完整备份、受保护刷写与被动串口观察 |
| `tests/` | Python 回归与原生 C++ 协议、刷新和翻页测试 |
| `assets/`、`designs/`、`archive/` | 页面素材、设计稿及历史记录 |
| `runtime/` | 本地缓存、日志、备份及构建产物，不进入 Git |

## 验收与边界

0.3 已通过用户实机测试；自动回归、异常数据、离线重启及恢复证据见 [测试报告](FIRMWARE-TESTS.md)。电池续航、真实断电、六小时以上残影和完整原厂写回尚未验证，当前未实现深度休眠优化。

- [当前状态与交接](PROJECT.md)
- [代码审查记录](firmware/REVIEW.md)
- [备份与固件记录](FIRMWARE.md)
- [历史功能记录](FUNCTIONAL-STATUS.md)

仓库不包含密钥、实际 Wi-Fi 配置、设备完整镜像、带认证信息的固件二进制或运行日志。原厂完整备份和已安装产物保留在开发机本地。
