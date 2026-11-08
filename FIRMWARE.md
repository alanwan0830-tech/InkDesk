# Paper 新固件

## 范围与验证边界

2026-11-08 用户要求：先备份原厂固件，再开发本地走时、局部刷新、固定第一屏的新固件。用户先允许备份临时重启，随后明确授权审查优化完成后刷入；0.2版现已完成应用写入和保护分区校验。当前状态见 PROJECT.md。

备份脚本：`integrations/backup-firmware.py`。运行前停止 `local.paper.dashboard` 并确认串口无其他使用者。脚本仅读取 Flash、向 RAM 加载读取助手和临时复位，不执行 Flash/eFuse 写入。完成或失败后尝试重启设备，后台服务需另行恢复。

## 备份方法

- ESP32-S3 实测 Flash 为 32 MiB，Secure Boot / Flash Encryption 均关闭。
- 当前串口在 921600、460800 波特率下试读失败；115200、230400 的 64 KiB 试读成功，230400 长读发生损坏，完整备份改用 115200；续读逐块重新验证已保存内容。
- 每个 64 KiB 块先由设备计算 MD5。全 `0xff` 块经校验确认后按原字节重建，其余块实际读取并比较设备 MD5。
- 全部块完成后，再比较完整 32 MiB 镜像与设备的 MD5；通过才将 `.partial` 改名为 `.bin`，写入带 SHA-256 的 `manifest.json`。
- 镜像及日志在 `runtime/firmware-backups/`，目录权限 700、文件权限 600。镜像含本地配置和可能的凭证，不上传、不提交、不公开。
- 镜像校验通过不等于已经验证恢复。恢复将改写设备，必须是明确授权的单独操作；完整镜像从地址 `0x0` 恢复，不能当作单一 app 分区文件。
- 备份不包含云端账号绑定状态或 eFuse。配置与页面归档继续保留在当前项目及 SenseCraft。

## 本轮结果

- 完整备份：`runtime/firmware-backups/20261108-183714/stock-full.bin`，32 MiB；逐块和整份设备 MD5 通过，本地 SHA-256 为 `c7892ecdca7bb25c49ecef2e31b9c9c151904abb080f25e34dd264dcf4f4f385`。
- 原厂运行重启指令已发送，Mac 登录服务恢复 running；未做刷写恢复测试，未目视确认设备画面。
- 0.2版审查修订后已编译并刷入；扩展回归后47项PC测试通过，最终800×480 PNG已检查。设备刷新日志已记录，离线重启与故障恢复测试见 FIRMWARE-TESTS.md；尚无用户目视确认。
- 实现、限制、配置、安装审阅方案和实机验收见 `firmware/README.md`。当前保护开关仍按 `PROJECT.md`。

## 开发约束

- 硬件 RTC 管理时间；首次校时以后断网也能每分钟更新。无可信时间显示缺失，不使用编译时间冒充当前时间。
- 按变更区域局部刷新；初始屏幕同步和必要的残影清理允许整屏刷新，具体频率须实机验证。
- 第一屏是唯一自动更新目标，不创建自动轮播；保留其他页面素材、归档配置与云端 ID。
- 网络请求不能阻塞本地时钟；下载不完整或校验失败保留上一张有效画面。
- USB 和电池模式分别验收；不能以编译成功或串口成功代替屏幕目视验收。

## 依据

- [Seeed 官方显示示例](https://wiki.seeedstudio.com/reterminal_e10xx_with_arduino/)：E1001 使用 UC8179、800×480、`BOARD_SCREEN_COMBO=520`。
- [Espressif esptool](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/esptool/basic-commands.html)：Flash 读取与校验。
- [Zephyr E1001 板文档](https://docs.zephyrproject.org/latest/boards/seeed/reterminal_e1001/doc/index.html)：完整原厂备份范围 32 MiB。
- Seeed_GFX 固定参考版本 `24c5094cbde79933e93565ee68119e214c48fb36`；官方 SenseCraft 源码参考 `8d97d89`。它们与设备原厂 1.2.2 二进制是否完全对应仍未确认。

## 0.3手动翻页修复

用户已目视确认0.2显示、走时和无整屏闪烁，但翻页无效。0.3补回按键手动四页切换，仍只自动更新第一屏，不轮播。48项测试与构建通过，已刷入并校验应用和保护区域；重启及分钟局刷日志正常。用户已确认0.3实机测试通过，详见 PROJECT.md。
