"""桌面配置与服务地址校验，不依赖窗口或业务后端。"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import urllib.request

DEFAULT_CONFIG = {'mode': 'local', 'server_url': ''}

def app_home():
    override = os.environ.get('SHIGUANG_HOME')
    return Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ShiguangMarket'

def normalize_server_url(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError('请填写服务器地址，例如 https://market.example.edu')
    value = value.strip()
    if any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('服务器地址不能包含空格或反斜杠')
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValueError('服务器地址格式不正确')
    if not parts.hostname or parts.username or parts.password:
        raise ValueError('请使用不含用户名或密码的完整服务器地址')
    if parts.path not in ('', '/') or parts.query or parts.fragment:
        raise ValueError('只填写站点根地址，不要带页面路径、查询参数或 #')
    if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('联网服务器必须使用 HTTPS；只有本机调试允许 HTTP')
    if port == 0:
        raise ValueError('端口号不能为 0')
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), '', '', ''))

def validate_config(value):
    if not isinstance(value, dict) or value.get('mode') not in ('local', 'online'):
        raise ValueError('请选择本地演示或联网使用模式')
    server = value.get('server_url', '')
    if server or value['mode'] == 'online':
        server = normalize_server_url(server)
    return {'mode': value['mode'], 'server_url': server}

def read_config(home):
    path = home / 'config.json'
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    return validate_config(json.loads(path.read_text(encoding='utf-8')))

def write_config(home, config):
    config = validate_config(config)
    home.mkdir(parents=True, exist_ok=True)
    temp = home / 'config.json.tmp'
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, home / 'config.json')
    return config

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def check_server(url):
    """不携带用户凭据，校验目标确实提供本项目 API，拒绝重定向。"""
    url = normalize_server_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url + '/api/health', headers={'Accept': 'application/json'})
    try:
        with opener.open(request, timeout=6) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError('响应过大')
            result = json.loads(raw)
            if result.get('status') != 'ok' or not isinstance(result.get('version'), str):
                raise ValueError('响应不匹配')
            return result
    except Exception as exc:
        raise ValueError('无法连接校园集市服务，请检查地址、网络、证书及服务器 /api/health 接口') from exc
