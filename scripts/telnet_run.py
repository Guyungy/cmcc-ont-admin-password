#!/usr/bin/env python3
"""
中国移动光猫 telnet 通用命令执行器（只读排查用）

用法:
  python3 telnet_run.py <光猫IP> <user账号> <user密码> "<命令1>" ["<命令2>" ...]

例:
  python3 telnet_run.py 192.168.1.1 user '背面密码' 'ls -la /config/work'
  python3 telnet_run.py 192.168.1.1 user '背面密码' 'grep -a -i ppp /config/work/lastgood.xml | head -40'

依赖: 仅 Python 标准库 (socket/select/re/sys)
说明:
  - 自带 telnet IAC 协议协商，不依赖系统 telnet（macOS 已移除 telnet 命令）
  - 逐条执行并打印回显，命令间不共享 shell 状态（每条独立执行）
  - 若需要 cd 后执行，用 `cd /path && cmd` 这种写法，或直接用绝对路径
"""
import socket, select, time, re, sys

IAC, DONT, DO, WONT, WILL = 255, 254, 253, 252, 251
SB, SE = 250, 240


class Telnet:
    def __init__(self, host, timeout=10):
        self.s = socket.create_connection((host, 23), timeout=timeout)
        self.s.setblocking(False)
        self.buf = b""

    def pump(self, wait=2.0):
        """读取可用数据，处理 IAC 协商，返回清理后的文本"""
        out = b""
        end = time.time() + wait
        while time.time() < end:
            r, _, _ = select.select([self.s], [], [], 0.2)
            if not r:
                continue
            try:
                data = self.s.recv(4096)
            except BlockingIOError:
                continue
            if not data:
                break
            self.buf += data
            i = 0
            while i < len(self.buf):
                b = self.buf[i]
                if b == IAC and i + 2 < len(self.buf):
                    cmd, opt = self.buf[i + 1], self.buf[i + 2]
                    if cmd == SB:
                        j = self.buf.find(bytes([IAC, SE]), i)
                        if j == -1:
                            break
                        i = j + 2
                    elif cmd in (DO, WILL):
                        self.s.sendall(bytes([IAC, DONT if cmd == DO else WONT, opt]))
                        i += 3
                    else:
                        i += 3
                else:
                    out += bytes([b])
                    i += 1
            self.buf = self.buf[i:]
        return out.decode("utf-8", errors="replace")

    def wait_for(self, patterns, timeout=15):
        txt = ""
        end = time.time() + timeout
        while time.time() < end:
            txt += self.pump(1.0)
            for p in patterns:
                if re.search(p, txt, re.I):
                    return txt
        return txt

    def send(self, line):
        self.s.sendall(line.encode() + b"\r\n")
        time.sleep(0.3)

    def login(self, user, pwd):
        self.wait_for([r"login:"], 15)
        self.send(user)
        self.wait_for([r"[Pp]assword:"], 15)
        self.send(pwd)
        txt = self.wait_for([r"[#$>]\s*$", r"~ #", r"# "], 15)
        low = txt.lower()
        if "incorrect" in low or "failed" in low or "denied" in low:
            raise SystemExit("!! 登录失败：账号或密码错误")
        return txt

    def run(self, command, timeout=15):
        self.send(command)
        # 等回显稳定：以提示符出现为准，再补一次静默读取
        txt = self.wait_for([r"[$#]\s*$"], timeout)
        txt += self.pump(1.0)
        return txt

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    host, user, pwd = sys.argv[1], sys.argv[2], sys.argv[3]
    commands = sys.argv[4:]

    t = Telnet(host)
    t.login(user, pwd)
    for c in commands:
        print(f"\n$ {c}")
        print("-" * 60)
        print(t.run(c).strip())
    t.close()


if __name__ == "__main__":
    main()
