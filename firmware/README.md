# E1001 配对、构建和设备检查

候选版适用目标是 reTerminal E1001（ESP32-S3、32 MiB、800×480 黑白屏）。E1002、其他分区和启用安全启动或闪存加密的设备不在支持范围内。首页后是只读车辆页，第 3 至第 5 页使用程序生成的离线演示图，左键上一页、中间键下一页、绿键回首页。

## 1. 配对

先按仓库 README 生成首页。设备与 Mac 接入同一可信局域网。编辑本地 `config.json`，保持 `device.transport=local`、`device.enabled=false`，启用 `firmware_bridge.enabled`。Mac 上生成仅自己可访问的配对令牌：

```sh
mkdir -p runtime
(umask 077; set -C; openssl rand -hex 32 > runtime/firmware-bridge-token)
cp -n firmware/include/secrets.example.h firmware/include/secrets.h
```

在本机编辑 `firmware/include/secrets.h`，填入 Wi-Fi、Mac 的局域网地址和同一个令牌。mDNS 名称填 Mac 的 LocalHostName，省略 `.local`。可用 `scutil --get LocalHostName` 查看。令牌不要粘贴到聊天或公开日志。启动 `./run.sh` 后，从同网另一台设备访问 Mac 的 8767 端口和 `/frame`，未认证预期返回 401。接口为 HTTP，仅供可信局域网使用。

## 2. 构建

```sh
.venv/bin/python firmware/tools/build_archives.py
uv tool run --python 3.12 --with pip --from platformio==6.1.18 pio run -d firmware
```

应用产物在 `firmware/.pio/build/paper_e1001/firmware.bin`。产物含 Wi-Fi 和配对凭证，请留在本机。PlatformIO 通用上传与擦除被禁用。

## 3. 备份与只读预检

刷写流程尚未在第二台 E1001 验证。普通用户先做到预检，确认失败请不要覆盖原厂分区。明确选择自己的串口，可用 `ls /dev/cu.*` 比较 USB 插入前后的变化。备份和预检会暂时进入下载模式并重启设备。备份保持本地且可能耗时，里面含设备配置。

```sh
PORT=/dev/cu.YOUR_DEVICE
uv run --python 3.12 --with esptool==5.1.0 integrations/backup-firmware.py --port "$PORT"
BACKUP=runtime/firmware-backups/YOUR_BACKUP_DIRECTORY
IMAGE=firmware/.pio/build/paper_e1001/firmware.bin
APP_SHA256=$(shasum -a 256 "$IMAGE" | cut -d ' ' -f 1)
uv run --python 3.12 --with esptool==5.1.0 integrations/flash-reviewed-firmware.py \
  --port "$PORT" --backup "$BACKUP" --image "$IMAGE" --sha256 "$APP_SHA256"
```

工具要求当前设备整片闪存与自己的验证备份相同，并限制分区表和 OTA 记录。正常重启后设备可能更新配置；遇到不一致应重新核对备份，不能跳过检查。工具预检默认不写。对受支持的原厂布局，在已有可靠恢复手段且理解风险时，同一命令添加 `--execute` 才写入 app0。写入成功后校验应用和 app0 外全部区域；写入异常时保留下载模式，检查日志并联系维护者评估恢复。完整原厂写回尚未实测，请勿使用通用命令整片覆盖。

## 4. 实机验收

```sh
.venv/bin/python integrations/monitor-firmware.py --port "$PORT" --seconds 330
```

设备日志依次应出现 `Wi-Fi connected`、`First-screen data accepted` 和 `Frame committed`。还需目视核对首页、翻页及归档页静止。断网时应显示缓存并继续走时。电池续航和长时残影尚未完成验收。
