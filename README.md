# InkDesk · 墨台

最近折腾了一个桌面小摆件，给它起名叫 InkDesk「墨台」。

想法很简单：把平时总要点开看的几件事，放到一块小屏幕上。天气、关注的行情，还有 Codex 有没有在干活、这周额度还剩多少，抬头就能看一眼。

尤其是把 AI 的工作状态摆到桌上这件事，有点好玩。我在这边坐着，它在旁边显示进度，多少有种看着同事上班的感觉 😂

用的是 reTerminal E1001，一块 800×480 的黑白墨水屏。除了信息页，我还在自己的设备上放了一些老照片、《兰亭集序》和猫咪天气主题页。想看哪张就按一下，停在那里，不会自己切走。黑白屏和书法放在一起，还挺搭的。

有同款设备、喜欢折腾墨水屏的朋友可以一起玩。

**把关心的事，放在眼前。**

如果是你，会想在这块屏上放什么？

公开版附带三张可重新生成的离线演示页。你可以换成自己的素材。

## 先在 Mac 上预览

准备 macOS、[Homebrew](https://brew.sh/)、[uv](https://docs.astral.sh/uv/) 和 Cairo。系统有可用中文字体时显示效果最佳。Codex 是可选项，缺少数据时首页显示缺失或缓存状态。

在项目根目录运行：

```sh
brew install uv cairo
uv sync --locked --python 3.12
cp -n config.example.json config.json
./run.sh --once
./run.sh
```

打开 [本机预览](http://127.0.0.1:8766/) 。若 8766 已有服务，先退出先前运行的实例，或修改本地配置的端口。首页文件也可直接在 `runtime/dashboard.png` 查看。

## 配对与构建

见 [E1001 配对、构建和设备检查](firmware/README.md) 。Mac 与设备须在互通的可信局域网内，Mac 须保持唤醒。登录自启可在前台服务验证通过后启用：

```sh
.venv/bin/python integrations/install-service.py
```

Codex 周额度从本机客户端读取。要显示本项目的任务状态，先登录 Codex，再运行 `.venv/bin/python integrations/configure-hooks.py`，阅读并信任生成的本地钩子。钩子只处理任务状态事件，不读取会话正文。

## 数据来源

- 天气由 [Open-Meteo](https://open-meteo.com/) 提供。免费 API 服务限非商业用途，数据采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 。 [服务条款](https://open-meteo.com/en/terms)
- 行情来自 Yahoo Finance 和 Coinbase Exchange，可能延迟、受限或随接口变化。使用前请核对各提供商的条款。项目不提供行情数据再分发授权。

## 测试

```sh
DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix cairo)/lib" .venv/bin/python -m pytest -q
```

设备端支持范围、刷写状态、已知限制见 [固件说明](firmware/README.md) 。包含网络凭证的固件、配置、完整闪存备份及运行日志均应留在本机。

一般使用问题可通过仓库的 Issues 提交，注明设备型号、系统版本和出错步骤。敏感问题见 [安全问题反馈](SECURITY.md) 。第三方组件说明见 [THIRD-PARTY.md](THIRD-PARTY.md) 。
