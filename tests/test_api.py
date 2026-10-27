import io
import re
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend import main


def test_frontend_revision_changes_together_and_revalidates_cache(clients,tmp_path,monkeypatch):
    a,_=clients
    source=main.ROOT
    for name in ('index.html',*main.FRONTEND_ASSETS):
        target=tmp_path/'frontend'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((source/'frontend'/name).read_bytes())
    monkeypatch.setattr(main,'ROOT',tmp_path)
    first=a.get('/')
    assert first.headers['cache-control']=='no-store'
    versions=re.findall(r'\?v=([a-f0-9]{16})',first.text)
    assert len(versions)==len(main.FRONTEND_ASSETS) and len(set(versions))==1
    for name in main.FRONTEND_ASSETS:
        response=a.get('/'+name+'?v='+versions[0])
        assert response.status_code==200 and response.headers['cache-control']=='no-cache, must-revalidate'
    app_file=tmp_path/'frontend/app.js'
    app_file.write_bytes(app_file.read_bytes()+b'\n// updated frontend revision\n')
    second=a.get('/')
    new_versions=re.findall(r'\?v=([a-f0-9]{16})',second.text)
    assert len(set(new_versions))==1 and new_versions[0]!=versions[0]

@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setattr(main,'DATA',tmp_path)
    main.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        yield a,b

def signup(c,name='student'):
    r=c.post('/api/auth/register',json={'username':name,'password':'Campus2026!','nickname':'测试同学'})
    assert r.status_code==201
    with main.db() as db:
        db.execute("UPDATE users SET verification='approved' WHERE id=?",(r.json()['id'],))
    return r.json()

def approved_post(client, **kwargs):
    response=client.post('/api/products',**kwargs)
    if response.status_code==201:
        with main.db() as db:db.execute("UPDATE products SET review_status='approved' WHERE id=?",(response.json()['id'],))
    return response

def payload(**kw):
    return {'title':'测试高数教材','description':'保存完好的教材，含少量笔记。','price':'12.34','category':'教材书籍','image_url':'/assets/book.svg','contact':'wx:test','location':'图书馆门口','condition':'轻微使用',**kw}

def publish(c):
    r=approved_post(c,json=payload())
    assert r.status_code==201
    return r.json()['id']

def test_auth_lifecycle(clients):
    a,b=clients
    assert a.get('/api/me').status_code==401
    signup(a)
    assert a.get('/api/me').json()['username']=='student'
    assert a.post('/api/auth/register',json={'username':'student','password':'Campus2026!','nickname':'重复'}).status_code==409
    assert a.post('/api/auth/logout').status_code==200
    assert a.get('/api/me').status_code==401
    assert a.post('/api/auth/login',json={'username':'student','password':'wrongpwd'}).status_code==401
    r=a.post('/api/auth/login',json={'username':'student','password':'Campus2026!'})
    assert r.status_code==200 and 'HttpOnly' in r.headers['set-cookie']

def test_publish_permissions_and_contact_privacy(clients):
    a,b=clients
    assert b.post('/api/products',json=payload()).status_code==401
    signup(a);pid=publish(a)
    assert 'contact' not in b.get('/api/products').json()['items'][0]
    assert b.get(f'/api/products/{pid}').json()['contact']=='登录后查看联系方式'
    signup(b,'other')
    assert b.put(f'/api/products/{pid}',json=payload()).status_code==403
    assert b.patch(f'/api/products/{pid}/status',json={'status':'sold'}).status_code==403
    assert a.put(f'/api/products/{pid}',json=payload(title='修改后的教材')).status_code==200
    assert b.get(f'/api/products/{pid}').status_code==404
    assert a.get(f'/api/products/{pid}').json()['review_status']=='pending'
    assert a.get('/api/me/products').json()[0]['contact']=='wx:test'

@pytest.mark.parametrize('changes',[{'price':-1},{'price':'0.001'},{'price':'NaN'},{'price':1000000},{'category':'非法分类'},{'image_url':'javascript:alert(1)'},{'image_url':'//evil.com/x.jpg'},{'title':'  '},{'description':'x'}])
def test_validation(clients,changes):
    a,_=clients;signup(a)
    assert approved_post(a,json=payload(**changes)).status_code==422

def test_search_filter_sort_pagination(clients):
    a,b=clients;signup(a)
    publish(a)
    approved_post(a,json=payload(title='线性代数课本',price='30'))
    approved_post(a,json=payload(title='无线耳机',price='100',category='数码电子'))
    assert b.get('/api/products?q=笔记').json()['total']==3
    assert b.get('/api/products?q=高数&category=教材书籍&min_price=12&max_price=13').json()['total']==1
    assert b.get('/api/products?sort=price_desc&page_size=1&page=2').json()['items'][0]['price']==30
    assert b.get('/api/products?q=%27%20OR%201=1--').json()['total']==0
    assert b.get('/api/products?min_price=50&max_price=1').status_code==422
    assert b.get('/api/products?page=0').status_code==422
    assert b.get('/api/products?page_size=1000').status_code==422

def test_status_machine_and_visibility(clients):
    a,b=clients;signup(a);pid=publish(a);signup(b,'buyer')
    path=f'/api/products/{pid}'
    assert a.patch(path+'/status',json={'status':'off_shelf'}).status_code==200
    assert b.get('/api/products').json()['total']==0
    assert b.post(path+'/messages',json={'content':'还在吗'}).status_code==409
    assert a.patch(path+'/status',json={'status':'on_sale'}).status_code==200
    assert a.patch(path+'/status',json={'status':'sold'}).status_code==200
    assert a.patch(path+'/status',json={'status':'on_sale'}).status_code==409
    assert b.get(path).json()['status']=='sold'

def test_favorites_idempotent_and_user_isolation(clients):
    a,b=clients;signup(a);pid=publish(a);signup(b,'buyer')
    for _ in range(2):assert b.put(f'/api/products/{pid}/favorite').status_code==200
    assert len(b.get('/api/me/favorites').json())==1
    assert len(a.get('/api/me/favorites').json())==0
    for _ in range(2):assert b.delete(f'/api/products/{pid}/favorite').status_code==200
    assert b.get('/api/me/favorites').json()==[]

def test_messages_seller_replies_and_parent_validation(clients):
    a,b=clients;signup(a);pid=publish(a);signup(b,'buyer')
    path=f'/api/products/{pid}/messages'
    mid=b.post(path,json={'content':'可以便宜点吗？'}).json()['id']
    assert b.post(path,json={'content':'伪造卖家回复','parent_id':mid}).status_code==403
    assert a.post(path,json={'content':'可以面交商量','parent_id':mid}).status_code==201
    other=publish(a)
    assert a.post(f'/api/products/{other}/messages',json={'content':'跨商品回复','parent_id':mid}).status_code==422
    assert b.post(path,json={'content':'   '}).status_code==422
    assert len(b.get(path).json())==2

def test_upload_validation(clients):
    a,b=clients
    assert b.post('/api/uploads',files={'file':('x.png',b'fake','image/png')}).status_code==401
    signup(a)
    assert a.post('/api/uploads',files={'file':('x.png',b'fake','image/png')}).status_code==422
    assert a.post('/api/uploads',files={'file':('x.svg',b'<svg/>','image/svg+xml')}).status_code==422
    assert a.post('/api/uploads',files={'file':('big.jpg',b'x'*(5*1024*1024+1),'image/jpeg')}).status_code==413
    image=io.BytesIO();Image.new('RGB',(20,20)).save(image,'PNG')
    r=a.post('/api/uploads',files={'file':('../../x.png',image.getvalue(),'image/png')})
    assert r.status_code==201 and r.json()['url'].endswith('.jpg')
    assert '..' not in r.json()['url']

def test_cross_origin_and_static_isolation(clients):
    a,b=clients;signup(a)
    assert approved_post(a,json=payload(),headers={'Origin':'https://evil.test'}).status_code==403
    for path in ['/data/market.db','/backend/main.py','/.env']:
        assert b.get(path).status_code==404
    assert b.get('/').status_code==200
    assert b.get('/api/health').json()['status']=='ok'
    assert b.get('/api/products/9999').status_code==404
    assert 'password_hash' not in a.get('/api/me').text

def test_expired_session(clients):
    a,b=clients;signup(a)
    with main.db() as c:c.execute('UPDATE sessions SET expires_at=0')
    assert a.get('/api/me').status_code==401

def test_money_precision(clients):
    a,b=clients;signup(a)
    pid=approved_post(a,json=payload(price='0.29')).json()['id']
    assert b.get(f'/api/products/{pid}').json()['price']==0.29
    with main.db() as c:assert c.execute('SELECT price_cents FROM products WHERE id=?',(pid,)).fetchone()[0]==29

def test_relevance_is_default_and_can_switch_to_price_or_newest(clients):
    a,b=clients;signup(a)
    titles=['键盘','键盘机械版','无线键盘','桌面配件']
    for i,title in enumerate(titles):
        assert approved_post(a,json=payload(title=title,description='这是一款键盘商品，保存完好。',price=str(40-i*10))).status_code==201
    assert [p['title'] for p in b.get('/api/products?q=键盘').json()['items']]==titles
    assert b.get('/api/products?q=键盘&sort=newest').json()['items'][0]['title']=='桌面配件'
    assert [p['price'] for p in b.get('/api/products?q=键盘&sort=price_asc').json()['items']]==[10,20,30,40]
    assert [p['price'] for p in b.get('/api/products?q=键盘&sort=price_desc').json()['items']]==[40,30,20,10]

def test_search_multiple_terms_and_stable_pagination(clients):
    a,b=clients;signup(a)
    for title,description in [('无线键盘','机械键盘，适合学习使用。'),('键盘机械款','有线连接，适合学习使用。'),('无线耳机','保存完好的无线耳机。')]:
        approved_post(a,json=payload(title=title,description=description))
    r=b.get('/api/products',params={'q':'  键盘   无线 '}).json()
    assert r['total']==1 and r['items'][0]['title']=='无线键盘'
    first=b.get('/api/products?q=键盘&page_size=1&page=1').json()['items'][0]['id']
    second=b.get('/api/products?q=键盘&page_size=1&page=2').json()['items'][0]['id']
    assert first!=second

def test_condition_and_published_within_combined(clients):
    a,b=clients;signup(a)
    new=approved_post(a,json=payload(condition='全新',price='25')).json()['id']
    old=approved_post(a,json=payload(condition='全新',price='30')).json()['id']
    used=publish(a)
    with main.db() as c:
        c.execute("UPDATE products SET created_at=datetime('now','-8 days') WHERE id=?",(old,))
    r=b.get('/api/products',params={'condition':'全新','published_within':7,'category':'教材书籍','min_price':20,'max_price':40}).json()
    assert [p['id'] for p in r['items']]==[new]
    assert b.get('/api/products?condition=全新&published_within=14').json()['total']==2
    assert b.get('/api/products?published_within=1').json()['total']==2


def test_multiple_categories_and_conditions_use_or_within_and_between(clients):
    a,b=clients;signup(a)
    book=approved_post(a,json=payload(category='教材书籍',condition='全新',price=20)).json()['id']
    device=approved_post(a,json=payload(category='数码电子',condition='几乎全新',price=30)).json()['id']
    approved_post(a,json=payload(category='生活日用',condition='全新',price=25))
    approved_post(a,json=payload(category='教材书籍',condition='正常使用',price=15))
    params=[('category','教材书籍'),('category','数码电子'),('condition','全新'),('condition','几乎全新')]
    result=b.get('/api/products',params=params).json()
    assert {p['id'] for p in result['items']}=={book,device} and result['total']==2
    result=b.get('/api/products',params=params+[('min_price',25),('sort','price_desc')]).json()
    assert [p['id'] for p in result['items']]==[device]


def test_multiple_filters_deduplicate_and_keep_single_value_compatibility(clients):
    a,b=clients;signup(a);publish(a)
    one=b.get('/api/products?category=教材书籍&condition=轻微使用').json()
    repeated=b.get('/api/products',params=[('category',''),('category','教材书籍'),('category','教材书籍'),('condition','轻微使用'),('condition','轻微使用')]).json()
    assert one==repeated and one['total']==1
    assert b.get('/api/products?category=').json()['total']==1
    assert b.get('/api/products',params=[('condition','全新'),('condition','损坏')]).status_code==422


def test_multiple_filters_preserve_review_privacy_and_pagination(clients):
    a,b=clients;signup(a)
    for category in ['教材书籍','数码电子']:
        approved_post(a,json=payload(category=category,condition='全新'))
    a.post('/api/products',json=payload(category='教材书籍',condition='全新'))
    params=[('category','教材书籍'),('category','数码电子'),('condition','全新'),('page_size',1)]
    first=b.get('/api/products',params=params).json()
    second=b.get('/api/products',params=params+[('page',2)]).json()
    assert first['total']==second['total']==2
    assert first['items'][0]['id']!=second['items'][0]['id']
    assert 'contact' not in first['items'][0]

@pytest.mark.parametrize('query',['condition=损坏','published_within=2','published_within=0','published_within=15','published_within=abc','min_price=NaN','max_price=Infinity','min_price=0.001'])
def test_search_filter_validation(clients,query):
    _,b=clients
    assert b.get('/api/products?'+query).status_code==422

def test_guest_history_isolated_deduplicated_and_capped(clients):
    a,b=clients
    response=a.get('/api/search/history')
    assert response.json()=={'items':[],'scope':'device'}
    assert 'HttpOnly' in response.headers['set-cookie']
    for i in range(15):
        assert a.post('/api/search/history',json={'keyword':f'搜索 {i}'}).status_code==200
    assert len(a.get('/api/search/history').json()['items'])==12
    assert a.get('/api/search/history').json()['items'][0]=='搜索 14'
    assert b.get('/api/search/history').json()['items']==[]
    a.post('/api/search/history',json={'keyword':'  搜索    4  '})
    assert a.get('/api/search/history').json()['items'][0]=='搜索 4'
    assert len(a.get('/api/search/history').json()['items'])==12
    a.delete('/api/search/history',params={'keyword':'搜索 4'})
    assert '搜索 4' not in a.get('/api/search/history').json()['items']
    a.delete('/api/search/history')
    assert a.get('/api/search/history').json()['items']==[]

def test_guest_and_account_search_history_never_mix(clients):
    a,b=clients
    a.post('/api/search/history',json={'keyword':'游客记录'})
    signup(a)
    assert a.get('/api/search/history').json()=={'items':[],'scope':'account'}
    a.post('/api/search/history',json={'keyword':'我的键盘'})
    signup(b,'other')
    assert b.get('/api/search/history').json()['items']==[]
    b.delete('/api/search/history')
    assert a.get('/api/search/history').json()['items']==['我的键盘']
    a.post('/api/auth/logout')
    assert a.get('/api/search/history').json()['items']==['游客记录']
    b.post('/api/auth/login',json={'username':'student','password':'Campus2026!'})
    assert b.get('/api/search/history').json()['items']==['我的键盘']

@pytest.mark.parametrize('word',['','   ','x'*101])
def test_history_keyword_validation(clients,word):
    a,_=clients
    assert a.post('/api/search/history',json={'keyword':word}).status_code==422

def test_history_cookie_persists_across_database_reinitialization(clients):
    a,_=clients
    a.post('/api/search/history',json={'keyword':'校园教材'})
    main.init_db()
    assert a.get('/api/search/history').json()['items']==['校园教材']

def test_suggestions_only_come_from_on_sale_titles(clients):
    a,b=clients;signup(a)
    pid=approved_post(a,json=payload(title='无线机械键盘')).json()['id']
    hidden=approved_post(a,json=payload(title='已售古董相机')).json()['id']
    a.patch(f'/api/products/{hidden}/status',json={'status':'sold'})
    suggestions=b.get('/api/search/suggestions').json()['items']
    assert '键盘' in suggestions and '相机' not in suggestions and '已售古董相机' not in suggestions
    assert b.get('/api/search/suggestions?q=无线').json()['items']==['无线机械键盘']
    assert b.get('/api/search/suggestions?q=%27%20OR%201=1--').json()['items']==[]
    a.patch(f'/api/products/{pid}/status',json={'status':'off_shelf'})
    assert b.get('/api/search/suggestions').json()['items']==[]
    assert b.get('/api/search/suggestions?limit=25').status_code==422


def test_explicit_cloud_preview_origin_without_allowing_other_sites(clients,monkeypatch):
    a,b=clients
    monkeypatch.setenv('MARKET_PUBLIC_ORIGIN','https://preview.example.test')
    data={'username':'cloudstudent','password':'Campus2026!','nickname':'云端测试'}
    assert a.post('/api/auth/register',json=data,headers={'Origin':'https://preview.example.test'}).status_code==201
    assert a.get('/api/me').status_code==200
    assert a.post('/api/auth/logout',headers={'Origin':'https://evil.example.test'}).status_code==403
    assert a.get('/api/me').status_code==200
    assert a.post('/api/auth/logout',headers={'Origin':'https://preview.example.test'}).status_code==200
    assert a.get('/api/me').status_code==401


@pytest.mark.parametrize('value',['http://preview.example.test','https://user:pass@preview.example.test','https://preview.example.test/path','https://preview.example.test/?query=1'])
def test_public_origin_rejects_unsafe_configuration(monkeypatch,value):
    monkeypatch.setenv('MARKET_PUBLIC_ORIGIN',value)
    with pytest.raises(ValueError):main.public_origin()


def test_https_deployment_sets_secure_cookie(clients,monkeypatch):
    a,_=clients
    monkeypatch.setenv('COOKIE_SECURE','1')
    response=a.post('/api/auth/register',json={'username':'securestudent','password':'Campus2026!','nickname':'HTTPS 测试'})
    assert response.status_code==201
    cookie=response.headers['set-cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=lax' in cookie


def test_http_session_and_admin_navigation(clients,monkeypatch):
    a,_=clients
    monkeypatch.setenv('COOKIE_SECURE','0')
    from backend.create_admin import create_admin
    create_admin('http_admin','HttpAdmin2026!')
    login=a.post('/api/auth/login',json={'username':'http_admin','password':'HttpAdmin2026!'})
    assert login.status_code==200
    assert 'Secure' not in login.headers['set-cookie']
    for page in ['/api/me','/api/me/profile','/api/orders','/api/conversations','/api/admin/overview','/api/admin/verifications']:
        assert a.get(page).status_code==200,page
    assert a.get('/api/me').json()['role']=='admin'
    with main.db() as c:
        stored=c.execute("SELECT password_hash FROM users WHERE username='http_admin'").fetchone()[0]
    assert stored!='HttpAdmin2026!'
    with pytest.raises(ValueError):
        create_admin('http_admin','Different2026!')
    a.post('/api/auth/logout')
    assert a.get('/api/admin/overview').status_code==401


def test_secure_cookie_does_not_authenticate_plain_http(clients,monkeypatch):
    a,_=clients
    monkeypatch.setenv('COOKIE_SECURE','1')
    signup(a,'http_rejected_cookie')
    assert a.get('/api/me').status_code==401
