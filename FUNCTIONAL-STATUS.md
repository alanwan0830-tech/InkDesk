# 当前结论（2026-11-08）

自动推送已恢复，设备唤醒间隔为 5 分钟。已修复自动上屏接口：网页实际调用 POST /api/v2/user/device/deploy，参数 mode=refresh、playlist_id、mac_addresses；之前参考代码使用 down_link type=1，接口成功不足以让新页面实际显示。新部署接口已用现有 API Key 验证，并校验响应设备与播放列表。用户确认新时间已显示、看板正常，13 项测试通过。下文排查记录中的“暂停”已解除。

# Paper 功能版

本地预览：http://127.0.0.1:8766/
设备连接页：http://127.0.0.1:8766/setup

已验证：小米、美团、QQQ、TSLA、PDD 行情；Coinbase BTC/USD 24 小时变化；北京海淀天气；Codex 7 天额度与重置时间。价格可能延迟，底部显示报价日期。所有功能版数据来自接口；缺失数据不使用样稿数字替代。

刷新：行情 5 分钟，天气 15 分钟，额度 5 分钟，本地时钟每分钟。设备计划每 5 分钟提交画面，待批准/回复/本轮结束事件优先，最短间隔 60 秒。实际可见延迟还取决于设备唤醒频率。

## 当前接入边界

- SenseCraft 账号现有密钥已验证并保存在本机；首次真实推送已被 API 接受（page 20721715），自动推送已启用。没有重置账号密钥；实际屏幕以设备唤醒接收为准。浏览器登录状态不作为后台凭证。
- Codex 钩子位于 `.codex/hooks.json`，只针对 Paper 项目；9 项均已通过 hooks/list 确认 enabled=true、trustStatus=trusted，且无配置错误。2026-11-08 重启 Codex 后，已收到当前桌面对话的真实 PreToolUse 事件，本地预览确认“已收到真实任务事件”，执行中状态接通。待确认、结束状态仍需后续真实事件验证。
- 周额度通过独立只读 app-server 请求读取，任务状态绝不从这个独立进程推断。
- 钩子只保存状态、项目名、时间、会话/轮次标识，不保存提示词、命令内容、回复正文或凭证。不会批准、阻止或修改任务。
- 异步提问不会被误记为整个任务停止；“本轮结束”不等于整个项目完成。30 分钟没有事件的活跃状态标为待更新。
- 登录自动启动已安装并验证：launchctl 显示 local.paper.dashboard 为 running，启用 RunAtLoad 与 KeepAlive。服务独立于 Codex 和终端运行；行情 6/6、天气、额度及真实任务事件均正常。Mac 需登录、联网且保持唤醒；当前网络配置使用本机代理端口 7897。

## 设备推送

使用 Seeed 官方参考中公开的 API：上传 PNG、创建图片页、关联固定播放列表、发送到设备。API 没有公开更新图片页示例，因此使用滚动图片页，仅保留程序自己创建的最近三页，绝不删除已有 V0.5/V0.6 或其他设计。上传失败不清理旧画面；记录明确的本程序 page IDs，避免误操作。

密钥仅写本地 `.env`（0600），程序不回显、不写日志。只使用 api-key，不读取浏览器 Cookie。预览服务仅绑定 127.0.0.1；配置提交有来源和 CSRF 检查。

原始凭证、运行缓存与临时数据均已加入 .gitignore。

## 运行与测试

- `./run.sh`：启动本地服务。
- `./run.sh --once`：一次采集与出图，不推送。
- `./run.sh --deploy-once`：配置密钥后明确推送一次。
- `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run --python 3.12 pytest -q`

参考：https://github.com/Seeed-Solution/reterminal_skill ，https://learn.chatgpt.com/docs/hooks ，https://developers.openai.com/codex/app-server ，https://open-meteo.com/en/docs

## 实机验证补充

2026-11-08 用户确认设备已显示 LIVE 与当前时间。设备上报刷新间隔已从 1800 秒改为 300 秒。浏览器设备页确认绑定 Paper Live。后台改为更新设备原播放列表 20245133（原样稿页 20721596 保留），原新建播放列表 20245144 暂不使用。绑定备份见 runtime/playlist-binding-backup.json。API 接受 down_link 本身不能作为实机已刷新的证据。

设备唤醒间隔已按用户要求提交为 60 秒；云端 target_interval=60，提交时设备仍休眠、上报旧值 300，待下次唤醒接收。普通画面推送仍为 5 分钟，通知优先且最短间隔 60 秒。

## 品牌画面故障排查

设备持续停在品牌画面，网页重新应用后用户确认恢复。为避免反复覆盖，自动推送暂时关闭（数据采集与登录后台仍运行）。刷新间隔已恢复 300 秒且设备回报确认。单次诊断页 20721820 使用官方 multipart 文件上传并跳过历史页清理，等待实机结果；尚不能把 API success 当作显示成功。

## 第二屏照片

已添加用户提供的 Ducati 照片（原图备份 assets/ducati-original.jpg，云端源页 20721844）。部署后的设备列表返回两页且 pending_deploy=false：sort=0 实时看板，sort=1 照片，分辨率 800×480，单色模式。runtime/hmi.json 的 extra_page_ids 保留固定照片；自动刷新只轮换第一屏，并保护附加页不被历史清理删除。14 项测试通过。设备左右键切页，物理显示效果待用户查看。

第三屏已添加猫咪照片（源页 20721902，原图 assets/cat-original.jpg），设备播放列表验证 total=3、pending_deploy=false，顺序为实时看板、Ducati、Cat。两张照片均由 extra_page_ids 保留，自动更新已恢复。

第三屏已替换为双猫照片（源页 20721921，原图 assets/two-cats-original.jpg）。部署列表验证三页顺序为看板、Ducati、Two Cats；旧猫照片源页仅移出播放列表，未删除。自动更新恢复。

第三屏已替换为公路人物照片（源页 20721983，原图 assets/road-portrait-original.jpg）。设备部署列表验证为看板、Ducati、Road，pending_deploy=false；自动更新恢复。

第三屏按用户确认替换为行书《兰亭集序》生成图（源页 20722115，项目文件 assets/lanting-calligraphy.png）。设备列表确认三页顺序为实时看板、Ducati、兰亭集序，pending_deploy=false。自动更新恢复。

第三屏更新为黑底白字《兰亭集序》（源页 20722156，assets/lanting-calligraphy-dark.png），列表三页顺序已核验，自动更新恢复。图像由内置 image_gen 编辑，提示要求仅反转为黑底白字、保留书法内容与布局。

## 2026-11-08 猫咪天气第四屏
新增实时猫咪天气页：北京海淀天气、温度、湿度、风速、时间日期。运行时与主看板一起渲染；部署顺序为主看板、Ducati、黑底兰亭集序、猫咪天气。`cat_screen_enabled` 保持第四屏随每次自动更新提交。服务已恢复 5 分钟更新。云端部署列表确认 total=4，pending_deploy=false；实机接收仍以设备唤醒后显示为准。15 项测试通过，包括连续更新时保留两张固定图和第四屏顺序。

## 2026-11-08 暂时仅展示第一屏
用户要求停止展示其他页，保留原稿。已备份四屏配置到 runtime/four-screen-backup.json；hmi.json 的 archived_screens/archived_page_ids 保留三屏配置及云端页面，清理逻辑保护归档页面。extra_page_ids 清空、cat_screen_enabled=false。云端已确认列表仅 Paper Live（total=1，pending_deploy=false）。继续每 300 秒自动更新；本地素材及猫咪天气渲染代码保留。16 项测试通过。

## 品牌页复发排查
设备在线、电量 94%、Wi-Fi RSSI -40；云端图片解码确认 800x480 单色正常。暂未确定品牌页根因。关闭部署后的历史图片删除（retain_uploaded_pages=true），排除设备延迟下载时图片被清理的可能性。新建单屏列表部署后当前列表查询未体现新页，故恢复原绑定列表，重新下发 page 20724761，查询确认单页且 source_page_id 匹配。暂时 device.enabled=false，等待用户按绿色键确认实机，确认后恢复 300 秒自动更新。原稿及归档页均保留。

用户已确认短按绿色键后恢复看板。已重新启用自动推送并重启登录服务，确认 running。仍为单屏、300 秒间隔，retain_uploaded_pages=true；品牌页根因尚未确定，未宣称彻底修复。

## 品牌页再次复发：暂停自动推送定位
旧图片清理保持关闭仍复发。设备在线、电量92%，last_seen比最近推送晚约10秒；不能由云端确认设备显示成功。诊断快照保存 runtime/brand-page-diagnostic.json。已暂停 Mac 自动推送（device.enabled=false），但设备自身300秒唤醒间隔未改。仅重新部署现有列表，不创建新页面；等待实机确认及USB串口连接后取日志，不自动恢复推送。

## 路径恢复后：电池唤醒规避
串口日志与官方源码对照发现：定时唤醒使用旧图片ID作为下载筛选；睡眠期间云端换图后可能先清旧图再因目标ID不匹配而无下载任务，最终显示品牌等待页。属于有源码支持的推断，尚无故障现场日志最终证实。实现publish_only_when_awake，在线且90秒内有上报才允许上传及替换列表；休眠延后每15秒重查。21测试通过，自动服务已恢复，保持单屏300秒。USB供电测试正常；电池供电验证待用户。详细记录 runtime/diagnostics/findings-20261108.md。
