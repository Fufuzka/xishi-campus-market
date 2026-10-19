"""校园业务：认证、求购、私聊、线下订单与人工管理。"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
import sqlite3
import json
from fastapi import UploadFile, File
from fastapi.responses import FileResponse
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator


def migrate(c, categories):
    additions = {
        'users': {'role': "TEXT NOT NULL DEFAULT 'student'", 'disabled': 'INTEGER NOT NULL DEFAULT 0',
                  'verification': "TEXT NOT NULL DEFAULT 'unverified'", 'real_name': "TEXT NOT NULL DEFAULT ''",
                  'student_no': "TEXT NOT NULL DEFAULT ''", 'college': "TEXT NOT NULL DEFAULT ''",
                  'verification_note': "TEXT NOT NULL DEFAULT ''", 'verification_images': "TEXT NOT NULL DEFAULT '[]'"},
        'products': {'campus': "TEXT NOT NULL DEFAULT '主校区'", 'trade_method': "TEXT NOT NULL DEFAULT '当面交易'",
                     'review_status': "TEXT NOT NULL DEFAULT 'pending'", 'review_note': "TEXT NOT NULL DEFAULT ''",
                     'deleted': 'INTEGER NOT NULL DEFAULT 0', 'image_urls': "TEXT NOT NULL DEFAULT '[]'"},
    }
    for table, columns in additions.items():
        present = {r[1] for r in c.execute(f'PRAGMA table_info({table})')}
        for name, declaration in columns.items():
            if name not in present:
                c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {declaration}')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS verification_uploads(name TEXT PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS categories(name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS wanted(
      id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,
      description TEXT NOT NULL,budget_cents INTEGER NOT NULL CHECK(budget_cents>=0),condition TEXT NOT NULL,
      campus TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS conversations(
      id INTEGER PRIMARY KEY,starter_id INTEGER NOT NULL REFERENCES users(id),recipient_id INTEGER NOT NULL REFERENCES users(id),
      product_id INTEGER REFERENCES products(id),wanted_id INTEGER REFERENCES wanted(id),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_product ON conversations(starter_id,recipient_id,product_id) WHERE product_id IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_wanted ON conversations(starter_id,recipient_id,wanted_id) WHERE wanted_id IS NOT NULL;
    CREATE TABLE IF NOT EXISTS private_messages(
      id INTEGER PRIMARY KEY,conversation_id INTEGER NOT NULL REFERENCES conversations(id),sender_id INTEGER NOT NULL REFERENCES users(id),
      content TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_private_messages ON private_messages(conversation_id,id);
    CREATE TABLE IF NOT EXISTS orders(
      id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),buyer_id INTEGER NOT NULL REFERENCES users(id),
      seller_id INTEGER NOT NULL REFERENCES users(id),price_cents INTEGER NOT NULL,title TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending_communication',meeting_place TEXT NOT NULL DEFAULT '',
      meeting_time TEXT NOT NULL DEFAULT '',buyer_confirmed INTEGER NOT NULL DEFAULT 0,seller_confirmed INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_order_active_product ON orders(product_id) WHERE status IN ('pending_communication','pending_trade');
    CREATE TABLE IF NOT EXISTS reports(
      id INTEGER PRIMARY KEY,reporter_id INTEGER NOT NULL REFERENCES users(id),product_id INTEGER NOT NULL REFERENCES products(id),
      reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',resolution TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS audit_log(
      id INTEGER PRIMARY KEY,actor_id INTEGER NOT NULL REFERENCES users(id),action TEXT NOT NULL,
      target_id INTEGER NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_student_no ON users(student_no) WHERE student_no<>'' AND verification IN ('pending','approved');
    ''')
    # 只初始化一次；被管理员停用的分类不会在重启时恢复。
    if not c.execute('SELECT 1 FROM categories LIMIT 1').fetchone():
        c.executemany('INSERT INTO categories(name) VALUES(?)', [(x,) for x in categories])


class TextModel(BaseModel):
    @field_validator('*', mode='before')
    @classmethod
    def strip_strings(cls, v):
        return v.strip() if isinstance(v, str) else v


class Verification(TextModel):
    real_name: str = Field(min_length=2,max_length=30)
    student_no: str = Field(min_length=4,max_length=32,pattern=r'^[A-Za-z0-9-]+$')
    college: str = Field(min_length=2,max_length=80)
    image_urls: list[str] = Field(min_length=1,max_length=3)


class Review(TextModel):
    status: Literal['approved','rejected']
    note: str = Field(default='',max_length=500)


class WantedInput(TextModel):
    title: str = Field(min_length=2,max_length=80)
    description: str = Field(min_length=5,max_length=2000)
    budget: Decimal = Field(ge=0,le=999999,decimal_places=2,allow_inf_nan=False)
    condition: Literal['不限','全新','几乎全新','轻微使用','正常使用'] = '不限'
    campus: str = Field(min_length=2,max_length=40)


class ConversationInput(BaseModel):
    product_id: int | None = Field(None,gt=0)
    wanted_id: int | None = Field(None,gt=0)


class ChatInput(TextModel):
    content: str = Field(min_length=1,max_length=2000)


class OrderInput(BaseModel):
    product_id: int = Field(gt=0)


class Appointment(TextModel):
    meeting_place: str = Field(min_length=2,max_length=100)
    meeting_time: str = Field(min_length=16,max_length=25)

    @field_validator('meeting_time')
    @classmethod
    def valid_time(cls, value):
        moment = datetime.fromisoformat(value)
        if moment.tzinfo or moment <= datetime.now():
            raise ValueError('请选择未来的本地时间')
        return moment.isoformat(timespec='minutes')


class ReportInput(TextModel):
    product_id: int = Field(gt=0)
    reason: str = Field(min_length=5,max_length=500)


class ResolveReport(TextModel):
    status: Literal['resolved','dismissed']
    resolution: str = Field(min_length=2,max_length=500)
    remove_product: bool = False


class UserState(BaseModel):
    disabled: bool


class CategoryInput(TextModel):
    name: str = Field(min_length=2,max_length=30)
    active: bool = True


def install(app, b):
    def verified(user=Depends(b.current_user)):
        if user['verification'] != 'approved':
            raise HTTPException(403,'请先在学生认证中提交资料并等待审核通过')
        return user

    b.verified_user = verified

    def admin(user=Depends(b.current_user)):
        if user['role'] != 'admin':
            raise HTTPException(403,'仅管理员可以操作')
        return user

    def audit(c, user, action, target, note=''):
        c.execute('INSERT INTO audit_log(actor_id,action,target_id,note) VALUES(?,?,?,?)',(user['id'],action,target,note))

    def conversation(c, cid, user):
        row=c.execute('SELECT * FROM conversations WHERE id=?',(cid,)).fetchone()
        if not row or user['id'] not in (row['starter_id'],row['recipient_id']):
            raise HTTPException(404,'会话不存在')
        return row

    def order(c, oid, user):
        row=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
        if not row or user['id'] not in (row['buyer_id'],row['seller_id']):
            raise HTTPException(404,'订单不存在')
        return row


    @app.post('/api/verification-images',status_code=201,tags=['学生认证'])
    async def upload_proof(file:UploadFile=File(...),user=Depends(b.current_user)):
        raw=await file.read(5*1024*1024+1)
        if len(raw)>5*1024*1024:raise HTTPException(413,'图片不能超过 5 MB')
        name=b.save_image(raw,b.DATA/'verification-images')
        with b.db() as c:c.execute('INSERT INTO verification_uploads(name,owner_id) VALUES(?,?)',(name,user['id']))
        return {'url':'/api/verification-images/'+name}

    @app.get('/api/verification-images/{name}',tags=['学生认证'])
    def proof_image(name:str,user=Depends(b.current_user)):
        with b.db() as c:
            row=c.execute('SELECT owner_id FROM verification_uploads WHERE name=?',(name,)).fetchone()
            if not row or (row['owner_id']!=user['id'] and user['role']!='admin'):raise HTTPException(404,'图片不存在')
        file=b.DATA/'verification-images'/name
        if not file.is_file():raise HTTPException(404,'图片不存在')
        return FileResponse(file,media_type='image/jpeg',headers={'Cache-Control':'no-store'})

    @app.post('/api/orders/{oid}/conversation',tags=['私聊'])
    def order_conversation(oid:int,user=Depends(verified)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=order(c,oid,user)
            c.execute('INSERT OR IGNORE INTO conversations(starter_id,recipient_id,product_id) VALUES(?,?,?)',(row['buyer_id'],row['seller_id'],row['product_id']))
            cid=c.execute('SELECT id FROM conversations WHERE starter_id=? AND recipient_id=? AND product_id=?',(row['buyer_id'],row['seller_id'],row['product_id'])).fetchone()[0]
        return {'id':cid}

    @app.get('/api/me/verification',tags=['学生认证'])
    def get_verification(user=Depends(b.current_user)):
        with b.db() as c:
            row=dict(c.execute('SELECT verification,real_name,student_no,college,verification_note,verification_images FROM users WHERE id=?',(user['id'],)).fetchone())
            row['image_urls']=json.loads(row.pop('verification_images'))
            return row

    @app.post('/api/me/verification',tags=['学生认证'])
    def submit_verification(p:Verification,user=Depends(b.current_user)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            state=c.execute('SELECT verification FROM users WHERE id=?',(user['id'],)).fetchone()[0]
            if state in ('pending','approved'):
                raise HTTPException(409,'资料正在审核或已通过，不可重复提交')
            if len(set(p.image_urls))!=len(p.image_urls):raise HTTPException(422,'不能提交重复图片')
            for url in p.image_urls:
                if not url.startswith('/api/verification-images/') or not c.execute('SELECT 1 FROM verification_uploads WHERE name=? AND owner_id=?',(url.removeprefix('/api/verification-images/'),user['id'])).fetchone():raise HTTPException(422,'请上传本人的认证证明图片')
            try:
                c.execute("UPDATE users SET real_name=?,student_no=?,college=?,verification_images=?,verification='pending',verification_note='' WHERE id=?",(p.real_name,p.student_no,p.college,json.dumps(p.image_urls),user['id']))
            except sqlite3.IntegrityError:
                raise HTTPException(409,'该学号已有认证申请')
        return {'ok':True}

    @app.get('/api/wanted',tags=['求购'])
    def list_wanted(q:str=Query('',max_length=100),campus:str=Query('',max_length=40),mine:bool=False,page:int=Query(1,ge=1),request:b.Request=None):
        args=[];where=" WHERE w.status='open' AND u.disabled=0"
        if mine:
            user=b.current_user(request);where=' WHERE w.owner_id=?';args=[user['id']]
        if q:
            where+=' AND (instr(w.title,?)>0 OR instr(w.description,?)>0)';args.extend([q,q])
        if campus:
            where+=' AND w.campus=?';args.append(campus)
        with b.db() as c:
            source=' FROM wanted w JOIN users u ON u.id=w.owner_id'
            total=c.execute('SELECT COUNT(*)'+source+where,args).fetchone()[0]
            rows=c.execute('SELECT w.*,u.nickname AS buyer'+source+where+' ORDER BY w.id DESC LIMIT 12 OFFSET ?',args+[(page-1)*12]).fetchall()
        return {'items':[{**dict(x),'budget':x['budget_cents']/100} for x in rows],'total':total,'page':page}

    @app.post('/api/wanted',status_code=201,tags=['求购'])
    def create_wanted(p:WantedInput,user=Depends(verified)):
        with b.db() as c:
            wid=c.execute('INSERT INTO wanted(owner_id,title,description,budget_cents,condition,campus) VALUES(?,?,?,?,?,?)',(user['id'],p.title,p.description,int(p.budget*100),p.condition,p.campus)).lastrowid
        return {'id':wid}

    @app.put('/api/wanted/{wid}',tags=['求购'])
    def edit_wanted(wid:int,p:WantedInput,user=Depends(verified)):
        with b.db() as c:
            row=c.execute('SELECT * FROM wanted WHERE id=? AND owner_id=?',(wid,user['id'])).fetchone()
            if not row:raise HTTPException(404,'求购不存在')
            if row['status']!='open':raise HTTPException(409,'已结束求购不能修改')
            c.execute('UPDATE wanted SET title=?,description=?,budget_cents=?,condition=?,campus=? WHERE id=?',(p.title,p.description,int(p.budget*100),p.condition,p.campus,wid))
        return {'ok':True}

    @app.delete('/api/wanted/{wid}',tags=['求购'])
    def close_wanted(wid:int,user=Depends(b.current_user)):
        with b.db() as c:
            if not c.execute('SELECT 1 FROM wanted WHERE id=? AND owner_id=?',(wid,user['id'])).fetchone():raise HTTPException(404,'求购不存在')
            c.execute("UPDATE wanted SET status='closed' WHERE id=?",(wid,))
        return {'ok':True}

    @app.post('/api/conversations',status_code=201,tags=['私聊'])
    def start_chat(p:ConversationInput,user=Depends(verified)):
        if (p.product_id is None)==(p.wanted_id is None):raise HTTPException(422,'请选择一个商品或求购')
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if p.product_id:
                row=b.get_product(c,p.product_id)
                if row['status']!='on_sale' or row['review_status']!='approved':raise HTTPException(409,'商品当前不可联系')
            else:
                row=c.execute("SELECT * FROM wanted WHERE id=? AND status='open'",(p.wanted_id,)).fetchone()
                if not row:raise HTTPException(404,'求购已结束或不存在')
            recipient=row['owner_id']
            if recipient==user['id']:raise HTTPException(422,'不能与自己发起私聊')
            if c.execute('SELECT disabled FROM users WHERE id=?',(recipient,)).fetchone()[0]:raise HTTPException(409,'对方账号不可联系')
            key='product_id' if p.product_id else 'wanted_id';target=p.product_id or p.wanted_id
            existing=c.execute(f'SELECT id FROM conversations WHERE starter_id=? AND recipient_id=? AND {key}=?',(user['id'],recipient,target)).fetchone()
            cid=existing[0] if existing else c.execute('INSERT INTO conversations(starter_id,recipient_id,product_id,wanted_id) VALUES(?,?,?,?)',(user['id'],recipient,p.product_id,p.wanted_id)).lastrowid
        return {'id':cid}

    @app.get('/api/conversations',tags=['私聊'])
    def chats(user=Depends(b.current_user)):
        with b.db() as c:
            return [dict(x) for x in c.execute('''SELECT v.*,u.nickname AS peer,COALESCE(p.title,w.title) AS title,
            (SELECT content FROM private_messages WHERE conversation_id=v.id ORDER BY id DESC LIMIT 1) AS last_message
            FROM conversations v JOIN users u ON u.id=CASE WHEN v.starter_id=? THEN v.recipient_id ELSE v.starter_id END
            LEFT JOIN products p ON p.id=v.product_id LEFT JOIN wanted w ON w.id=v.wanted_id
            WHERE v.starter_id=? OR v.recipient_id=? ORDER BY v.id DESC''',(user['id'],user['id'],user['id']))]

    @app.get('/api/conversations/{cid}/messages',tags=['私聊'])
    def private_messages(cid:int,after:int=Query(0,ge=0),user=Depends(b.current_user)):
        with b.db() as c:
            conversation(c,cid,user)
            return [dict(x) for x in c.execute('SELECT m.*,u.nickname FROM private_messages m JOIN users u ON u.id=m.sender_id WHERE conversation_id=? AND m.id>? ORDER BY m.id LIMIT 100',(cid,after))]

    @app.post('/api/conversations/{cid}/messages',status_code=201,tags=['私聊'])
    def send_private(cid:int,p:ChatInput,user=Depends(verified)):
        with b.db() as c:
            row=conversation(c,cid,user)
            peer=row['recipient_id'] if row['starter_id']==user['id'] else row['starter_id']
            if c.execute('SELECT disabled FROM users WHERE id=?',(peer,)).fetchone()[0]:raise HTTPException(409,'对方账号不可联系')
            mid=c.execute('INSERT INTO private_messages(conversation_id,sender_id,content) VALUES(?,?,?)',(cid,user['id'],p.content)).lastrowid
        return {'id':mid}

    @app.post('/api/orders',status_code=201,tags=['线下订单'])
    def create_order(p:OrderInput,user=Depends(verified)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=b.get_product(c,p.product_id)
            if row['owner_id']==user['id']:raise HTTPException(422,'不能购买自己的商品')
            if row['status']!='on_sale' or row['review_status']!='approved' or row['seller_disabled']:raise HTTPException(409,'商品不可交易')
            try:
                oid=c.execute('INSERT INTO orders(product_id,buyer_id,seller_id,price_cents,title) VALUES(?,?,?,?,?)',(row['id'],user['id'],row['owner_id'],row['price_cents'],row['title'])).lastrowid
            except sqlite3.IntegrityError:raise HTTPException(409,'该商品已有进行中的交易约定')
            c.execute('INSERT OR IGNORE INTO conversations(starter_id,recipient_id,product_id) VALUES(?,?,?)',(user['id'],row['owner_id'],row['id']))
        return {'id':oid}

    @app.get('/api/orders',tags=['线下订单'])
    def list_orders(user=Depends(b.current_user)):
        with b.db() as c:
            return [{**dict(x),'price':x['price_cents']/100} for x in c.execute('SELECT o.*,s.nickname AS seller,b.nickname AS buyer FROM orders o JOIN users s ON s.id=o.seller_id JOIN users b ON b.id=o.buyer_id WHERE buyer_id=? OR seller_id=? ORDER BY o.id DESC',(user['id'],user['id']))]

    @app.patch('/api/orders/{oid}/appointment',tags=['线下订单'])
    def appointment(oid:int,p:Appointment,user=Depends(verified)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=order(c,oid,user)
            if row['seller_id']!=user['id']:raise HTTPException(403,'由卖家确认面交时间和地点')
            if row['status']!='pending_communication':raise HTTPException(409,'当前状态不可修改约定，请取消后重新约定')
            product=b.get_product(c,row['product_id'])
            if product['status']!='on_sale' or product['review_status']!='approved':raise HTTPException(409,'商品不可交易')
            c.execute("UPDATE orders SET meeting_place=?,meeting_time=?,status='pending_trade',updated_at=CURRENT_TIMESTAMP WHERE id=?",(p.meeting_place,p.meeting_time,oid))
        return {'ok':True}

    @app.post('/api/orders/{oid}/complete',tags=['线下订单'])
    def complete(oid:int,user=Depends(verified)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=order(c,oid,user)
            if row['status']!='pending_trade':raise HTTPException(409,'仅待交易订单可确认完成')
            field='buyer_confirmed' if row['buyer_id']==user['id'] else 'seller_confirmed'
            c.execute(f'UPDATE orders SET {field}=1,updated_at=CURRENT_TIMESTAMP WHERE id=?',(oid,))
            updated=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if updated['buyer_confirmed'] and updated['seller_confirmed']:
                c.execute("UPDATE orders SET status='completed' WHERE id=?",(oid,))
                c.execute("UPDATE products SET status='sold',updated_at=CURRENT_TIMESTAMP WHERE id=?",(row['product_id'],))
        return {'ok':True}

    @app.post('/api/orders/{oid}/cancel',tags=['线下订单'])
    def cancel(oid:int,user=Depends(b.current_user)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=order(c,oid,user)
            if row['status'] not in ('pending_communication','pending_trade'):raise HTTPException(409,'订单已结束')
            c.execute("UPDATE orders SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
        return {'ok':True}

    @app.delete('/api/products/{pid}',tags=['商品'])
    def delete_product(pid:int,user=Depends(b.current_user)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');b.owned(c,pid,user)
            if c.execute("SELECT 1 FROM orders WHERE product_id=? AND status IN ('pending_communication','pending_trade')",(pid,)).fetchone():raise HTTPException(409,'请先结束进行中的订单')
            c.execute("UPDATE products SET deleted=1,status='off_shelf' WHERE id=?",(pid,))
        return {'ok':True}

    @app.post('/api/reports',status_code=201,tags=['举报'])
    def report(p:ReportInput,user=Depends(b.current_user)):
        with b.db() as c:
            row=b.get_product(c,p.product_id)
            if row['owner_id']==user['id']:raise HTTPException(422,'不能举报自己的商品')
            if c.execute("SELECT 1 FROM reports WHERE reporter_id=? AND product_id=? AND status='pending'",(user['id'],p.product_id)).fetchone():raise HTTPException(409,'已有待处理举报')
            rid=c.execute('INSERT INTO reports(reporter_id,product_id,reason) VALUES(?,?,?)',(user['id'],p.product_id,p.reason)).lastrowid
        return {'id':rid}

    @app.get('/api/me/reports',tags=['举报'])
    def my_reports(user=Depends(b.current_user)):
        with b.db() as c:return [dict(x) for x in c.execute('SELECT r.*,p.title FROM reports r JOIN products p ON p.id=r.product_id WHERE reporter_id=? ORDER BY r.id DESC',(user['id'],))]

    @app.get('/api/admin/overview',tags=['管理'])
    def overview(user=Depends(admin)):
        with b.db() as c:
            return {key:c.execute(sql).fetchone()[0] for key,sql in {
                'verifications':"SELECT COUNT(*) FROM users WHERE verification='pending'",
                'products':"SELECT COUNT(*) FROM products WHERE review_status='pending' AND deleted=0",
                'reports':"SELECT COUNT(*) FROM reports WHERE status='pending'"}.items()}

    @app.get('/api/admin/verifications',tags=['管理'])
    def verifications(user=Depends(admin)):
        with b.db() as c:return [{**dict(x),'image_urls':json.loads(x['verification_images'])} for x in c.execute("SELECT id,username,nickname,real_name,student_no,college,verification,verification_note,verification_images FROM users WHERE verification!='unverified' ORDER BY CASE WHEN verification='pending' THEN 0 ELSE 1 END,id DESC")]

    @app.patch('/api/admin/verifications/{uid}',tags=['管理'])
    def review_verification(uid:int,p:Review,user=Depends(admin)):
        if p.status=='rejected' and not p.note:raise HTTPException(422,'请填写退回原因')
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT verification FROM users WHERE id=?',(uid,)).fetchone()
            if not row:raise HTTPException(404,'用户不存在')
            if row[0]!='pending':raise HTTPException(409,'仅待审核申请可处理')
            c.execute('UPDATE users SET verification=?,verification_note=? WHERE id=?',(p.status,p.note,uid));audit(c,user,'verification_'+p.status,uid,p.note)
        return {'ok':True}

    @app.get('/api/admin/products',tags=['管理'])
    def admin_products(user=Depends(admin)):
        with b.db() as c:return [b.product_dict(x) for x in c.execute(b.SELECT_PRODUCT+' WHERE p.deleted=0 ORDER BY p.id DESC')]

    @app.patch('/api/admin/products/{pid}',tags=['管理'])
    def review_product(pid:int,p:Review,user=Depends(admin)):
        if p.status=='rejected' and not p.note:raise HTTPException(422,'请填写退回原因')
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=b.get_product(c,pid)
            if p.status=='approved':
                owner=c.execute('SELECT disabled,verification FROM users WHERE id=?',(row['owner_id'],)).fetchone()
                if owner['disabled'] or owner['verification']!='approved':raise HTTPException(409,'卖家需认证通过且账号正常')
            c.execute('UPDATE products SET review_status=?,review_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(p.status,p.note,pid))
            if p.status=='rejected':c.execute("UPDATE orders SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE product_id=? AND status IN ('pending_communication','pending_trade')",(pid,))
            audit(c,user,'product_'+p.status,pid,p.note)
        return {'ok':True}

    @app.get('/api/admin/reports',tags=['管理'])
    def reports(user=Depends(admin)):
        with b.db() as c:return [dict(x) for x in c.execute('SELECT r.*,p.title,u.nickname AS reporter FROM reports r JOIN products p ON p.id=r.product_id JOIN users u ON u.id=r.reporter_id ORDER BY r.id DESC')]

    @app.patch('/api/admin/reports/{rid}',tags=['管理'])
    def resolve_report(rid:int,p:ResolveReport,user=Depends(admin)):
        if p.status=='dismissed' and p.remove_product:raise HTTPException(422,'驳回举报不能同时下架商品')
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone()
            if not row:raise HTTPException(404,'举报不存在')
            if row['status']!='pending':raise HTTPException(409,'举报已处理')
            c.execute('UPDATE reports SET status=?,resolution=? WHERE id=?',(p.status,p.resolution,rid))
            if p.remove_product:
                c.execute("UPDATE products SET review_status='rejected',review_note=?,status='off_shelf' WHERE id=?",(p.resolution,row['product_id']))
                c.execute("UPDATE orders SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE product_id=? AND status IN ('pending_communication','pending_trade')",(row['product_id'],))
            audit(c,user,'report_'+p.status,rid,p.resolution)
        return {'ok':True}

    @app.get('/api/admin/users',tags=['管理'])
    def users(user=Depends(admin)):
        with b.db() as c:return [dict(x) for x in c.execute('SELECT id,username,nickname,role,disabled,verification,created_at FROM users ORDER BY id DESC')]

    @app.patch('/api/admin/users/{uid}',tags=['管理'])
    def user_state(uid:int,p:UserState,user=Depends(admin)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not row:raise HTTPException(404,'用户不存在')
            if row['role']=='admin':raise HTTPException(409,'不能在此停用管理员')
            c.execute('UPDATE users SET disabled=? WHERE id=?',(int(p.disabled),uid))
            if p.disabled:
                c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
                c.execute("UPDATE orders SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE (buyer_id=? OR seller_id=?) AND status IN ('pending_communication','pending_trade')",(uid,uid))
            audit(c,user,'disable_user' if p.disabled else 'enable_user',uid)
        return {'ok':True}

    @app.get('/api/admin/categories',tags=['管理'])
    def all_categories(user=Depends(admin)):
        with b.db() as c:return [dict(x) for x in c.execute('SELECT * FROM categories ORDER BY rowid')]

    @app.put('/api/admin/categories',tags=['管理'])
    def save_category(p:CategoryInput,user=Depends(admin)):
        with b.db() as c:
            c.execute('INSERT INTO categories(name,active) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET active=excluded.active',(p.name,int(p.active)))
            audit(c,user,'category_state',0,p.name+':'+str(p.active))
        return {'ok':True}

    @app.get('/api/admin/audit',tags=['管理'])
    def audit_entries(user=Depends(admin)):
        with b.db() as c:return [dict(x) for x in c.execute('SELECT a.*,u.nickname FROM audit_log a JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 200')]
