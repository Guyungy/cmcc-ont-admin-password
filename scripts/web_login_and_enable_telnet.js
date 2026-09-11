#!/usr/bin/env node
/**
 * 中国移动光猫（CMCC webcmcc）Web 自动登录 + 开启/关闭 telnet
 *
 * 用法:
 *   node web_login_and_enable_telnet.js <光猫IP> <账号> <密码>             # 登录并开启 telnet
 *   node web_login_and_enable_telnet.js <光猫IP> <账号> <密码> --off       # 登录并关闭 telnet
 *   node web_login_and_enable_telnet.js <光猫IP> <账号> <密码> --check     # 只登录，不碰 telnet
 *
 * 例:
 *   node web_login_and_enable_telnet.js 192.168.1.1 user 'Z55HL@GD'
 *   node web_login_and_enable_telnet.js 192.168.1.1 CMCCAdmin 'PCdq%RZ3' --off
 *
 * 依赖: 仅 Node 内置模块 (crypto / net)。Node 18+ 自带全局 fetch。
 *
 * 原理（逆向自设备 /webcmcc/script/aes_1.js + index.html）:
 *   1) 密码加密 encryted_pwd(pwd)：
 *        key = 把 pwd 每个字符的 charCode 转 16 进制（不足 2 位补 0）拼起来，
 *              截断或补 '0' 到 64 个 hex 字符（= 32 字节 -> AES-256）
 *        iv  = 随机 16 字节（hex 32 字符）
 *        密文 = AES-256-CBC(Pkcs7, key, iv)
 *        提交值 = ivHex + 密文Hex
 *   2) 登录接口（注意账号不同路径不同）：
 *        user / useradmin  -> POST /boaform/web_login_exe.cgi
 *        CMCCAdmin 等超管  -> POST /aoaform/web_login_exe.cgi
 *      body: mode_name=<cgi路径>&nonedata=<随机数>&web_login_name=<账号>&web_login_password=<加密串>
 *      成功标志: data.result == "success_useradmin" | "success_telecomadmin"
 *   3) telnet 开关接口:
 *        POST /boaform/set_telnet_enabled_url.cgi
 *        body: mode_name=...&nonedata=<随机数>&telnet_port=23
 *              &telnet_lan_enabled=1|0&telnet_wan_enabled=0&default_flag=1
 *      （开启其实就是 GET 一次 /webcmcc/telnet.html，页面 onload 自动调用上面的接口）
 */
const crypto = require('crypto');
const net = require('net');

const [, , HOST_ARG, USER, PWD, ...flags] = process.argv;
if (!HOST_ARG || !USER || !PWD) {
  console.error('用法: node web_login_and_enable_telnet.js <光猫IP> <账号> <密码> [--off|--check]');
  process.exit(1);
}
const BASE = HOST_ARG.startsWith('http') ? HOST_ARG.replace(/\/$/, '') : `http://${HOST_ARG}`;
const OFF = flags.includes('--off');
const CHECK_ONLY = flags.includes('--check');

/** 复刻 aes_1.js 的 encryted_pwd() */
function encryted_pwd(pwd) {
  let key = '';
  for (const ch of pwd) {
    const h = ch.charCodeAt(0).toString(16);
    key += h.length < 2 ? '0' + h : h;
  }
  key = key.length > 64 ? key.slice(0, 64) : key.padEnd(64, '0');
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-cbc', Buffer.from(key, 'hex'), iv);
  const body = cipher.update(Buffer.from(pwd, 'utf8'), undefined, 'hex') + cipher.final('hex');
  return iv.toString('hex') + body;
}

const jar = new Map();
function saveCookies(res) {
  const raw = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  for (const c of raw) {
    const [pair] = c.split(';');
    const i = pair.indexOf('=');
    if (i > 0) jar.set(pair.slice(0, i).trim(), pair.slice(i + 1).trim());
  }
}
async function req(url, opts = {}) {
  const headers = Object.assign({ 'User-Agent': 'Mozilla/5.0' }, opts.headers || {});
  if (jar.size) headers['Cookie'] = [...jar].map(([k, v]) => `${k}=${v}`).join('; ');
  const res = await fetch(url, { ...opts, headers, redirect: 'manual' });
  saveCookies(res);
  return { status: res.status, text: await res.text(), headers: res.headers };
}
function form(fields) {
  return Object.entries(fields).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
}
function tcpOpen(host, port, timeout = 3000) {
  return new Promise((resolve) => {
    const s = net.connect({ host, port });
    const done = (ok) => { s.destroy(); resolve(ok); };
    s.setTimeout(timeout);
    s.once('connect', () => done(true));
    s.once('timeout', () => done(false));
    s.once('error', () => done(false));
  });
}

(async () => {
  // 1) 先访问首页，拿到 Token（部分固件要求带 Token 头）与初始 cookie
  const root = await req(BASE + '/');
  const token = root.headers.get('Token');
  console.log(`[1] GET /  -> ${root.status}${token ? `  Token: ${token}` : ''}`);

  // 2) 登录
  const enc = encryted_pwd(PWD);
  const cgiPath = (USER === 'user' || USER === 'useradmin')
    ? '/boaform/web_login_exe'
    : '/aoaform/web_login_exe';
  const candidates = [BASE + cgiPath + '.cgi', BASE + cgiPath, BASE + '/boaform/web_login_exe.cgi'];

  let result = null;
  for (const u of candidates) {
    const r = await req(u, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        ...(token ? { Token: token } : {}),
      },
      body: form({
        mode_name: cgiPath,
        nonedata: Math.random(),
        web_login_name: USER,
        web_login_password: enc,
      }),
    });
    const m = /"result"\s*:\s*"([^"]+)"/.exec(r.text);
    if (m) { result = m[1]; console.log(`[2] POST ${u.replace(BASE, '')} -> ${r.status}  result=${result}`); break; }
  }
  if (!result) { console.error('!! 登录接口无有效响应，请确认光猫 IP 与固件版本'); process.exit(2); }
  if (!/^success/.test(result)) {
    console.error(`!! 登录失败: ${result}（密码错误 / 账号错误 / 已被锁定）`);
    process.exit(3);
  }
  console.log(`[2] 登录成功（${result === 'success_telecomadmin' ? '超级管理员' : '普通用户'}）`);

  if (CHECK_ONLY) { console.log('[3] --check 模式，不修改 telnet 配置'); process.exit(0); }

  // 3) 开关 telnet
  const want = OFF ? '0' : '1';
  const ep = '/boaform/set_telnet_enabled_url';
  const r3 = await req(BASE + ep + '.cgi', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { Token: token } : {}),
    },
    body: form({
      mode_name: ep,
      nonedata: Math.random(),
      telnet_port: 23,
      telnet_lan_enabled: want,
      telnet_wan_enabled: '0',
      default_flag: '1',
    }),
  });
  const ok3 = /SUCCESS|success/.test(r3.text);
  console.log(`[3] ${OFF ? '关闭' : '开启'} telnet -> ${r3.status} ${ok3 ? 'OK' : r3.text.slice(0, 200)}`);

  // 4) 验证 23 端口状态
  const open = await tcpOpen(new URL(BASE).hostname, 23);
  console.log(`[4] 端口 23 当前状态: ${open ? 'OPEN' : 'CLOSED'}（期望 ${OFF ? 'CLOSED' : 'OPEN'}）`);
  process.exit(open === !OFF ? 0 : 4);
})().catch((e) => { console.error('ERROR:', e.message); process.exit(9); });
