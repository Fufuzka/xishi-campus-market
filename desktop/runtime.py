"""在桌面进程内运行仅监听回环地址的本地服务。"""
import os
import socket
import threading
import time
from desktop.config import check_server

class LocalService:
    def __init__(self, home):
        self.home = home
        self.server = None
        self.thread = None
        self.socket = None
        self.url = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return self.url
        os.environ['MARKET_DATA_DIR'] = str(self.home / 'data')
        os.environ['COOKIE_SECURE'] = '0'
        from backend.seed import seed
        from backend.main import app
        import uvicorn
        seed()  # 数据为空时导入，已有用户时不会覆盖。
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', 0))
            sock.listen(128)
            self.socket = sock
            self.url = f'http://127.0.0.1:{sock.getsockname()[1]}'
            self.server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', log_config=None, access_log=False, loop='asyncio', http='h11', ws='none', timeout_graceful_shutdown=3))
            self.thread = threading.Thread(target=self.server.run, kwargs={'sockets': [sock]}, daemon=True, name='shiguang-local-api')
            self.thread.start()
            for _ in range(150):
                if self.server.started:
                    check_server(self.url)
                    return self.url
                if not self.thread.is_alive():
                    break
                time.sleep(.1)
            raise RuntimeError('本地服务未能启动，请在连接设置中查看数据目录与日志')
        except Exception:
            self.stop()
            sock.close()
            raise

    def stop(self):
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=6)
        if self.thread and self.thread.is_alive():
            raise RuntimeError('本地服务仍在退出，请关闭软件后重新打开')
        if self.socket:
            self.socket.close()
        self.server = self.thread = self.socket = None
        self.url = None
