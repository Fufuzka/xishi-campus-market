"""校园集市：同源 Vue 前端与 FastAPI 服务。"""
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from io import BytesIO
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import warnings

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('MARKET_DATA_DIR', ROOT / 'data'))
CATEGORIES = ['数码电子', '教材书籍', '生活日用', '运动户外', '服饰配件', '其他好物']
STATUS = Literal['on_sale', 'off_shelf', 'sold']

@contextmanager
def db():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / 'market.db', timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    (DATA / 'uploads').mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript((ROOT / 'backend/schema.sql').read_text(encoding='utf-8'))
        c.execute('PRAGMA journal_mode=WAL')

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()

def verify_password(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(':')[0]), stored)

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title='校园集市 API', version='0.1.0-beta.1', lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=422, content={'detail': '输入不符合要求，请检查字段、金额或分类'})

@app.middleware('http')
async def headers(request, call_next):
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            return JSONResponse(status_code=403, content={'detail': '不允许跨站提交'})
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

def current_user(request: Request):
    token = request.cookies.get('market_session', '')
    with db() as c:
        row = c.execute('SELECT u.id,u.username,u.nickname FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?', (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
    if row is None:
        raise HTTPException(401, '请先登录')
    return dict(row)

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r'^[A-Za-z0-9_]+$')
    password: str = Field(min_length=8, max_length=128)

class Registration(Credentials):
    nickname: str = Field(min_length=1, max_length=24)

    @field_validator('nickname')
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError('昵称不能为空')
        return v.strip()

def issue_session(c, response, uid):
    token = secrets.token_urlsafe(32)
    c.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
    c.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), uid, int(time.time()) + 86400 * 7))
    response.set_cookie('market_session', token, httponly=True, samesite='lax', secure=os.environ.get('COOKIE_SECURE') == '1', max_age=604800)

@app.post('/api/auth/register', status_code=201, tags=['用户'])
def register(payload: Registration, response: Response):
    with db() as c:
        try:
            uid = c.execute('INSERT INTO users(username,nickname,password_hash) VALUES(?,?,?)', (payload.username, payload.nickname, hash_password(payload.password))).lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(409, '用户名已存在')
        issue_session(c, response, uid)
    return {'id': uid, 'username': payload.username, 'nickname': payload.nickname}

@app.post('/api/auth/login', tags=['用户'])
def login(payload: Credentials, response: Response):
    with db() as c:
        row = c.execute('SELECT * FROM users WHERE username=?', (payload.username,)).fetchone()
        valid = verify_password(payload.password, row['password_hash'] if row else '0' * 32 + ':' + '0' * 64)
        if not row or not valid:
            raise HTTPException(401, '用户名或密码错误')
        issue_session(c, response, row['id'])
    return {'id': row['id'], 'username': row['username'], 'nickname': row['nickname']}

@app.post('/api/auth/logout', tags=['用户'])
def logout(request: Request, response: Response):
    with db() as c:
        c.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(request.cookies.get('market_session', '').encode()).hexdigest(),))
    response.delete_cookie('market_session')
    return {'ok': True}

@app.get('/api/me', tags=['用户'])
def me(user=Depends(current_user)):
    return user

@app.get('/api/health', tags=['运维'])
def health():
    with db() as c:
        c.execute('SELECT 1')
    return {'status': 'ok', 'version': '0.1.0-beta.1'}

@app.get('/api/categories', tags=['商品'])
def categories():
    return CATEGORIES

class ProductInput(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=5, max_length=3000)
    price: Decimal = Field(ge=0, le=999999, decimal_places=2, allow_inf_nan=False)
    category: str
    image_url: str = Field(min_length=1, max_length=600)
    contact: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=80)
    condition: Literal['全新', '几乎全新', '轻微使用', '正常使用'] = '轻微使用'

    @field_validator('title', 'description', 'contact', 'location')
    @classmethod
    def trim(cls, value):
        if len(value.strip()) < 2:
            raise ValueError('不能为空')
        return value.strip()

    @field_validator('category')
    @classmethod
    def category_check(cls, value):
        if value not in CATEGORIES:
            raise ValueError('分类无效')
        return value

    @field_validator('image_url')
    @classmethod
    def image_check(cls, value):
        from urllib.parse import urlsplit
        url = urlsplit(value)
        if value.startswith(('/uploads/', '/assets/')) and '..' not in value and '\\' not in value:
            return value
        if url.scheme == 'https' and url.netloc and not url.username and not url.password:
            return value
        raise ValueError('请上传图片或使用 HTTPS 图片 URL')

def product_dict(row, include_contact=False):
    result = dict(row)
    result['price'] = result.pop('price_cents') / 100
    if not include_contact:
        result.pop('contact', None)
    return result

SELECT_PRODUCT = 'SELECT p.*,u.nickname AS seller FROM products p JOIN users u ON u.id=p.owner_id'

def search_owner(request, response):
    try:
        return 'user:' + str(current_user(request)['id']), 'account'
    except HTTPException:
        pass
    import re
    token = request.cookies.get('xishi_search_device', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        token = secrets.token_urlsafe(32)
        response.set_cookie('xishi_search_device', token, httponly=True, samesite='lax', secure=os.environ.get('COOKIE_SECURE') == '1', max_age=86400*365)
    return 'device:' + hashlib.sha256(token.encode()).hexdigest(), 'device'

class SearchHistoryInput(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)

    @field_validator('keyword')
    @classmethod
    def clean_keyword(cls, value):
        value = ' '.join(value.split())
        if not value:
            raise ValueError('搜索词不能为空')
        return value

@app.get('/api/search/history', tags=['搜索'])
def get_search_history(request: Request, response: Response):
    owner, scope = search_owner(request, response)
    with db() as c:
        rows = c.execute('SELECT keyword FROM search_history WHERE owner_key=? ORDER BY used_at DESC,id DESC LIMIT 12', (owner,)).fetchall()
    return {'items':[r['keyword'] for r in rows], 'scope':scope}

@app.post('/api/search/history', tags=['搜索'])
def save_search_history(p: SearchHistoryInput, request: Request, response: Response):
    owner, _ = search_owner(request, response)
    with db() as c:
        c.execute('INSERT INTO search_history(owner_key,keyword_key,keyword,used_at) VALUES(?,?,?,?) ON CONFLICT(owner_key,keyword_key) DO UPDATE SET keyword=excluded.keyword,used_at=excluded.used_at', (owner,p.keyword.casefold(),p.keyword,time.time_ns()//1000))
        c.execute('DELETE FROM search_history WHERE owner_key=? AND id NOT IN (SELECT id FROM search_history WHERE owner_key=? ORDER BY used_at DESC,id DESC LIMIT 12)', (owner,owner))
    return {'ok':True}

@app.delete('/api/search/history', tags=['搜索'])
def delete_search_history(request: Request, response: Response, keyword: str | None = Query(None,max_length=100)):
    owner, _ = search_owner(request,response)
    with db() as c:
        if keyword is None:
            c.execute('DELETE FROM search_history WHERE owner_key=?',(owner,))
        else:
            c.execute('DELETE FROM search_history WHERE owner_key=? AND keyword_key=?',(owner,' '.join(keyword.split()).casefold()))
    return {'ok':True}

@app.get('/api/search/suggestions', tags=['搜索'])
def search_suggestions(q: str = Query('',max_length=100), limit: int = Query(8,ge=1,le=24)):
    term = ' '.join(q.split())
    with db() as c:
        if term:
            tokens = list(dict.fromkeys(term.split()))
            clauses = ' AND '.join('instr(lower(title),lower(?))>0' for _ in tokens)
            rows = c.execute("SELECT title FROM products WHERE status='on_sale' AND " + clauses + ' GROUP BY title ORDER BY CASE WHEN lower(title)=lower(?) THEN 0 WHEN instr(lower(title),lower(?))=1 THEN 1 ELSE 2 END,MAX(id) DESC LIMIT ?', tokens+[term,term,limit]).fetchall()
            return {'items':[r['title'] for r in rows]}
        # 候选词只在确实存在匹配在售商品时展示，不伪造热搜次数。
        terms = ['教材','耳机','台灯','运动鞋','相机','帆布包','键盘','绿植','自行车','书桌','显示器','背包']
        result=[]
        for word in terms:
            if c.execute("SELECT 1 FROM products WHERE status='on_sale' AND instr(title,?)>0 LIMIT 1",(word,)).fetchone():
                result.append(word)
        for row in c.execute("SELECT title FROM products WHERE status='on_sale' GROUP BY title ORDER BY MAX(id) DESC LIMIT 24"):
            if row['title'] not in result:
                result.append(row['title'])
    return {'items':result[:limit]}

@app.get('/api/products', tags=['商品'])
def products(q: str = Query('', max_length=100), category: str = '', min_price: Decimal = Query(0, ge=0, le=999999,decimal_places=2,allow_inf_nan=False), max_price: Decimal = Query(999999, ge=0, le=999999,decimal_places=2,allow_inf_nan=False), sort: Literal['relevance','newest','price_asc','price_desc']='relevance', condition: Literal['全新','几乎全新','轻微使用','正常使用'] | None = None, published_within: int | None = Query(None,ge=1,le=14), page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=48)):
    if min_price > max_price:
        raise HTTPException(422, '最低价不能高于最高价')
    if published_within is not None and published_within not in (1,3,7,14):
        raise HTTPException(422, '发布时间仅支持 1、3、7、14 天内')
    where = " WHERE p.status='on_sale' AND p.price_cents>=? AND p.price_cents<=?"
    args = [int(min_price * 100), int(max_price * 100)]
    term = ' '.join(q.split())
    tokens = list(dict.fromkeys(term.split()))
    for token in tokens:
        where += ' AND (instr(lower(p.title),lower(?))>0 OR instr(lower(p.description),lower(?))>0)'
        args.extend([token,token])
    if category:
        where += ' AND p.category=?'
        args.append(category)
    if condition:
        where += ' AND p.condition=?'
        args.append(condition)
    if published_within:
        where += " AND p.created_at>=datetime('now',?)"
        args.append(f'-{published_within} days')
    order_args=[]
    if sort=='relevance' and term:
        title_tokens=' AND '.join('instr(lower(p.title),lower(?))>0' for _ in tokens)
        order='CASE WHEN lower(p.title)=lower(?) THEN 0 WHEN instr(lower(p.title),lower(?))=1 THEN 1 WHEN instr(lower(p.title),lower(?))>0 THEN 2 WHEN '+title_tokens+' THEN 3 ELSE 4 END,p.id DESC'
        order_args=[term,term,term]+tokens
    else:
        order = {'relevance':'p.id DESC','newest':'p.id DESC','price_asc':'p.price_cents,p.id DESC','price_desc':'p.price_cents DESC,p.id DESC'}[sort]
    with db() as c:
        total = c.execute('SELECT COUNT(*) FROM products p' + where, args).fetchone()[0]
        rows = c.execute(SELECT_PRODUCT + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', args + order_args + [page_size, (page-1)*page_size]).fetchall()
    return {'items': [product_dict(r) for r in rows], 'total': total, 'page': page, 'page_size': page_size}

@app.get('/api/me/products', tags=['个人中心'])
def my_products(user=Depends(current_user)):
    with db() as c:
        return [product_dict(r, True) for r in c.execute(SELECT_PRODUCT + ' WHERE p.owner_id=? ORDER BY p.id DESC', (user['id'],))]

@app.get('/api/me/favorites', tags=['个人中心'])
def my_favorites(user=Depends(current_user)):
    with db() as c:
        return [product_dict(r) for r in c.execute(SELECT_PRODUCT + ' JOIN favorites f ON f.product_id=p.id WHERE f.user_id=? ORDER BY f.created_at DESC,p.id DESC', (user['id'],))]

def get_product(c, pid):
    row = c.execute(SELECT_PRODUCT + ' WHERE p.id=?', (pid,)).fetchone()
    if not row:
        raise HTTPException(404, '商品不存在')
    return row

def owned(c, pid, user):
    row = get_product(c, pid)
    if row['owner_id'] != user['id']:
        raise HTTPException(403, '只能管理自己发布的商品')
    return row

@app.get('/api/products/{pid}', tags=['商品'])
def detail(pid: int, request: Request):
    with db() as c:
        row = get_product(c, pid)
        result = product_dict(row)
        try:
            user = current_user(request)
        except HTTPException:
            user = None
        result['contact'] = row['contact'] if user else '登录后查看联系方式'
        result['favorited'] = bool(user and c.execute('SELECT 1 FROM favorites WHERE user_id=? AND product_id=?', (user['id'], pid)).fetchone())
        return result

@app.post('/api/products', status_code=201, tags=['商品'])
def create_product(p: ProductInput, user=Depends(current_user)):
    with db() as c:
        pid = c.execute('INSERT INTO products(owner_id,title,description,price_cents,category,image_url,contact,location,condition) VALUES(?,?,?,?,?,?,?,?,?)', (user['id'],p.title,p.description,int(p.price*100),p.category,p.image_url,p.contact,p.location,p.condition)).lastrowid
    return {'id': pid}

@app.put('/api/products/{pid}', tags=['商品'])
def edit_product(pid: int, p: ProductInput, user=Depends(current_user)):
    with db() as c:
        owned(c,pid,user)
        c.execute('UPDATE products SET title=?,description=?,price_cents=?,category=?,image_url=?,contact=?,location=?,condition=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (p.title,p.description,int(p.price*100),p.category,p.image_url,p.contact,p.location,p.condition,pid))
    return {'ok': True}

class StatusInput(BaseModel):
    status: STATUS

@app.patch('/api/products/{pid}/status', tags=['商品'])
def change_status(pid: int, p: StatusInput, user=Depends(current_user)):
    with db() as c:
        old = owned(c,pid,user)
        if old['status'] == 'sold' and p.status != 'sold':
            raise HTTPException(409, '已售商品不能重新上架，请重新发布')
        c.execute('UPDATE products SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (p.status,pid))
    return {'ok': True}

@app.put('/api/products/{pid}/favorite', tags=['收藏'])
def favorite(pid: int, user=Depends(current_user)):
    with db() as c:
        get_product(c,pid)
        c.execute('INSERT OR IGNORE INTO favorites(user_id,product_id) VALUES(?,?)', (user['id'],pid))
    return {'ok': True}

@app.delete('/api/products/{pid}/favorite', tags=['收藏'])
def unfavorite(pid: int, user=Depends(current_user)):
    with db() as c:
        c.execute('DELETE FROM favorites WHERE user_id=? AND product_id=?', (user['id'],pid))
    return {'ok': True}

class MessageInput(BaseModel):
    content: str = Field(min_length=1,max_length=500)
    parent_id: int | None = None

    @field_validator('content')
    @classmethod
    def content_check(cls, value):
        if not value.strip():
            raise ValueError('内容不能为空')
        return value.strip()

@app.get('/api/products/{pid}/messages', tags=['留言'])
def messages(pid: int):
    with db() as c:
        get_product(c,pid)
        return [dict(r) for r in c.execute('SELECT m.*,u.nickname FROM messages m JOIN users u ON u.id=m.user_id WHERE m.product_id=? ORDER BY m.id', (pid,))]

@app.post('/api/products/{pid}/messages', status_code=201, tags=['留言'])
def add_message(pid: int, p: MessageInput, user=Depends(current_user)):
    with db() as c:
        product = get_product(c,pid)
        if product['status'] != 'on_sale':
            raise HTTPException(409, '商品已下架或售出，不能继续留言')
        if p.parent_id is not None:
            parent = c.execute('SELECT * FROM messages WHERE id=? AND product_id=?', (p.parent_id,pid)).fetchone()
            if not parent or parent['parent_id'] is not None:
                raise HTTPException(422, '回复目标无效')
            if user['id'] != product['owner_id']:
                raise HTTPException(403, '只有卖家可以回复询价')
        mid = c.execute('INSERT INTO messages(product_id,user_id,content,parent_id) VALUES(?,?,?,?)', (pid,user['id'],p.content,p.parent_id)).lastrowid
    return {'id': mid}

@app.post('/api/uploads', status_code=201, tags=['图片'])
async def upload(file: UploadFile = File(...), user=Depends(current_user)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, '图片不能超过 5 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(BytesIO(raw))
            if image.format not in ('JPEG','PNG','WEBP') or image.width * image.height > 20000000:
                raise ValueError()
            image.load()
            image = image.convert('RGB')
            image.thumbnail((1600,1600))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, '请上传有效的 JPG、PNG 或 WebP 图片（最多 2000 万像素）')
    name = secrets.token_hex(16) + '.jpg'
    image.save(DATA / 'uploads' / name, 'JPEG', quality=85)
    return {'url': '/uploads/' + name}

# 只挂载前端和上传目录，数据库及后端源码不暴露。
(DATA / 'uploads').mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=DATA / 'uploads'), name='uploads')
app.mount('/assets', StaticFiles(directory=ROOT / 'frontend/assets'), name='assets')
app.mount('/vendor', StaticFiles(directory=ROOT / 'frontend/vendor'), name='vendor')

@app.get('/', include_in_schema=False)
def index():
    return FileResponse(ROOT / 'frontend/index.html')

@app.get('/app.js', include_in_schema=False)
def script():
    return FileResponse(ROOT / 'frontend/app.js', media_type='text/javascript')

@app.get('/style.css', include_in_schema=False)
def style():
    return FileResponse(ROOT / 'frontend/style.css', media_type='text/css')
