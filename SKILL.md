---
name: cmcc-ont-admin-password
description: 提取中国移动光猫（CMCC 智能网关/XG-PON ONU，如 UNG953H1-S 等）超级管理员账号密码，以及宽带（PPPoE）拨号账号密码。触发场景：用户需要光猫超管权限、修改拨号/桥接/远程管理配置、找回被运营商隐藏的超管密码、光猫后台只有 user 权限时、**忘记宽带账号或宽带密码**时。适用设备：中国移动智能家庭网关（webcmcc 平台，unionman 等）。全流程脚本化：Web 登录（复刻设备 AES-256-CBC 密码加密）→ 开启 telnet → telnet 读取 /config/work/lastgood.xml 提取 aucTeleAccountName/aucTeleAccountPassword（超管）与 WAN_CONNECTION_ATTR_TAB 的 aucUsername/aucPassword（宽带）→ 用 ps 里 pppd 进程参数交叉验证 → 收尾关闭 telnet。
agent_created: true
---

# 中国移动光猫超管密码提取

## 概述

中国移动光猫（如 UNG953H1-S、华为/中兴/创维代工等）普通 user 账号无法修改拨号、桥接等关键配置，需要超级管理员（CMCCAdmin）权限。本 skill 通过开启 telnet → 登录 → 读取配置文件 lastgood.xml 的方式提取超管账号密码。

**前提**：需先拿到光猫背面的普通 user 账号密码（标签上的 USER PASSWORD）。

**全程可自动化**，不需要人工开浏览器：Web 登录用 `scripts/web_login_and_enable_telnet.js`（内置 AES 加密复刻），telnet 提取用 `scripts/telnet_get_admin.py`。详见「资源」一节的完整链路。

> 不要凭猜测执行破坏性操作。只读 `lastgood.xml` 是安全的；`set_*` / `save` 类接口会改设备配置，动手前先备份。

## 工作流

### 步骤 1：确认设备与网络

1. 确认光猫型号（背面标签或 Web 登录页），常见型号：UNG953H1-S（中国移动智能家庭网关 类型十九 2.5GE）
2. 确认光猫默认管理地址（通常 `192.168.1.1`），可用 `ping 192.168.1.1` 验证连通

### 步骤 2：开启 telnet

部分光猫默认 telnet 关闭，需先用 user 登录 Web 后台开启。**先确认是否已开**：

```bash
nc -z -w 3 <光猫IP> 23 && echo OPEN || echo CLOSED
```

已 OPEN 可直接跳到步骤 3。

#### 方式 A：脚本自动开启（推荐，Agent 首选）

无需浏览器，一条命令完成「Web 登录 + 开启 telnet + 验证端口」：

```bash
node scripts/web_login_and_enable_telnet.js <光猫IP> <user账号> <user密码>
```

例：
```bash
node scripts/web_login_and_enable_telnet.js 192.168.1.1 user 你的光猫背面密码
```

脚本内部做的事（逆向自设备 `webcmcc` 前端）：
1. `GET /` 取 `Token` 响应头与初始 cookie
2. 用 `encryted_pwd()` 加密密码（算法见下方「密码加密算法」），POST 登录接口
   - user / useradmin → `/boaform/web_login_exe.cgi`
   - CMCCAdmin 等超管 → `/aoaform/web_login_exe.cgi`
3. POST `/boaform/set_telnet_enabled_url.cgi` 开启 telnet（`telnet_lan_enabled=1`）
4. 回连 23 端口确认

可选参数：`--check` 只登录不改 telnet；`--off` 登录并**关闭** telnet（收尾用）。

#### 方式 B：浏览器手动开启

1. 浏览器打开 `http://<光猫IP>`，用 user 账号登录
2. 访问 `http://<光猫IP>/webcmcc/telnet.html`，页面 onload 会自动调用开启接口，提示 `open telnet success!` 即成功
3. 若提示 `Incorrect account password!`，改访问 `http://<光猫IP>/webcmcc/telnet_page.html`（需已登录状态）

> 注意：`/webcmcc/telnet.html` 是**开**接口，GET 一次就会开。没有对应的「关闭页」，关闭需调 `set_telnet_enabled_url.cgi` 并传 `telnet_lan_enabled=0`（见方式 A 的 `--off`）。

#### 密码加密算法（encryted_pwd，来自设备 `/webcmcc/script/aes_1.js`）

```
key  = 密码每个字符 charCode 转 16 进制（不足 2 位补 0）拼接，
       截断或补 '0' 到 64 个 hex 字符（32 字节 → AES-256）
iv   = 随机 16 字节
密文 = AES-256-CBC + Pkcs7(key, iv)
提交 = ivHex + 密文Hex        // 注意是 iv 和密文拼在一起，不是 base64
```

登录 body：`mode_name=<cgi路径>&nonedata=<随机数>&web_login_name=<账号>&web_login_password=<加密串>`
成功标志：返回 JSON 中 `data.result` 为 `success_useradmin` 或 `success_telecomadmin`。

**⚠️ 三个必须记住的性质（否则会得出错误结论）：**

1. **这是加密，不是哈希。** 可逆——用同样的 key/iv 能解回明文。所以**不能拿 SHA-256 之类的摘要去比对**，
   两者根本不是一个范畴。`web_login_password` 里那串 hex 是密文，不是摘要。
2. **每次结果都不同，无法复现。** `iv` 是 `Math.random()` 生成的，同一个密码每次"加密"出来都不一样。
   因此**不存在"某密码的加密值"这个固定值**，任何"两次结果对不上"都是正常的，不代表算法错了。
   （64 个 hex 字符 = 前 32 位 IV + 后 32 位密文；密码 ≤16 字节时密文恰好一个 AES 块。）
3. **key 由密码自身派生**（不是固定密钥）：`key = hex(每个字符 charCode) 补 '0' 到 64 个 hex 字符`。
   例：`abc123` → `a`=61 `b`=62 `c`=63 `1`=31 `2`=32 `3`=33 → `616263313233` → 补零 →
   `6162633132330000000000000000000000000000000000000000000000000000`（32 字节 → AES-256）。
   这是固件设计上的弱点（密钥与明文同源），但复刻时必须照做。

**这个算法只用于 Web 登录的密码传输**，与 `lastgood.xml` 里存的凭据无关——
配置文件里的超管密码、宽带密码都是**明文**，没有走这套加密。别把两者混为一谈。

自检方法（改动脚本后跑一次，能证明实现正确）：

```bash
node -e "
const c=require('crypto');
const k=(p)=>{let s='';for(const h of p){const x=h.charCodeAt(0).toString(16);s+=x.length<2?'0'+x:x}return Buffer.from(s.length>64?s.slice(0,64):s.padEnd(64,'0'),'hex')};
const iv=c.randomBytes(16),e=c.createCipheriv('aes-256-cbc',k('abc123'),iv);
const ct=e.update('abc123','utf8','hex')+e.final('hex');
const d=c.createDecipheriv('aes-256-cbc',k('abc123'),iv);
console.log('往返 =', d.update(Buffer.from(ct,'hex'),undefined,'utf8')+d.final('utf8'));
"
# 期望输出: 往返 = abc123
```

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

### 步骤 5：验证超管凭据（推荐）

用步骤 2 的脚本以超管账号登录一次，返回 `success_telecomadmin` 即证明凭据有效：

```bash
node scripts/web_login_and_enable_telnet.js <光猫IP> CMCCAdmin '<提取到的超管密码>' --check
```

### 步骤 6：结果输出与提示

- 超管 Web 登录地址：`http://<光猫IP>`，账号 `CMCCAdmin`，密码为提取值
- 密码常含特殊字符（`#`、`%`、`@` 等），告知用户直接复制粘贴，避免手输
- 提醒用户：超管凭据敏感，勿公开泄露；修改配置（桥接/拨号）有风险，先备份原配置

### 步骤 7：收尾——按需关闭 telnet

开启 telnet 是为了提取凭据；提取完若不打算继续用，应恢复原状（原状态多为关闭）：

```bash
node scripts/web_login_and_enable_telnet.js <光猫IP> user '<user密码>' --off
```

若用户还要继续在 telnet 里操作（改桥接、看拨号等），则保持开启并明确告知用户「telnet 目前是开着的」。

**询问用户再决定**，不要默默改设备状态。

## 扩展：提取宽带（PPPoE）拨号账号密码

用户忘记宽带账号/密码时，同一份 `lastgood.xml` 里也能取回，无需重置光猫。

### 定位上网连接

`WAN_CONNECTION_ATTR_TAB` 有**多个实例**（每个 WAN 连接一个），靠 `aucWanName` 和 `ucServiceList` 区分：

| aucWanName 示例 | 用途 | 判据 |
|---|---|---|
| `1_TR069_R_VID_46` | 远程管理（TR-069） | `ucServiceList=1` |
| `2_INTERNET_R_VID_41` | **上网拨号** | `ucServiceList=4`，`ucConnectionType=1`，`ucNATEnabled=1`，`aucWanIfName=pppoe-wanX_XX` |
| `3_OTHER_B_VID_48` / `4_OTHER_B_VID_50` | IPTV / 其他 | `ucServiceList=8` |

要找的是 **`ucServiceList=4`（INTERNET）且 `aucWanIfName` 以 `pppoe-` 开头**的那条。

### 取账号密码

```bash
grep -a -n -E 'Name="(aucWanName|aucUsername|aucPassword)"' /config/work/lastgood.xml
```

- `aucUsername` → 宽带账号（形如 `手机号@139.gd`；`139.gd` 后缀 = 广东移动，各地后缀不同）
- `aucPassword` → 宽带密码（**明文存储**，非加密）

### 最可靠的验证：看正在跑的 pppd 进程

配置文件可能被改过却没生效；`ps` 里能看到设备**实际拨号**用的凭据，是运行时真值：

```bash
ps | grep -i ppp
```

输出形如：

```
pppd nodetach ipparam wan2_41 ifname pppoe-wan2_41 +ipv6 ... usepeerdns persist maxfail 1 \
     user 13800138000@139.gd password example-pass ip-up-script ... mru 1492 plugin rp-pppoe.so ...
```

`user` 后面是账号，`password` 后面是密码。**用这个值向用户交付**，配置文件的值作为佐证。

### 别搞混：TR-069 远程管理凭据

同一文件里另有一组 `aucUsername` / `aucPassword`（`cpeXXXX` 形式的随机串），那是运营商**远程管理（TR-069/CWMP）**账号，配合同段的 `aucAcsUrl` 判断：

```
<Value Name="aucAcsUrl"  Value="http://itms.example.invalid/itms-server/itms"/>
<Value Name="aucUsername" Value="cpeExample123"/>
<Value Name="aucPassword" Value="cpePasswordExample"/>
```

**判据是字段落在哪个 `<Dir>` 里**，不是字段名。同名 `aucUsername` 出现在 TR-069 段就是管理账号，出现在 `WAN_CONNECTION_ATTR_TAB` 且该实例是 INTERNET 才是宽带账号。

## 排查技巧（telnet 侧）

- **通用命令执行器**：`python3 scripts/telnet_run.py <光猫IP> <账号> <密码> "<命令>" ["<命令2>" ...]`
  可跑任意只读命令，不用为每个需求改脚本。这是排查阶段的默认工具。
- **BusyBox 陷阱**：部分固件的 shell 不允许写 `/dev/null`，`cmd 2>/dev/null` 会报
  `-ash: can't create /dev/null: Permission denied`。**直接省掉重定向**即可。
- **定位字段所在配置段**：BusyBox grep 支持 `-n/-B/-A/-C`：
  `grep -a -n -B 12 -A 12 'Name="aucUsername"' /config/work/lastgood.xml`
- **导出整张配置表**：`sed -n '/<Dir Name="表名"/,/<\/Dir>/p' lastgood.xml`
  注意这**只打印第一个匹配块**；表有多个实例时用行号取，例如 `sed -n '5205,5245p'`。
- **先列全表名**：`grep -a -o -E 'Dir Name="[^"]*"' lastgood.xml | sort -u`，比盲猜字段名快。
- `/config` 下还有 `workb/`（上一版配置备份），改配置前可对比。

## 注意事项 / 故障排查

| 问题 | 处理 |
|---|---|
| telnet 端口 23 不通 | 需先完成步骤 2 的 Web 开启 telnet；部分固件需登录 Web 后访问 telnet_page.html |
| 登录提示 `incorrect password` | 背面密码输错；或运营商改过密码，需重置光猫恢复初始密码 |
| `lastgood.xml` 为加密/压缩内容 | grep 无结果时，执行 `base64 lastgood.xml` 导出 base64 串，再用解密工具（如 RouterPassView / 对应型号解密脚本）处理 |
| 配置文件里无 aucTeleAccount 字段 | 部分固件字段名不同，用 `grep -a -i -E "(super|admin)" lastgood.xml` 兜底搜索；或直接 `vi lastgood.xml` 后 `/TeleAccountName` 搜索 |
| 系统无 telnet/timeout 命令 | 用脚本（纯 Python 实现协商），不依赖系统 telnet |
| Web 登录返回 `one_user_login` | 设备同时只允许一个登录用户，稍等片刻或让已登录方退出后重试 |
| Web 登录返回 `three_error_login` | 密码连错 3 次被锁，等 1 分钟再试 |
| Web 登录返回 `invalid_username` / `bad_password` / `invalid_password` | 账号或密码错误（脚本会统一报「登录失败」） |
| 登录脚本报「登录接口无有效响应」 | 确认光猫 IP；确认是 webcmcc 平台（`curl -sI http://<IP>/` 看 `Server:` 头）；非 webcmcc 固件不适用本流程 |
| 响应里没有任何 Set-Cookie | **正常现象**。该平台会话按客户端 IP 维护，脚本不需要 cookie 也能继续调后续接口 |

## 安全边界

- 仅用于本人家庭/单位自有光猫管理，不得用于未授权设备
- 提取到的超管密码为敏感信息，输出时提醒用户妥善保管

## 资源

| 脚本 | 依赖 | 作用 |
|---|---|---|
| `scripts/web_login_and_enable_telnet.js` | Node 18+（内置模块） | Web 登录（复刻 AES 加密）+ 开关 telnet + 端口验证。参数：`<光猫IP> <账号> <密码> [--off\|--check]` |
| `scripts/telnet_get_admin.py` | Python 3.8+（纯标准库） | telnet 登录 + 读取 lastgood.xml + 提取超管凭据。参数：`<光猫IP> <user账号> <user密码>` |
| `scripts/telnet_run.py` | Python 3.8+（纯标准库） | **通用** telnet 命令执行器，跑任意只读命令（查宽带密码、列配置表等）。参数：`<光猫IP> <账号> <密码> "<命令>" ...` |

> 取宽带（PPPoE）密码不需要专用脚本：用 `telnet_run.py` 跑
> `grep -a -n -E 'Name="(aucWanName|aucUsername|aucPassword)"' /config/work/lastgood.xml`
> 和 `ps | grep -i ppp` 即可，见上文「扩展」一节。

完整链路（Agent 可全自动）：

```bash
node scripts/web_login_and_enable_telnet.js 192.168.1.1 user '背面密码'
python3 scripts/telnet_get_admin.py 192.168.1.1 user '背面密码'
node scripts/web_login_and_enable_telnet.js 192.168.1.1 CMCCAdmin '提取到的超管密码' --check
node scripts/web_login_and_enable_telnet.js 192.168.1.1 user '背面密码' --off   # 收尾
```

> Node 用 WorkBuddy 自带版本即可：`/Users/a1/.workbuddy-ai/binaries/node/versions/*/bin/node`；
> Python 同理用 `/Users/a1/.workbuddy-ai/binaries/python/versions/*/bin/python3`，避免污染系统环境。
