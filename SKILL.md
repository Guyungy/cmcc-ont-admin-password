---
name: cmcc-ont-admin-password
description: 提取中国移动光猫（CMCC 智能网关/XG-PON ONU，如 UNG953H1-S 等）超级管理员账号密码。触发场景：用户需要光猫超管权限、修改拨号/桥接/远程管理配置、找回被运营商隐藏的超管密码、光猫后台只有 user 权限时。适用设备：中国移动智能家庭网关（webcmcc 平台，unionman 等）。通过 telnet 登录后读取 /config/work/lastgood.xml 提取 aucTeleAccountName/aucTeleAccountPassword。
agent_created: true
---

# 中国移动光猫超管密码提取

## 概述

中国移动光猫（如 UNG953H1-S、华为/中兴/创维代工等）普通 user 账号无法修改拨号、桥接等关键配置，需要超级管理员（CMCCAdmin）权限。本 skill 通过开启 telnet → 登录 → 读取配置文件 lastgood.xml 的方式提取超管账号密码。

**前提**：需先拿到光猫背面的普通 user 账号密码（标签上的 USER PASSWORD）。

## 工作流

### 步骤 1：确认设备与网络

1. 确认光猫型号（背面标签或 Web 登录页），常见型号：UNG953H1-S（中国移动智能家庭网关 类型十九 2.5GE）
2. 确认光猫默认管理地址（通常 `192.168.1.1`），可用 `ping 192.168.1.1` 验证连通

### 步骤 2：开启 telnet（Web 方式）

部分光猫默认 telnet 关闭，需先用 user 登录 Web 后台开启：

1. 浏览器打开 `http://192.168.1.1`，用 user 账号登录
2. 访问 `http://192.168.1.1/webcmcc/telnet.html`，页面显示 `TelnetSet Success!` 或 `TelnetSet 开启` 即成功
3. 若提示 `Incorrect account password!`，改访问 `http://192.168.1.1/webcmcc/telnet_page.html`（需已登录状态）

验证 telnet 端口开放：`nc -z -w 3 <光猫IP> 23`

### 步骤 3：telnet 登录并提取凭据（核心）

**推荐直接运行脚本**（已内置完整流程）：

```bash
python3 scripts/telnet_get_admin.py <光猫IP> <user账号> <user密码>
```

例：
```bash
python3 scripts/telnet_get_admin.py 192.168.1.1 user 你的光猫背面密码
```

脚本自动完成：
1. telnet 登录（处理 IAC 协议协商，纯 Python 标准库，无需系统 telnet）
2. `cd /config/work` → `ls -la` 确认 `lastgood.xml` 存在
3. `grep -a -i -E "TeleAccount(Name|Password|User)" lastgood.xml` 提取超管
4. 兜底 grep `super|admin|CMCCAdmin|aucDefaultAccount` 常见字段

### 步骤 4：无脚本手动流程（命令行交互）

若需手动操作：

1. macOS 无 telnet 命令，可用 Python socket 或 `nc`；Windows 用管理员 cmd 输入 `telnet 192.168.1.1`
2. 输入 user 账号和背面密码（密码输入时不回显，正常输入回车即可）
3. 进入 shell 后依次执行：
   ```
   cd /config/work
   ls -la
   grep -a -i -E "TeleAccount(Name|Password|User)" lastgood.xml
   ```
4. 输出示例：
   ```
   <Value Name="aucTeleAccountName" Value="CMCCAdmin"/>
   <Value Name="aucTeleAccountPassword" Value="<此处的密码即为超管密码>"/>
   ```
   - `aucTeleAccountName` / `aucTeleAccountPassword` = 超管账号密码（通常 CMCCAdmin）
   - `aucDefaultAccountName` / `aucDefaultAccountPassword` = 默认账号（常见 useradmin/useradmin）

### 步骤 5：结果输出与提示

- 超管 Web 登录地址：`http://192.168.1.1`，账号 `CMCCAdmin`，密码为提取值
- 密码常含特殊字符（`#`、`%`、`@` 等），告知用户直接复制粘贴，避免手输
- 提醒用户：超管凭据敏感，勿公开泄露；修改配置（桥接/拨号）有风险，先备份原配置（`/config/work` 目录下 `lastgood.xml` 可先下载备份）

## 注意事项 / 故障排查

| 问题 | 处理 |
|---|---|
| telnet 端口 23 不通 | 需先完成步骤 2 的 Web 开启 telnet；部分固件需登录 Web 后访问 telnet_page.html |
| 登录提示 `incorrect password` | 背面密码输错；或运营商改过密码，需重置光猫恢复初始密码 |
| `lastgood.xml` 为加密/压缩内容 | grep 无结果时，执行 `base64 lastgood.xml` 导出 base64 串，再用解密工具（如 RouterPassView / 对应型号解密脚本）处理 |
| 配置文件里无 aucTeleAccount 字段 | 部分固件字段名不同，用 `grep -a -i -E "(super|admin)" lastgood.xml` 兜底搜索；或直接 `vi lastgood.xml` 后 `/TeleAccountName` 搜索 |
| 系统无 telnet/timeout 命令 | 用脚本（纯 Python 实现协商），不依赖系统 telnet |

## 安全边界

- 仅用于本人家庭/单位自有光猫管理，不得用于未授权设备
- 提取到的超管密码为敏感信息，输出时提醒用户妥善保管

## 资源

- `scripts/telnet_get_admin.py`：一键自动化脚本（参数：光猫IP、user账号、user密码）
