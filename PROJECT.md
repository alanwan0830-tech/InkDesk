# InkDesk「墨台」当前状态与交接

最后更新：2026-11-08 22:36（Asia/Shanghai）。项目根目录：`/Users/mi/Desktop/Paper`。

## 当前设备与架构

reTerminal E1001，ESP32-S3、32 MiB Flash、800×480单色屏。**已刷入本项目自研固件0.3**，原厂SenseCraft 1.2.2完整备份保留。

Mac Python采集行情、海淀天气、Codex项目事件及周额度 → 本地认证第一屏接口 → 设备独立绘制时间并局部刷新。首次联网校时后，设备依靠本地时钟走时，RTC保存UTC供重启恢复。用户已确认0.2显示正常、时间在走、没有整屏闪烁，但翻页无效。已补回手动切页：仅第一屏自动更新，其他三页允许手动查看，不自动轮播。

## 手动翻页修复（0.3已安装）

- 根因：0.2将页码固定为0且未接入按钮，将“不轮播”误实现为不可手动切页。
- 0.3：GPIO5上一页、GPIO4下一页、GPIO3绿色键回首页；40ms去抖，独立采样保留刷新期间短按。手动切页整屏刷新一次；其他页停留时无分钟/网络/六小时维护刷新。
- 三张归档图打包在应用内，离线可看；猫咪天气固定快照标明ARCHIVE/NOT LIVE。原素材、云端归档及图片分区不变。
- 48项回归通过，编译通过，三个800×480页面预览已检查。已仅更新应用槽（1,139,152字节），应用及保护区域校验通过，原厂镜像及0.2应用保留。
- 22:30:42启动全刷完成2.35秒；22:31:01分钟局刷完成1.075秒，无显示错误日志。测试串口采集已结束；正常数据服务继续运行。0.3验收记录 `runtime/firmware-tests/navigation-acceptance.json`，用户已确认0.3实机测试通过（包括翻页修复）。

## 扩展自动测试（已完成）

- 全套47项通过；设备实测拒绝401、503、截断数据和坏CRC，保留缓存并继续本地走时。
- 19:31:08离线重启刷新完成；直到19:47:31才接受新数据。期间16次分钟局刷均限于时钟数字，约1.08秒，无额外整屏刷新或显示超时日志。RTC UTC标记、持久缓存长度与CRC已验证。
- 故障接口19:46:59自动退出并恢复正常服务；设备19:47:31重新取数，19:47:35完成四处变化区域局刷，随后分钟局刷继续。
- 修复旧云端入口仍可启用的问题：`device.transport=local`独立于接口可用性，关闭云端setup入口并禁止后台/CLI云部署。固件产物与已安装版本一致，本轮未重新刷写。
- 正常认证接口200、无认证401、包校验和预览均通过；9份素材/归档/凭证文件哈希不变。临时测试和串口采集均结束，串口已释放。
- 完整测试范围和未验证项见 `FIRMWARE-TESTS.md`；机器证据在 `runtime/firmware-tests/extended-acceptance.json`。

## 本轮授权、安装与审查结果

- 用户明确要求“进行代码审查并优化，全部完成后再刷入固件”，已授权本轮刷写，无需再次确认。
- 修复了局刷边界错误、BUSY无期限等待、显示失败误提交、旧帧未显式恢复、离线提示丢失、队列校时滞后、时间范围溢出等问题。详细记录：`firmware/REVIEW.md`。
- ESP32-S3交叉编译通过；最初36项测试通过，扩展回归后共47项，包含原21项及备份、协议/显示传输、安装成功/失败路径。800×480 PNG已检查。
- 仅写入app0（`0x90000`），0.2应用994,528字节。写前核对当前boot/分区/OTA选择；写后应用校验通过，boot/NVS/OTA和图片分区写前/写后MD5一致。
- 已发送重启，设备日志记录整屏刷新完成约2.35秒，随后按分钟在时钟数字范围局刷约1.08秒。**这是设备日志证据，不是用户目视确认。**
- 7分钟数据接口离线测试已完成：数据接口关闭期间连续分钟局刷；19:20–19:24多次取数失败，旧图保留。接口自动恢复后19:25:26设备重新取数，四个变化区域局刷约4.28秒完成，无额外整屏刷新日志。
- 用户已目视确认0.2显示正常、时间在走、没有整屏闪烁；另外反馈翻页无效，本轮0.3已补回手动切页。

## 当前开关与服务

- `local.paper.dashboard`登录服务继续运行，提供8766本机预览及8767设备接口；Mac需登录并运行才能更新行情等数据。
- `config.json`：`device.enabled=false`（停用原厂云端推送）、`device.transport=local`；`firmware_bridge.host=0.0.0.0`、端口8767。当前 `firmware_bridge.enabled=true`，离线测试已结束并恢复。
- 临时离线测试进程已结束，`runtime/firmware-tests/offline-result.json` 为 `restored=true`。8767认证响应已复核200，设备重新取数已在日志确认。
- 设备复用原有Wi-Fi配置，未清除配网；mDNS查找Mac，失败后使用配置地址。
- 接口token位于 `runtime/firmware-bridge-token` 和忽略提交的 `firmware/include/secrets.h`，不打印。生产二进制含token，保持本地受限权限。
- 原 `runtime/hmi.json` 保护配置保持：`extra_page_ids=[]`、`cat_screen_enabled=false`、`retain_uploaded_pages=true`、`publish_only_when_awake=true`。未调用云端删除或清理。
- 原厂 `--deploy-once` 当前不用于自研固件。回到原厂方案前需明确任务授权及相应恢复步骤。

## 验证边界与下一步

- 0.2写入、日志和用户目视确认均已完成；0.3已安装，用户已确认0.3实机测试通过。
- 接口离线与恢复验证已完成；离线重启RTC/缓存恢复也已验证。后续为电池和长时运行验证。
- 接口离线测试不等同断开Wi-Fi或拔USB。电池供电、真实断电、长时间断网及六小时残影仍未实测。
- 首次、每六小时维护，以及显示失败后重新同步可能整屏刷新；不能承诺绝对零闪烁。
- 显示BUSY超时20秒，失败不提交已显示帧，60秒后重试。未实现深度休眠优化，不声称续航已达标。
- 缓存最多每小时持久化一次，重启后可能显示较旧数据；无可信时间显示缺失，数据过期/来源失败明确标记。

## 备份、产物与重要位置

| 内容 | 位置 |
|---|---|
| 原厂完整32 MiB备份 | `runtime/firmware-backups/20261108-183714/stock-full.bin`，同目录 `manifest.json` |
| 备份SHA-256 | `c7892ecdca7bb25c49ecef2e31b9c9c151904abb080f25e34dd264dcf4f4f385` |
| 本轮写前boot/NVS与校验结果 | `runtime/firmware-installs/`；刷写日志 `runtime/firmware-install.log` |
| 当前0.3产物 | `runtime/firmware-build/paper-e1001-0.3.bin`、`release.json` |
| 固件、构建、安装与验收 | `firmware/README.md`、`firmware/REVIEW.md`、`FIRMWARE.md` |
| 设备串口日志 | `runtime/firmware-monitor/20261108-191535.log`、`20261108-193106.log`及脱敏summary；采集进程已主动结束，串口已释放 |
| 实机串口 | `/dev/cu.usbserial-210`、115200；同一时间只开一个进程 |
| 本地预览 | `http://127.0.0.1:8766`；`runtime/status.json`、`runtime/service.log` |
| 固件模拟PNG | `runtime/firmware-preview/dashboard.png`及一分钟差分 |
| 四屏备份与云端清单 | `runtime/four-screen-backup.json`、`runtime/hmi.json` |
| 用户原稿 | `assets/`；书法 `lanting-calligraphy-dark.png` |
| 登录启动与钩子 | `~/Library/LaunchAgents/local.paper.dashboard.plist`、`.codex/hooks.json`、`paper/hook.py` |

备份已逐块/整份设备MD5及本地SHA-256复核；**未做完整写回恢复实验**。镜像包含配置和可能的凭证，不上传、不提交。设备未开启Secure Boot/Flash Encryption。高速串口曾损坏，正式备份和安装使用115200。

## 保留的原厂历史与归档

第一屏小米、美团、QQQ、TSLA、PDD、BTC、海淀天气、Codex任务及周额度。第二屏Ducati、第三屏《兰亭集序》、第四屏猫咪天气作为本地固定归档快照手动查看，不自动更新；云端归档不改动、不删除。

SenseCraft设备ID `20240911`，原活动列表 `20245133`；归档第二/三屏 `20721844` / `20722156`，猫咪页 `20724713`。不要清空部署清单或拿unused列表替换活动列表。API密钥只在 `.env`。

原厂电池模式品牌页问题并未最终证实根因；此前源码推断为唤醒旧图片ID与云端新清单竞态。自研固件已改用本地接口，不等于修复了原厂固件。原始依据保留在 `runtime/diagnostics/findings-20261108.md` 和 `FUNCTIONAL-STATUS.md`，不要把旧推断当作已确认事实。

## InkDesk 项目与 Git

用户将项目命名为 **InkDesk「墨台」**，标语“把关心的事，放在眼前。”，定位为可自定义的桌面墨水屏看板。GitHub仓库使用 `alanwan0830-tech/InkDesk`，私有。现有目录、Python包和登录服务名保持兼容；代码、测试、文档及素材纳入Git，凭证、运行日志、依赖目录、备份与固件二进制不提交。
