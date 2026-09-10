#!/usr/bin/env python3
"""
中国移动光猫（CMCC ONT/ONU）telnet 超管密码提取脚本
用法:
  python3 telnet_get_admin.py <光猫IP> <user账号> <user密码>
  例: python3 telnet_get_admin.py 192.168.1.1 user 你的光猫背面密码

流程:
  1. telnet 登录 (处理 IAC 协商)
  2. cd /config/work
  3. ls -la 确认 lastgood.xml
  4. grep 提取 aucTeleAccountName/aucTeleAccountPassword (超管)
  5. 兜底: grep super/admin 常见字段

依赖: 仅 Python 标准库 (socket/select/re)
注意: 仅适用于已开启 telnet 的中国移动光猫 (如 UNG953H1-S 等 unionman 平台)
"""
import socket, select, time, re, sys

def run(host, user, pwd, timeout=10):
    IAC, DONT, DO, WONT, WILL = 255, 254, 253, 252, 251
    SB, SE = 250, 240

    s = socket.create_connection((host, 23), timeout=timeout)
    s.setblocking(False)
    buf = b""

    def pump(wait=2.0):
        """读取可用数据，处理 IAC 协商，返回清理后的文本"""
        nonlocal buf
        out = b""
        end = time.time() + wait
        while time.time() < end:
            r, _, _ = select.select([s], [], [], 0.2)
            if not r:
                continue
            try:
                data = s.recv(4096)
            except BlockingIOError:
                continue
            if not data:
                break
            buf += data
            i = 0
            while i < len(buf):
                b = buf[i]
                if b == IAC and i + 2 < len(buf):
                    cmd, opt = buf[i+1], buf[i+2]
                    if cmd == SB:
                        j = buf.find(bytes([IAC, SE]), i)
                        if j == -1:
                            break
                        i = j + 2
                    elif cmd in (DO, WILL):
                        s.sendall(bytes([IAC, DONT if cmd == DO else WONT, opt]))
                        i += 3
                    else:
                        i += 3
                else:
                    out += bytes([b])
                    i += 1
            buf = buf[i:]
        return out.decode("utf-8", errors="replace")

    def wait_for(patterns, timeout=15):
        txt = ""
        end = time.time() + timeout
        while time.time() < end:
            txt += pump(1.0)
            for p in patterns:
                if re.search(p, txt, re.I):
                    return txt
        return txt

    def send(line):
        s.sendall(line.encode() + b"\r\n")
        time.sleep(0.3)

    def cmd(c, wait_pats=None, timeout=8):
        send(c)
        return wait_for(wait_pats or [r"[#$]\s*$", r"BusyBox", r"~ #"], timeout)

    results = {}

    # 1. 登录
    txt = wait_for([r"login:"], 15)
    send(user)
    txt = wait_for([r"[Pp]assword:"], 15)
    send(pwd)
    txt = wait_for([r"[#$>]\s*$", r"~ #", r"# "], 15)
    if "incorrect" in txt.lower() or "failed" in txt.lower() or "denied" in txt.lower():
        print("!! 登录失败：账号或密码错误", file=sys.stderr)
        s.close()
        return None

    # 2. 进入配置目录并列出文件
    cmd("cd /config/work")
    ls = cmd("ls -la", timeout=8)
    results["ls"] = ls
    print(ls)

    # 3. 提取超管凭据
    g = cmd('grep -a -i -E "TeleAccount(Name|Password|User)" lastgood.xml', timeout=8)
    results["grep_tele"] = g
    print(g)

    # 4. 兜底：常见超管/默认账号字段
    g2 = cmd('grep -a -i -E "(super|admin|CMCCAdmin|aucDefaultAccount)" lastgood.xml | head -30', timeout=8)
    results["grep_admin"] = g2
    print(g2)

    s.close()

    # 解析结果
    creds = {}
    for line in (g + "\n" + g2).splitlines():
        m = re.search(r'Name="([^"]+)"\s+Value="([^"]*)"', line)
        if m:
            creds[m.group(1)] = m.group(2)
    if "aucTeleAccountName" in creds:
        results["admin"] = {
            "account": creds["aucTeleAccountName"],
            "password": creds.get("aucTeleAccountPassword", ""),
        }
    if "aucDefaultAccountName" in creds:
        results["default"] = {
            "account": creds["aucDefaultAccountName"],
            "password": creds.get("aucDefaultAccountPassword", ""),
        }
    return results

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python3 telnet_get_admin.py <光猫IP> <user账号> <user密码>")
        sys.exit(1)
    res = run(sys.argv[1], sys.argv[2], sys.argv[3])
    if res and "admin" in res:
        print("\n=== 超级管理员 ===")
        print("账号:", res["admin"]["account"])
        print("密码:", res["admin"]["password"])
    if res and "default" in res:
        print("\n=== 默认账号 ===")
        print("账号:", res["default"]["account"])
        print("密码:", res["default"]["password"])
