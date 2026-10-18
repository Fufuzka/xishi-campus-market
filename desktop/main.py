"""Windows 桌面入口；远程商品页不暴露原生文件或配置接口。"""
import ctypes
import hashlib
import html
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import threading
import time
from pathlib import Path

from desktop.config import app_home, read_config, write_config, validate_config, check_server
from desktop.runtime import LocalService

ROOT = Path(__file__).resolve().parents[1]

class Controller:
    def __init__(self, home):
        self.home = home
        self.warning = ''
        try:
            self.config = read_config(home)
        except (ValueError, OSError):
            self.config = {'mode':'local', 'server_url':''}
            self.warning = '配置文件无效，已回到本地演示；保存设置后可修复。'
        self.local = LocalService(home)
        self.window = None
        self.settings_window = None
        self.lock = threading.Lock()

    def connect(self, config):
        return self.local.start() if config['mode']=='local' else self.remote(config['server_url'])

    @staticmethod
    def remote(url):
        check_server(url)
        return url

    def startup(self):
        try:
            with self.lock:
                url = self.connect(self.config)
                self.window.set_title('夕拾 · '+('本地演示版' if self.config['mode']=='local' else '联网使用版'))
                self.window.load_url(url+'/?desktop=1&mode='+self.config['mode'])
        except Exception as exc:
            logging.exception('Desktop startup failed')
            self.window.load_html(message_html('暂时无法打开集市', str(exc)+'。请从窗口顶部菜单打开“连接设置”，检查地址或切换回本地演示。'))

    def show_settings(self):
        import webview
        if self.settings_window:
            self.settings_window.show()
            self.settings_window.restore()
            return
        self.settings_window = webview.create_window('夕拾 · 连接设置', html=(ROOT/'desktop/settings.html').read_text(encoding='utf-8'),js_api=SettingsAPI(self),width=620,height=780,min_size=(560,700),background_color='#f5f7ef',text_select=True)
        self.settings_window.events.closed += self.settings_closed

    def settings_closed(self):
        self.settings_window = None

    def closed(self):
        if self.settings_window:
            self.settings_window.destroy()
        self.local.stop()

class SettingsAPI:
    def __init__(self, controller):
        self._controller = controller

    def get_settings(self):
        c=self._controller
        return {**c.config, 'data_home':str(c.home), 'warning':c.warning}

    def test_connection(self, url):
        try:
            info=check_server(url)
            return {'ok':True,'message':'连接成功，服务版本 '+info['version']+'。可以保存并切换。'}
        except ValueError as exc:
            return {'ok':False,'message':str(exc)}

    def apply_settings(self, value):
        c=self._controller
        if not c.lock.acquire(blocking=False):
            return {'ok':False,'message':'上一次连接仍在处理中，请稍候。'}
        try:
            config=validate_config(value)
            url=c.connect(config)
            write_config(c.home,config)
            c.config=config
            c.warning=''
            c.window.set_title('夕拾 · '+('本地演示版' if config['mode']=='local' else '联网使用版'))
            c.window.load_url(url+'/?desktop=1&mode='+config['mode'])
            if config['mode']=='online':
                c.local.stop()
            return {'ok':True,'message':'已切换为'+('本地演示。回到集市窗口即可使用。' if config['mode']=='local' else '联网使用。请使用服务器账号登录。')}
        except Exception as exc:
            logging.exception('Connection change failed')
            return {'ok':False,'message':str(exc)}
        finally:
            c.lock.release()

def message_html(title, text):
    return '<html lang="zh-CN"><meta charset="utf-8"><body style="background:#f5f7ef;font-family:Microsoft YaHei;padding:70px;color:#28533d"><h1>'+html.escape(title)+'</h1><p style="line-height:2">'+html.escape(text)+'</p></body></html>'

def self_test(home, output):
    """对真正打包的资源和本地 API 做启动及重启验证，不依赖开发环境。"""
    import urllib.request
    import http.cookiejar
    controller=Controller(home)
    try:
        url=controller.local.start()
        info=check_server(url)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def request(path, data=None):
            raw=json.dumps(data).encode() if data is not None else None
            with opener.open(urllib.request.Request(url+path,data=raw,headers={'Content-Type':'application/json'}),timeout=10) as r:
                return r.read()
        products=json.loads(request('/api/products'))
        assert products['total']>=8
        assert b'vue' in request('/vendor/vue.global.prod.js')[:80].lower()
        assert '<svg' in request('/assets/book.svg').decode()
        request('/api/auth/login',{'username':'demo','password':'Campus2026!'})
        created=json.loads(request('/api/products',{'title':'桌面包持久化验收','description':'仅用于软件打包测试的商品记录。','price':'20.29','category':'教材书籍','image_url':'/assets/book.svg','contact':'测试联系方式','location':'图书馆门口','condition':'轻微使用'}))
        request('/api/search/history',{'keyword':'桌面历史验收'})
        old_port=url.split(':')[-1]
        controller.local.stop()
        url=controller.local.start()
        assert json.loads(request('/api/products/'+str(created['id'])))['price']==20.29
        assert json.loads(request('/api/me'))['username']=='demo'
        assert json.loads(request('/api/search/history'))['items'][0]=='桌面历史验收'
        request('/api/auth/logout',{})
        request('/api/search/history')
        request('/api/search/history',{'keyword':'游客历史验收'})
        controller.local.stop()
        url=controller.local.start()
        assert json.loads(request('/api/search/history'))['items'][0]=='游客历史验收'
        write_config(home,{'mode':'local','server_url':''})
        assert read_config(home)['mode']=='local'
        result={'status':'PASS','packaged':bool(getattr(sys,'frozen',False)),'health':info,'seed_products':products['total'],'restart_persistence':True,'session_after_restart':True,'bundled_vue_assets':True,'account_search_history_after_restart':True,'guest_search_history_after_restart':True,'loopback_only':True,'initial_port':old_port,'runtime':sys.version}
    finally:
        controller.local.stop()
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    home=app_home()
    home.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(home/'desktop.log',maxBytes=2_000_000,backupCount=2,encoding='utf-8')
    logging.basicConfig(level=logging.INFO,handlers=[handler],format='%(asctime)s %(levelname)s %(message)s')
    if '--self-test' in sys.argv:
        self_test(home,sys.argv[sys.argv.index('--self-test')+1])
        return
    # 同一数据目录只允许一个桌面实例。
    mutex=None
    if sys.platform=='win32':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        mutex=kernel.CreateMutexW(None,False,'Local\\ShiguangMarket_'+hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:20])
        if ctypes.get_last_error()==183:
            ctypes.windll.user32.MessageBoxW(0,'夕拾已经在运行，请切换到已有窗口。','夕拾校园集市',0x40)
            return
    try:
        import webview
        from webview.menu import Menu, MenuAction
        controller=Controller(home)
        window=webview.create_window('夕拾 · 正在启动',html=message_html('夕拾校园集市','正在准备集市，请稍候…'),width=1280,height=900,min_size=(900,640),background_color='#f5f7ef',text_select=True,zoomable=True)
        controller.window=window
        # 商品页只提供打开设置窗口的入口；配置读写仅限独立设置窗口。
        window.expose(controller.show_settings)
        window.events.closed += controller.closed
        menu=[Menu('夕拾',[MenuAction('连接设置',controller.show_settings),MenuAction('退出',window.destroy)])]
        webview.start(controller.startup,gui='edgechromium',private_mode=False,storage_path=str(home/'webview'),menu=menu,debug=False)
    except Exception:
        logging.exception('Desktop window failed')
        if sys.platform=='win32':
            ctypes.windll.user32.MessageBoxW(0,'软件启动失败。请确认已安装 Microsoft Edge WebView2 Runtime。\n详细日志：'+str(home/'desktop.log'),'夕拾校园集市',0x10)
        raise
    finally:
        if mutex:
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            kernel.CloseHandle(mutex)

if __name__=='__main__':
    main()
