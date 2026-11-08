# InkDesk「墨台」项目协作规则

适用范围：本项目根目录及全部子目录。开始工作前先读取根目录 `PROJECT.md`，了解当前状态；不要把历史排查推测当成已确认事实。

## 项目与目录

InkDesk（原名 Paper）是 reTerminal E1001 的桌面墨水屏看板。Mac 上的 Python 服务采集行情、北京海淀天气和 Codex 状态，生成 800×480 单色图片，通过本地认证接口供设备获取。设备现已刷入本项目自研固件0.3；原厂SenseCraft方案和完整备份保留供回退。当前运行状态以 `PROJECT.md` 为准。

- `paper/`：运行代码。`server.py` 调度与预览；`render.py` 主屏；`cat_weather.py` 猫咪天气页；`data.py` 数据源；`codex.py` 用量与任务状态；`hmi.py` 上传部署；`hook.py` 事件接入；`common.py` 配置和文件工具。
- `firmware/`：ESP32-S3固件、本地时钟和局刷传输；`paper/firmware_bridge.py`：第一屏认证数据接口。构建/安装/验证见 `firmware/README.md`，不要用通用上传覆盖原厂分区。
- `config.json`：城市、时区、间隔、设备开关等非敏感配置。
- `assets/`：用户照片和书法原稿；`designs/`：历史设计与生成脚本。
- `integrations/`、`.codex/hooks.json`：登录启动和 Codex 钩子配置。
- `tests/`：测试；`runtime/`：生成图片、缓存、部署清单、状态及诊断日志。
- `.env`：本地凭证，不提交、不输出；`FUNCTIONAL-STATUS.md`：历史记录，最新状态以 `PROJECT.md` 和实测为准。

## 开发与验证

- 使用 Python 3.12、现有 `.venv`/uv 和 `pyproject.toml`，保持现有小型模块结构，避免无关重构。
- 界面针对真实 800×480 黑白屏验证。优先清晰、粗实的字形和高对比；改布局后检查最终 PNG，不只看 SVG 或浏览器预览。
- 无数据时显示缺失或缓存状态，不伪造实时行情、天气、额度或任务状态。
- Codex 任务状态来自钩子事件；不要读取对话正文。额度按周展示，保持项目范围过滤。
- 共享配置和清单优先使用 `atomic_json`。改推送逻辑时防止后台服务与手工部署并发写入。
- 运行与测试（在项目根目录）：
  ```sh
  ./run.sh                         # 前台服务；已运行登录服务时不要重复启动
  ./run.sh --once                  # 获取数据并生成预览，不直接部署；会改 runtime 文件
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q
  ```
- 本机预览：`http://127.0.0.1:8766`。`./run.sh --deploy-once` 是保留的原厂SenseCraft云端推送路径；当前自研固件不使用它。仅在明确使用原厂方案的任务中执行，并避免与后台推送重叠。
- 登录服务：`local.paper.dashboard`；配置改动需重启进程才生效：
  ```sh
  launchctl print gui/$(id -u)/local.paper.dashboard
  launchctl kickstart -k gui/$(id -u)/local.paper.dashboard
  ```
- 文档等低风险修改无需重复跑无关测试；推送、清理、调度修改必须验证失败路径与既有页面保留行为。

## 不能随意改变的事项

- 用户不需要自动轮播。第一屏自动更新；本轮用户反馈翻页无效，授权恢复按键手动查看其余三页。停留其他页时不能被定时刷新或网络更新打断；保留原稿与云端归档配置，不删除。
- 不删除用户素材、归档页或非本程序创建的云端页面。部署清单是保护依据，不要清空或手改历史 ID 来绕过检查。
- 不把云端 HTTP 成功或 `pending_deploy=false` 等同于实机显示成功。区分“已提交”“设备日志显示完成”“用户目视确认”。
- SenseCraft 已验证部署接口为 `POST /api/v2/user/device/deploy`，使用 `mode: refresh`、`playlist_id`、`mac_addresses`。不要退回历史上只返回成功却未正确上屏的 type=1 down_link 方案。
- 品牌页故障未最终解决。不要未经验证移除休眠推送保护或重新开启旧图片清理；先读 `PROJECT.md`。
- 不擅自刷固件、恢复出厂、重置 Wi-Fi/配对或 API 密钥。既有任务授权范围内的常规修改和上屏无需重复询问。
- 不移动项目或修改绝对路径而遗漏登录服务和钩子：曾因 `paper/hook.py` 路径失效导致所有工具调用被拦截。
- 串口读取不发送控制命令、不主动复位；同一端口只开一个采集进程。原始日志可能包含连接信息，保持本地受限权限，分享前脱敏。
- `.env`、`.venv/`、`runtime/` 应保持忽略；不要把凭证或完整敏感日志复制到文档。

## 交接约定

每完成一个阶段或改变运行状态，更新 `PROJECT.md` 的最后更新时间、当前开关、已验证结果和下一步。长期规则仅在项目约定改变时更新本文件；详细过程放历史记录，不让交接文件无限增长。
