import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.seed_experiments import seed_experiments


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA',tmp_path)
    main.init_db()
    with TestClient(main.app) as a,TestClient(main.app) as b:
        yield a,b


def register(c,name):
    r=c.post('/api/auth/register',json={'username':name,'nickname':name,'password':'Campus2026!'})
    assert r.status_code==201
    return r.json()['id']


def payload(price):
    return dict(title='测试键盘',description='完整可用的校园键盘。',price=price,category='数码电子',image_url='/assets/keyboard.svg',contact='私聊联系',location='图书馆',condition='全新')


def test_profile_owner_validation_and_public_fields(env):
    a,b=env
    register(a,'alice');register(b,'bob')
    assert a.patch('/api/me/profile',json={'nickname':'  新昵称  ','bio':'  喜欢读书  ','role':'admin'}).status_code==200
    assert a.get('/api/me/profile').json()['nickname']=='新昵称'
    assert a.get('/api/me/profile').json()['bio']=='喜欢读书'
    assert b.get('/api/me/profile').json()['nickname']=='bob'
    assert a.get('/api/me').json()['role']=='student'
    assert a.patch('/api/me/profile',json={'nickname':'   '}).status_code==422
    assert a.patch('/api/me/profile',json={'nickname':'昵称','bio':'长'*201}).status_code==422
    a.post('/api/auth/logout')
    assert a.patch('/api/me/profile',json={'nickname':'别人'}).status_code==401


def test_password_verification_rotation_and_other_sessions(env):
    a,b=env
    register(a,'alice')
    assert b.post('/api/auth/login',json={'username':'alice','password':'Campus2026!'}).status_code==200
    before=a.cookies.get('market_session')
    assert a.post('/api/me/password',json={'current_password':'Wrong2026!','new_password':'Changed2026!'}).status_code==400
    assert b.get('/api/me').status_code==200
    assert a.post('/api/me/password',json={'current_password':'Campus2026!','new_password':'Campus2026!'}).status_code==422
    assert a.post('/api/me/password',json={'current_password':'Campus2026!','new_password':'short'}).status_code==422
    assert a.post('/api/me/password',json={'current_password':'Campus2026!','new_password':'Changed2026!'}).status_code==200
    assert a.cookies.get('market_session')!=before
    assert a.get('/api/me').status_code==200
    assert b.get('/api/me').status_code==401
    assert b.post('/api/auth/login',json={'username':'alice','password':'Campus2026!'}).status_code==401
    assert b.post('/api/auth/login',json={'username':'alice','password':'Changed2026!'}).status_code==200


def test_real_reduction_review_history_and_price_increase(env):
    a,b=env
    uid=register(a,'alice')
    with main.db() as c:c.execute("UPDATE users SET verification='approved' WHERE id=?",(uid,))
    pid=a.post('/api/products',json=payload('100')).json()['id']
    with main.db() as c:c.execute("UPDATE products SET review_status='approved' WHERE id=?",(pid,))
    assert a.put(f'/api/products/{pid}',json=payload('70')).status_code==200
    assert b.get('/api/products?reduced=true').json()['total']==0
    with main.db() as c:c.execute("UPDATE products SET review_status='approved' WHERE id=?",(pid,))
    row=b.get('/api/products?reduced=true').json()['items'][0]
    assert row['previous_price_cents']==10000 and row['price']==70
    assert 'contact' not in row and 'student_no' not in row
    assert a.put(f'/api/products/{pid}',json=payload('80')).status_code==200
    with main.db() as c:
        c.execute("UPDATE products SET review_status='approved' WHERE id=?",(pid,))
        assert c.execute('SELECT COUNT(*) FROM price_changes WHERE product_id=?',(pid,)).fetchone()[0]==2
    assert b.get('/api/products?reduced=true').json()['total']==0


def test_experimental_seed_is_labelled_and_non_destructive(env):
    a,b=env
    seed_experiments()
    items=a.get('/api/products?reduced=true').json()['items']
    assert len(items)==2 and all(p['is_demo'] and p['title'].startswith('【模拟】') for p in items)
    assert a.post('/api/auth/login',json={'username':'demo','password':'Campus2026!'}).status_code==200
    orders=a.get('/api/orders').json()
    assert {o['status'] for o in orders}=={'pending_communication','pending_trade','completed','cancelled'}
    with pytest.raises(ValueError,match='空数据库'):seed_experiments()
    assert len(a.get('/api/orders').json())==4


def test_activity_and_completed_sales_are_real_sort_metrics(env):
    a,b=env
    seed_experiments()
    recent=a.get('/api/products?sort=recent_active').json()['items']
    assert recent[0]['seller'].endswith('小林同学')
    sales=a.get('/api/products?sort=completed_sales').json()['items']
    assert sales[0]['completed_sales']==1
    assert all(r['completed_sales']<=1 for r in sales)
    a.post('/api/auth/login',json={'username':'demo','password':'Campus2026!'})
    recent=b.get('/api/products?sort=recent_active').json()['items']
    assert recent[0]['seller'].endswith('夕拾同学')
    assert not any(k in recent[0] for k in ['real_name','student_no','password_hash'])


def test_migration_is_repeatable(env):
    a,b=env
    register(a,'alice')
    main.init_db();main.init_db()
    assert a.get('/api/me/profile').json()['nickname']=='alice'
    with main.db() as c:
        assert {'last_active_at','bio','is_demo'} <= {r[1] for r in c.execute('PRAGMA table_info(users)')}
        assert {'price_reduced_at','previous_price_cents'} <= {r[1] for r in c.execute('PRAGMA table_info(products)')}
