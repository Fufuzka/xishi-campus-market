"""显式创建管理员：python -m backend.create_admin 用户名（密码交互输入）。"""
import getpass
import os
import sys
from backend.main import init_db, db, hash_password, Credentials


def create_admin(username, password):
    Credentials(username=username,password=password)
    init_db()
    with db() as c:
        if c.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
            raise ValueError('账号已存在，请使用新的管理员用户名；不会自动提权普通用户')
        c.execute("INSERT INTO users(username,nickname,password_hash,role,verification) VALUES(?,?,?,'admin','approved')",(username,'平台管理员',hash_password(password)))


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('用法：python -m backend.create_admin 管理员用户名')
    password=os.environ.get('MARKET_ADMIN_PASSWORD') or getpass.getpass('管理员密码（至少 8 位）：')
    create_admin(sys.argv[1],password)
    print('管理员已创建，请通过网页登录。不要在生产环境使用演示密码。')
