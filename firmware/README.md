# Paper E1001 固件 0.3

0.3补回手动翻页；具体安装状态及实机证据以根目录 `PROJECT.md` 为准。0.2已获得用户目视确认：显示正常、时间在走、没有整屏闪烁。审查细节见 `REVIEW.md`。

## 行为

- 首次从 Mac 校时，之后设备按分钟本地走时；PCF8563 保存 UTC，用于重启恢复。无可信时间显示 `--:--`。
- 每五分钟读取第一屏底图。网络失败一分钟后重试；时钟不等网络。数据源失败显示 `OFFLINE`，底图超过十分钟未更新显示 `CACHED`。
- 比较七个互不重叠区域的像素，仅刷新变化范围。每个局刷窗口显式提供旧、新帧，正确处理边缘坐标；没有变化不刷新。
- 第一屏是唯一自动更新目标，无自动轮播。左白键（GPIO5）上一页，中间白键（GPIO4）下一页，绿色键（GPIO3）回首页。页面顺序为看板、Ducati、兰亭集序、猫咪天气归档快照；首尾可手动循环。
- 其他页静止显示，不接收时钟/数据/维护定时刷新；后台继续维护第一屏缓存和时钟，返回首页即显示最新已收到数据。三张图随应用打包，离线可翻阅；猫咪天气标明归档时间及NOT LIVE，不伪装为实时。
- 按钮40ms去抖，按住不连跳；独立任务采样，刷新期间最多缓存8次按键。
- 首次、手动换页、首页每六小时维护、显示错误后的重新同步可能整屏刷新。BUSY 等待最多20秒；失败不提交“已显示”状态，60秒后重试。
- 首次有效图及以后至多每小时写一次独立 `paper-v1` NVS 缓存。重启缓存可能比上次画面旧一小时；不格式化存储。
- Wi-Fi 优先使用私有构建配置；SSID 为空时复用设备原有配置，不擦除已保存的网络。Mac 地址初始使用构建配置，mDNS 解析成功时更新，解析失败时沿用当前地址。网络工作放在独立任务，取数后关闭 Wi-Fi。串口分别记录连接成功或超时，不输出凭证。
- 没有实现深度休眠，电池续航和长期残影仍需实测。

## 当前运行

现有 `local.paper.dashboard` 登录服务同时提供：

- `127.0.0.1:8766`：Mac 本地预览。
- `0.0.0.0:8767/frame`：经独立 token 认证的设备数据接口，仅用于可信局域网。

`config.json`：`device.enabled=false` 停止原厂云端推送；正常运行时 `firmware_bridge.enabled=true`。离线测试会暂时关闭后者，测试进程在结束时自动恢复。采集和原有云端归档保护保留。

联网接口只读取 `runtime/snapshot.json`，不提供云端页面修改或任意文件访问。首次/周期更新需要 Mac 在线；已校时后的本地走时不需要 Mac。

## 编译与验证

在项目根目录运行：

```sh
.venv/bin/python firmware/tools/build_archives.py
uv tool run --python 3.12 --with pip --from platformio==6.1.18 pio run -d firmware
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python firmware/tools/preview.py
```

依赖固定版本；输出 `firmware/.pio/build/paper_e1001/firmware.bin`。发布镜像和校验信息在 `runtime/firmware-build/`，当前发布记录为 `release.json`。生产二进制含本地接口 token，保持受限权限，不分享。

私有 `include/secrets.h` 已配置并忽略提交。SSID 为空时复用设备原有 Wi-Fi；若另行配置，使用 `secrets.example.h` 的字段。接口 token 保存在 `runtime/firmware-bridge-token`，不是 SenseCraft API 密钥。不要把凭证放进日志、命令行参数或文档。

预览按固件实际字体和点阵生成800×480 PNG；它不是实机屏幕照片。自动测试包含原有行为、备份、协议、实际面板传输代码和安装失败路径。

## 安装与回退

用户本轮已明确授权审查完成后刷入。安装工具 `integrations/flash-reviewed-firmware.py` 的 `--execute` 必须对应明确授权，不应从普通构建流程自动调用。

本轮安装：

1. 核对32 MiB原厂镜像SHA-256，检查设备型号、安全状态与32 MiB容量。
2. 读取当前boot/NVS/分区/OTA前缀并保存；确认启动配置及OTA选择仍匹配已审阅的app0。
3. 仅写 `0x90000` 应用槽。保留bootloader、分区表、NVS、OTA选择记录、归档图片分区。
4. 核对新应用，以及写前/写后的保护区域MD5，一致后才重启。写入未验证时留在下载模式，避免启动半写入固件。

原厂完整备份：`runtime/firmware-backups/20261108-183714/stock-full.bin`。本轮刷写前状态与结果：`runtime/firmware-installs/`。完整备份不能当成单一应用文件刷入；完整回退从 `0x0` 写入，会回滚配置和缓存。回退写入需要任务授权；当前没有进行写回恢复实验。

工程仍阻止 PlatformIO 通用上传和擦除，避免误写其他分区。

安装工具默认使用 115200 波特率；遇到串口传输损坏时可指定 `--baud 57600` 降速，原有写前检查和写后校验仍须全部通过。

## 实机验证边界

已安装不等同目视正常。分别记录：写入校验、设备刷新完成日志、用户目视确认。离线数据接口测试不等同拔掉电池或断开所有无线网络；0.2离线重启及缓存恢复已验证；0.3实机按钮已由用户确认；供电切换、电池续航和至少六小时残影仍需独立验证。不能承诺绝对零闪烁。

本地模式使用 `device.transport=local` 独立锁定，临时停用数据接口也不会开启旧云端部署；旧 `/setup` 写入返回409。完整实机自动测试及验证边界见根目录 `FIRMWARE-TESTS.md`。

归档打包命令仅在明确更新归档快照时运行，不随数据采集重建。生成的 `include/archived_pages.h` 忽略提交；`runtime/firmware-pages/` 留存800×480预览与来源校验值。按钮接线依据 [Seeed官方板载外设文档](https://wiki.seeedstudio.com/reterminal_e10xx_with_arduino_peripherals/)。
