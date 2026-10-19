# Desktop Operator

一个常驻的本地桌面/浏览器操作层，用来替代“每个动作新起一个 CLI、整页快照、30 秒超时”的慢流程。

它在同一个进程里持有 Playwright、Windows UI Automation、截图和中文 OCR。浏览器查询通常 10-30ms，原生窗口枚举 40-80ms，截图约 200ms。

[English README](README.md)

## 安装

```powershell
git clone https://github.com/gz2008/desktop-operator.git
cd desktop-operator
.\setup.ps1
.\op.ps1 system.info
```

要求：Windows 10/11、PowerShell 5.1+、Python 3.11-3.13、Microsoft Edge。

## 常用命令

```powershell
.\op.ps1 browser.goto "url=https://example.com" "headed=true"
.\op.ps1 browser.query "selector=button" "limit=10"
.\op.ps1 browser.find_text "text=登录"
.\op.ps1 browser.click "selectors=[\".login-btn\",\"text=登录\"]"
.\op.ps1 browser.fill "selector=input[name=user]" "value=admin"
.\op.ps1 win.list
.\op.ps1 win.tree "title=记事本" "depth=4" "limit=120"
.\op.ps1 win.click "title=记事本" "name=保存"
.\op.ps1 screen.capture
.\op.ps1 screen.find_text "query=确定"
.\op.ps1 screen.click_text "query=确定"
```

批量动作：

```powershell
.\op.ps1 call '{"cmd":"batch","actions":[{"cmd":"browser.fill","selector":"#user","value":"admin"},{"cmd":"browser.click","selector":"text=下一步"}]}'
```

## 设计

- `dop.py`：常驻 HTTP 服务，绑定 `127.0.0.1:8765`。
- `op.ps1`：命令行入口，第一次调用自动启动守护进程。
- `ocr.ps1`：Windows 自带 OCR，支持中文。
- `secret.ps1`：DPAPI 本地凭据，`secrets/` 已被 git 忽略。
- `profile/`、`shots/`、`cdp-test/`、日志和 `.venv/` 都不进仓库。

## 安全边界

- 只监听本机回环地址。
- 使用独立 Edge profile，不复制日常浏览器配置。
- `browser.close` 通过 CDP 连接时只断开，不关闭用户的浏览器进程。
- 这是本地自动化工具，不是远程控制或凭据提取工具。

## 实验文档

- [KooLabs 加速手册](docs/PLAYBOOK-huaweicloud-koolabs.md)
- [2026-10-19 华为云实验复盘](docs/POSTMORTEM-2026-10-19.md)

## License

MIT
