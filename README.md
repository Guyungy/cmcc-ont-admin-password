# CMCC ONT Admin Password Extractor

提取**中国移动光猫**（智能家庭网关 / XG-PON ONU）超级管理员账号密码的自动化工具。

普通 `user` 账号无法修改拨号方式、桥接、端口映射、远程管理等关键配置，只有超级管理员（`CMCCAdmin`）才有权限。运营商通常不告知该密码，本工具通过读取光猫本地配置文件把它取回来——**适用于你自己的设备**。

## 支持设备

| 项目 | 说明 |
|---|---|
| 运营商 | 中国移动（CMCC） |
| 平台 | webcmcc 管理界面（unionman 等代工平台） |
| 已验证型号 | `UNG953H1-S`（中国移动智能家庭网关 类型十九 2.5GE，XG-PON ONU） |
| 其他可能适用 | 同平台华为 / 中兴 / 创维 / 烽火代工型号（只要 `/webcmcc/` 路径与 `lastgood.xml` 结构一致） |

## 原理

光猫的完整配置（含超管凭据）以明文 XML 保存在 `/config/work/lastgood.xml`，只是 Web 界面不提供访问入口。流程：

```
Web 登录 user → 开启 telnet → telnet 登录 → 读取 lastgood.xml → 提取超管凭据
```

超管凭据所在字段：

```xml
<Value Name="aucTeleAccountName"     Value="CMCCAdmin"/>   <!-- 超管账号 -->
<Value Name="aucTeleAccountPassword" Value="********"/>    <!-- 超管密码 -->
<Value Name="aucDefaultAccountName"  Value="useradmin"/>   <!-- 默认账号 -->
```

## 环境要求

- Python 3.8+（**仅标准库**，无需 pip 安装任何依赖）
- 本机与光猫网络连通（同一局域网，光猫管理地址通常为 `192.168.1.1`）
- 光猫背面的 `user` 账号密码（标签上的 USER PASSWORD）
- Windows / macOS / Linux 均可（macOS 已无内置 telnet，本工具自带协议实现，不受影响）

## 使用方法

### 1. 确认与光猫连通

```bash
ping 192.168.1.1
```

### 2. 开启 telnet

浏览器打开 `http://192.168.1.1`，用 `user` 账号登录后台，然后访问：

```
http://192.168.1.1/webcmcc/telnet.html
```

页面显示 `TelnetSet Success!` 或 `TelnetSet 开启` 即成功。

> 若提示 `Incorrect account password!`，改为访问 `http://192.168.1.1/webcmcc/telnet_page.html`（需保持已登录状态）。
> 部分固件 telnet 默认已开启，可先验证：`nc -z -w 3 192.168.1.1 23`

### 3. 一键提取

```bash
python3 scripts/telnet_get_admin.py 192.168.1.1 user 你的光猫背面密码
```

输出：

```
=== 超级管理员 ===
账号: CMCCAdmin
密码: ********

=== 默认账号 ===
账号: useradmin
密码: useradmin
```

拿到后用超管账号登录 `http://192.168.1.1` 即可。

### 手动方式（不用脚本）

telnet 登录后依次执行：

```bash
cd /config/work
ls -la
grep -a -i -E "TeleAccount(Name|Password|User)" lastgood.xml
```

## 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| 端口 23 不通 | telnet 未开启，回到第 2 步；部分固件需先登录 Web 再访问 `telnet_page.html` |
| `incorrect password` / 登录失败 | 背面密码有误；或运营商已改密码，需重置光猫恢复出厂 |
| grep 无输出 | 配置被加密或压缩，执行 `base64 lastgood.xml` 导出后本地解码 |
| 找不到 `aucTeleAccount` 字段 | 不同固件字段名有差异，用 `grep -a -i -E "(super\|admin)" lastgood.xml` 兜底，或 `vi lastgood.xml` 后输入 `/TeleAccountName` 搜索 |
| macOS 报 `command not found: telnet` / `timeout` | 系统已移除这些命令，直接用本仓库脚本（自带 Python 协议实现） |

## 作为 AI Agent Skill 使用

本仓库同时是一个 [WorkBuddy](https://www.workbuddy.cn) / Claude Code 风格的 Skill。将整个目录放入 `~/.workbuddy/skills/` 后，`SKILL.md` 中的元数据会让 Agent 在用户提出「获取光猫超管密码」「光猫改桥接」等需求时自动加载本流程。

## 免责声明

- 本工具**仅限用于你本人拥有或已获授权管理的光猫设备**。
- 未经授权访问他人网络设备属违法行为，使用者需自行承担全部法律责任。
- 使用超管权限修改拨号 / 桥接等配置可能导致断网、IPTV 失效或设备无法注册。**操作前请备份**：telnet 登录后执行 `base64 /config/work/lastgood.xml` 保存原始配置。
- 提取到的凭据属敏感信息，请勿公开分享。

## License

MIT
