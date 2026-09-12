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
- Node.js 18+（仅「脚本开启 telnet」这一步需要，用内置模块，同样无需 npm install；不装 Node 可改用浏览器手动开启）
- 本机与光猫网络连通（同一局域网，光猫管理地址通常为 `192.168.1.1`）
- 光猫背面的 `user` 账号密码（标签上的 USER PASSWORD）
- Windows / macOS / Linux 均可（macOS 已无内置 telnet，本工具自带协议实现，不受影响）

## 使用方法

### 1. 确认与光猫连通

```bash
ping 192.168.1.1
```

### 2. 开启 telnet

先看是不是已经开着：

```bash
nc -z -w 3 192.168.1.1 23 && echo OPEN || echo CLOSED
```

**方式 A：脚本自动开启（推荐）**

一条命令完成「Web 登录 → 开启 telnet → 验证端口」，不需要浏览器：

```bash
node scripts/web_login_and_enable_telnet.js 192.168.1.1 user 你的光猫背面密码
```

脚本复刻了设备前端的密码加密方式（`aes_1.js` 里的 `encryted_pwd`：AES-256-CBC + Pkcs7，key 由密码字符 hex 补零到 64 位派生，iv 随机 16 字节，提交值为 `ivHex + 密文Hex`），
并按账号走对应登录接口（`user`/`useradmin` → `/boaform/web_login_exe.cgi`，`CMCCAdmin` 等超管 → `/aoaform/web_login_exe.cgi`）。

可选参数：

- `--check`：只登录，不改 telnet 配置（可用于验证账号密码）
- `--off`：登录并**关闭** telnet（用完收尾，见第 5 步）

**方式 B：浏览器手动开启**

浏览器打开 `http://192.168.1.1`，用 `user` 账号登录后台，然后访问：

```
http://192.168.1.1/webcmcc/telnet.html
```

该页面 onload 会自动调用开启接口，提示 `open telnet success!` 即成功（部分固件显示 `TelnetSet Success!`）。

> 若提示 `Incorrect account password!`，改为访问 `http://192.168.1.1/webcmcc/telnet_page.html`（需保持已登录状态）。
> 注意：这个页面是**开**接口，打开一次就开；没有对应的「关闭页」，关闭请用方式 A 的 `--off`。

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

### 4. 验证超管凭据（可选）

用超管账号登录一次，返回 `success_telecomadmin` 即说明凭据有效：

```bash
node scripts/web_login_and_enable_telnet.js 192.168.1.1 CMCCAdmin '提取到的超管密码' --check
```

### 5. 收尾：关闭 telnet

开启 telnet 只是为了读配置。提取完若不继续使用，建议恢复原状：

```bash
node scripts/web_login_and_enable_telnet.js 192.168.1.1 user 你的光猫背面密码 --off
```

要接着在 telnet 里操作（改桥接、看拨号等）就保持开启，心里有数即可。

## 找回宽带（PPPoE）拨号账号密码

同一份 `/config/work/lastgood.xml` 也保存了宽带拨号凭据。先按上面的步骤开启 telnet，再运行：

```bash
python3 scripts/telnet_run.py 192.168.1.1 user '光猫背面密码' \
  'grep -a -n -E "Name=\"(aucWanName|aucUsername|aucPassword)\"" /config/work/lastgood.xml' \
  'ps | grep -i ppp'
```

在 `WAN_CONNECTION_ATTR_TAB` 中找到 INTERNET 连接（通常 `aucWanName` 含 `INTERNET`、`ucServiceList=4`、接口名以 `pppoe-` 开头）：

- `aucUsername`：宽带拨号账号
- `aucPassword`：宽带拨号密码（部分固件明文保存）

`ps | grep -i ppp` 显示的是设备正在使用的 `pppd` 参数，若其中出现 `user ... password ...`，可用来交叉验证当前实际拨号凭据。

> 注意：配置里 TR-069/CWMP 段也有同名 `aucUsername` / `aucPassword`，那是运营商远程管理凭据，不是宽带拨号凭据。应以所在 `<Dir>` 和 INTERNET WAN 连接特征为准。

## Web 登录加密算法说明

`web_login_password` 不是 SHA-256 哈希，而是 AES-256-CBC 密文：

1. key：密码字符的 charCode 转 hex 后拼接，截断或补 `0` 到 64 个 hex 字符（32 字节）
2. IV：每次随机 16 字节
3. padding：PKCS#7
4. 提交值：`ivHex + ciphertextHex`

因此同一密码每次输出都不同，不能拿 SHA-256 或另一次加密结果直接比较。该算法仅用于 Web 登录传输；`lastgood.xml` 里的凭据字段是否明文由固件决定。

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
| Web 登录返回 `one_user_login` | 设备同时只允许一个登录用户，稍等片刻或让已登录方退出后重试 |
| Web 登录返回 `three_error_login` | 密码连错 3 次被锁，等 1 分钟再试 |
| Web 登录返回 `invalid_username` / `bad_password` / `invalid_password` | 账号或密码错误 |
| 登录脚本报「登录接口无有效响应」 | 确认光猫 IP；确认是 webcmcc 平台（`curl -sI http://192.168.1.1/` 看 `Server:` 头）；非 webcmcc 固件不适用本流程 |
| 响应里没有任何 Set-Cookie | **正常现象**。该平台会话按客户端 IP 维护，脚本不需要 cookie 也能继续调后续接口 |

## 作为 AI Agent Skill 使用

本仓库同时是一个 [WorkBuddy](https://www.workbuddy.cn) / Claude Code 风格的 Skill。将整个目录放入 WorkBuddy AI 的用户级技能目录 `~/.workbuddy-ai/skills/`（或项目级 `{项目}/.workbuddy-ai/skills/`）后，`SKILL.md` 中的元数据会让 Agent 在用户提出「获取光猫超管密码」「光猫改桥接」等需求时自动加载本流程。

## 免责声明

- 本工具**仅限用于你本人拥有或已获授权管理的光猫设备**。
- 未经授权访问他人网络设备属违法行为，使用者需自行承担全部法律责任。
- 使用超管权限修改拨号 / 桥接等配置可能导致断网、IPTV 失效或设备无法注册。**操作前请备份**：telnet 登录后执行 `base64 /config/work/lastgood.xml` 保存原始配置。
- 提取到的凭据属敏感信息，请勿公开分享。

## License

MIT
