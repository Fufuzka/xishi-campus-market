from datetime import datetime, timedelta
import sqlite3
import io
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from backend import main


def product(**kw):
    return dict(title='校园教材',description='保存完好的教材，可在图书馆面交。',price='28.50',category='教材书籍',image_url='/assets/book.svg',contact='仅用于测试',location='图书馆南门',condition='轻微使用',campus='南校区',trade_method='当面交易',**kw)


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA',tmp_path)
    main.init_db()
    with TestClient(main.app) as admin,TestClient(main.app) as seller,TestClient(main.app) as buyer,TestClient(main.app) as outsider:
        for client,name in [(admin,'admin'),(seller,'seller'),(buyer,'buyer'),(outsider,'outsider')]:
            assert client.post('/api/auth/register',json={'username':name,'password':'Campus2026!','nickname':name}).status_code==201
        with main.db() as c:c.execute("UPDATE users SET role='admin',verification='approved' WHERE username='admin'")
        yield admin,seller,buyer,outsider


def proof(client):
    data=io.BytesIO();Image.new('RGB',(20,20),(100,150,100)).save(data,'PNG')
    result=client.post('/api/verification-images',files={'file':('proof.png',data.getvalue(),'image/png')})
    assert result.status_code==201,result.text
    return [result.json()['url']]


def verify(admin,client,number):
    uid=client.get('/api/me').json()['id']
    r=client.post('/api/me/verification',json={'real_name':'测试学生','student_no':number,'college':'计算机学院','image_urls':proof(client)})
    assert r.status_code==200,r.text
    assert admin.patch(f'/api/admin/verifications/{uid}',json={'status':'approved'}).status_code==200
    return uid


def approved_product(admin,seller):
    verify(admin,seller,'S1001')
    r=seller.post('/api/products',json=product());assert r.status_code==201,r.text
    pid=r.json()['id']
    assert admin.patch(f'/api/admin/products/{pid}',json={'status':'approved'}).status_code==200
    return pid


def test_verification_gates_and_private_identity(env):
    admin,seller,buyer,_=env
    assert seller.post('/api/products',json=product()).status_code==403
    assert seller.post('/api/wanted',json={'title':'教材求购','description':'希望收一本高数教材','budget':30,'campus':'南校区'}).status_code==403
    uid=verify(admin,seller,'S1234')
    public=seller.get('/api/me').json()
    assert public['role']=='student' and public['verification']=='approved'
    assert all(k not in public for k in ['real_name','student_no','college','password_hash'])
    assert buyer.get('/api/admin/verifications').status_code==403
    assert 'S1234' not in buyer.get('/api/products').text
    assert seller.post('/api/me/verification',json={'real_name':'新姓名','student_no':'S2222','college':'文学学院','image_urls':proof(buyer)}).status_code==409
    assert buyer.post('/api/me/verification',json={'real_name':'他人姓名','student_no':'S1234','college':'文学学院','image_urls':proof(buyer)}).status_code==409


def test_rejected_verification_can_resubmit(env):
    admin,seller,_,_=env;uid=seller.get('/api/me').json()['id']
    data={'real_name':'测试学生','student_no':'S1002','college':'计算机学院','image_urls':proof(seller)}
    seller.post('/api/me/verification',json=data)
    assert admin.patch(f'/api/admin/verifications/{uid}',json={'status':'rejected'}).status_code==422
    assert admin.patch(f'/api/admin/verifications/{uid}',json={'status':'rejected','note':'请核对学院名称'}).status_code==200
    assert seller.get('/api/me/verification').json()['verification_note']=='请核对学院名称'
    assert seller.post('/api/me/verification',json=data).status_code==200


def test_product_review_campus_and_edit_recheck(env):
    admin,seller,buyer,_=env;verify(admin,seller,'S1003')
    pid=seller.post('/api/products',json=product()).json()['id']
    assert buyer.get('/api/products').json()['total']==0
    assert buyer.get(f'/api/products/{pid}').status_code==404
    assert buyer.get(f'/api/products/{pid}/messages').status_code==404
    assert buyer.get('/api/search/suggestions?q=教材').json()['items']==[]
    assert seller.get(f'/api/products/{pid}').json()['review_status']=='pending'
    admin.patch(f'/api/admin/products/{pid}',json={'status':'approved'})
    assert buyer.get('/api/products?campus=南校区').json()['total']==1
    assert buyer.get('/api/products?campus=北校区').json()['total']==0
    assert seller.put(f'/api/products/{pid}',json=product()).status_code==200
    assert buyer.get(f'/api/products/{pid}').status_code==404
    assert seller.patch(f'/api/products/{pid}/status',json={'status':'on_sale'}).status_code==409


def test_wanted_owner_management_and_private_chat(env):
    admin,seller,buyer,outsider=env;verify(admin,buyer,'B1001');verify(admin,seller,'S1004')
    data={'title':'求购二手键盘','description':'宿舍学习用，希望静音。','budget':'50.20','condition':'轻微使用','campus':'南校区'}
    wid=buyer.post('/api/wanted',json=data).json()['id']
    assert seller.get('/api/wanted?q=键盘&campus=南校区').json()['items'][0]['budget']==50.2
    assert seller.put(f'/api/wanted/{wid}',json=data).status_code==404
    cid=seller.post('/api/conversations',json={'wanted_id':wid}).json()['id']
    assert seller.post('/api/conversations',json={'wanted_id':wid}).json()['id']==cid
    assert seller.post(f'/api/conversations/{cid}/messages',json={'content':'我有一个键盘，想看看吗？'}).status_code==201
    assert buyer.get(f'/api/conversations/{cid}/messages').json()[0]['content']=='我有一个键盘，想看看吗？'
    assert outsider.get(f'/api/conversations/{cid}/messages').status_code==404
    assert outsider.post(f'/api/conversations/{cid}/messages',json={'content':'越权尝试'}).status_code==403
    assert buyer.delete(f'/api/wanted/{wid}').status_code==200
    assert seller.get('/api/wanted').json()['total']==0
    assert seller.post('/api/conversations',json={'wanted_id':wid}).status_code==404


def test_chat_context_and_disabled_peer(env):
    admin,seller,buyer,_=env;pid=approved_product(admin,seller);verify(admin,buyer,'B1002')
    assert seller.post('/api/conversations',json={'product_id':pid}).status_code==422
    assert buyer.post('/api/conversations',json={}).status_code==422
    assert buyer.post('/api/conversations',json={'product_id':pid,'wanted_id':1}).status_code==422
    cid=buyer.post('/api/conversations',json={'product_id':pid}).json()['id']
    assert buyer.post(f'/api/conversations/{cid}/messages',json={'content':'   '}).status_code==422
    uid=seller.get('/api/me').json()['id'];admin.patch(f'/api/admin/users/{uid}',json={'disabled':True})
    assert buyer.post(f'/api/conversations/{cid}/messages',json={'content':'能看货吗'}).status_code==409


def test_order_reservation_and_dual_completion(env):
    admin,seller,buyer,outsider=env;pid=approved_product(admin,seller);verify(admin,buyer,'B1003');verify(admin,outsider,'O1003')
    assert seller.post('/api/orders',json={'product_id':pid}).status_code==422
    oid=buyer.post('/api/orders',json={'product_id':pid}).json()['id']
    assert outsider.post('/api/orders',json={'product_id':pid}).status_code==409
    assert seller.delete(f'/api/products/{pid}').status_code==409
    assert seller.put(f'/api/products/{pid}',json=product()).status_code==409
    assert seller.patch(f'/api/products/{pid}/status',json={'status':'sold'}).status_code==409
    assert buyer.post(f'/api/orders/{oid}/complete').status_code==409
    meeting={'meeting_place':'图书馆南门','meeting_time':(datetime.now()+timedelta(days=1)).isoformat(timespec='minutes')}
    assert buyer.patch(f'/api/orders/{oid}/appointment',json=meeting).status_code==403
    assert outsider.patch(f'/api/orders/{oid}/appointment',json=meeting).status_code==404
    assert seller.patch(f'/api/orders/{oid}/appointment',json=meeting).status_code==200
    assert buyer.post(f'/api/orders/{oid}/complete').status_code==200
    assert buyer.get('/api/orders').json()[0]['status']=='pending_trade'
    assert seller.post(f'/api/orders/{oid}/complete').status_code==200
    assert buyer.get('/api/orders').json()[0]['status']=='completed'
    assert buyer.get(f'/api/products/{pid}').json()['status']=='sold'
    assert buyer.post(f'/api/orders/{oid}/cancel').status_code==409


def test_cancellation_releases_reservation_and_past_appointment_rejected(env):
    admin,seller,buyer,_=env;pid=approved_product(admin,seller);verify(admin,buyer,'B1004')
    oid=buyer.post('/api/orders',json={'product_id':pid}).json()['id']
    assert seller.patch(f'/api/orders/{oid}/appointment',json={'meeting_place':'南门','meeting_time':'2020-01-01T10:00'}).status_code==422
    assert buyer.post(f'/api/orders/{oid}/cancel').status_code==200
    assert buyer.post('/api/orders',json={'product_id':pid}).status_code==201


def test_reporting_moderation_and_audit(env):
    admin,seller,buyer,_=env;pid=approved_product(admin,seller);verify(admin,buyer,'B1005')
    oid=buyer.post('/api/orders',json={'product_id':pid}).json()['id']
    data={'product_id':pid,'reason':'商品描述涉嫌虚假，请核实。'}
    rid=buyer.post('/api/reports',json=data).json()['id']
    assert buyer.post('/api/reports',json=data).status_code==409
    assert seller.post('/api/reports',json=data).status_code==422
    assert buyer.patch(f'/api/admin/reports/{rid}',json={'status':'resolved','resolution':'恶意操作'}).status_code==403
    assert admin.patch(f'/api/admin/reports/{rid}',json={'status':'resolved','resolution':'核实后下架处理','remove_product':True}).status_code==200
    assert buyer.get('/api/me/reports').json()[0]['status']=='resolved'
    assert buyer.get('/api/orders').json()[0]['status']=='cancelled'
    assert buyer.get(f'/api/products/{pid}').status_code==404
    assert admin.get('/api/admin/audit').json()[0]['action']=='report_resolved'
    assert seller.patch(f'/api/products/{pid}/status',json={'status':'on_sale'}).status_code==409


def test_user_disable_revokes_sessions_and_hides_products(env):
    admin,seller,buyer,_=env;pid=approved_product(admin,seller);uid=seller.get('/api/me').json()['id']
    assert buyer.patch(f'/api/admin/users/{uid}',json={'disabled':True}).status_code==403
    aid=admin.get('/api/me').json()['id']
    assert admin.patch(f'/api/admin/users/{aid}',json={'disabled':True}).status_code==409
    assert admin.patch(f'/api/admin/users/{uid}',json={'disabled':True}).status_code==200
    assert seller.get('/api/me').status_code==401
    assert seller.post('/api/auth/login',json={'username':'seller','password':'Campus2026!'}).status_code==403
    assert buyer.get('/api/products').json()['total']==0
    assert buyer.get(f'/api/products/{pid}').status_code==404
    assert buyer.post('/api/orders',json={'product_id':pid}).status_code==403
    verify(admin,buyer,'Bdisabled')
    assert buyer.post('/api/orders',json={'product_id':pid}).status_code==409
    assert admin.patch(f'/api/admin/users/{uid}',json={'disabled':False}).status_code==200
    assert seller.post('/api/auth/login',json={'username':'seller','password':'Campus2026!'}).status_code==200


def test_categories_persist_and_deleted_product_hidden(env):
    admin,seller,buyer,_=env;pid=approved_product(admin,seller)
    assert buyer.put('/api/admin/categories',json={'name':'二手教材'}).status_code==403
    assert admin.put('/api/admin/categories',json={'name':'二手教材'}).status_code==200
    assert '二手教材' in buyer.get('/api/categories').json()
    assert admin.put('/api/admin/categories',json={'name':'教材书籍','active':False}).status_code==200
    main.init_db()
    assert '教材书籍' not in buyer.get('/api/categories').json()
    assert seller.post('/api/products',json=product()).status_code==422
    assert buyer.delete(f'/api/products/{pid}').status_code==403
    assert seller.delete(f'/api/products/{pid}').status_code==200
    assert buyer.get(f'/api/products/{pid}').status_code==404
    assert seller.get('/api/me/products').json()==[]


def test_legacy_database_migration_is_repeatable(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA',tmp_path)
    with sqlite3.connect(tmp_path/'market.db') as c:
        c.executescript((main.ROOT/'backend/schema.sql').read_text(encoding='utf-8'))
        c.execute("INSERT INTO users(username,nickname,password_hash) VALUES('legacy','老用户','placeholder')")
        c.execute("INSERT INTO products(owner_id,title,description,price_cents,category,image_url,contact,location,condition) VALUES(1,'旧商品','旧商品说明',500,'教材书籍','/assets/book.svg','旧联系','南门','轻微使用')")
    main.init_db();main.init_db()
    with main.db() as c:
        row=c.execute('SELECT * FROM products').fetchone()
        assert row['title']=='旧商品' and row['review_status']=='pending' and row['campus']=='主校区'
        assert c.execute('SELECT verification,role FROM users').fetchone()[:]==('unverified','student')


@pytest.mark.parametrize('count',[1,2,3])
def test_product_supports_one_to_three_images(env,count):
    admin,seller,buyer,_=env;verify(admin,seller,'MULTI001')
    data=product();data.pop('image_url');data['image_urls']=['/assets/book.svg','/assets/lamp.svg','/assets/keyboard.svg'][:count]
    response=seller.post('/api/products',json=data);assert response.status_code==201,response.text
    pid=response.json()['id']
    row=seller.get(f'/api/products/{pid}').json()
    assert row['image_urls']==data['image_urls'] and row['image_url']==data['image_urls'][0]
    assert admin.get('/api/admin/products').json()[0]['image_urls']==data['image_urls']
    admin.patch(f'/api/admin/products/{pid}',json={'status':'approved'})
    assert buyer.get(f'/api/products/{pid}').json()['image_urls']==data['image_urls']


@pytest.mark.parametrize('images',[[],['/assets/book.svg']*4,['/assets/book.svg']*2,['javascript:alert(1)']])
def test_product_image_count_duplicates_and_url_validation(env,images):
    admin,seller,_,_=env;verify(admin,seller,'MULTI002')
    data=product();data['image_urls']=images
    assert seller.post('/api/products',json=data).status_code==422


def test_proof_images_are_private_and_owned(env):
    admin,seller,buyer,_=env
    urls=proof(seller)+proof(seller)+proof(seller)
    assert seller.get(urls[0]).status_code==200
    assert seller.get(urls[0]).headers['cache-control']=='no-store'
    assert admin.get(urls[0]).status_code==200
    assert buyer.get(urls[0]).status_code==404
    with TestClient(main.app) as guest:
        assert guest.get(urls[0]).status_code==401
        assert guest.get(urls[0].replace('/api/verification-images/','/verification-images/')).status_code==404
    payload={'real_name':'测试学生','student_no':'PROOF001','college':'测试学院','image_urls':urls}
    assert buyer.post('/api/me/verification',json=payload).status_code==422
    assert seller.post('/api/me/verification',json={**payload,'image_urls':[]}).status_code==422
    assert seller.post('/api/me/verification',json={**payload,'image_urls':urls+[urls[0]]}).status_code==422
    assert seller.post('/api/me/verification',json=payload).status_code==200
    assert seller.get('/api/me/verification').json()['image_urls']==urls
    assert admin.get('/api/admin/verifications').json()[0]['image_urls']==urls


def test_order_creates_conversation_and_retains_it_after_deletion(env):
    admin,seller,buyer,outsider=env;pid=approved_product(admin,seller);verify(admin,buyer,'THREAD001')
    oid=buyer.post('/api/orders',json={'product_id':pid}).json()['id']
    chats=buyer.get('/api/conversations').json();assert len(chats)==1
    assert seller.get('/api/conversations').json()[0]['id']==chats[0]['id']
    assert outsider.post(f'/api/orders/{oid}/conversation').status_code==403
    assert buyer.post(f'/api/orders/{oid}/conversation').json()['id']==chats[0]['id']
    buyer.post(f'/api/orders/{oid}/cancel');seller.delete(f'/api/products/{pid}')
    assert seller.post(f'/api/orders/{oid}/conversation').json()['id']==chats[0]['id']
    assert buyer.post(f"/api/conversations/{chats[0]['id']}/messages",json={'content':'记录仍然保留'}).status_code==201
