import json
import pytest
from fastapi.testclient import TestClient
from backend import main


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA',tmp_path)
    main.init_db()
    with TestClient(main.app) as a,TestClient(main.app) as b,TestClient(main.app) as outsider:
        ids=[]
        for client,name in [(a,'alice'),(b,'bob'),(outsider,'outsider')]:
            r=client.post('/api/auth/register',json={'username':name,'nickname':name,'password':'Campus2026!'})
            ids.append(r.json()['id'])
        with main.db() as c:c.execute("UPDATE users SET verification='approved'")
        yield a,b,outsider,ids


def answers(*ids):
    return [{'question_id':i,'answer':'My Secret '+str(i)} for i in ids]


def setup(a,*ids):
    return a.put('/api/me/security-questions',json={'current_password':'Campus2026!','answers':answers(*ids)})


def recover(a,values=None,username='alice'):
    return a.post('/api/auth/recover',json={'username':username,'new_password':'Recovered2026!','answers':values or answers(1)})


def test_question_settings_require_password_and_one_to_three_distinct(env):
    a,b,_,_=env
    assert setup(a).status_code==422
    assert setup(a,1,1).status_code==422
    assert setup(a,4).status_code==422
    assert a.put('/api/me/security-questions',json={'current_password':'Wrong2026!','answers':answers(1)}).status_code==400
    assert a.put('/api/me/security-questions',json={'current_password':'Campus2026!','answers':[{'question_id':1,'answer':'  '}]}).status_code==422
    assert setup(a,1).status_code==200
    assert b.get('/api/me/security-questions').json()['configured']==[]


def test_answers_are_hashed_not_returned_and_settings_replace(env):
    a,_,_,ids=env
    assert setup(a,1,2,3).status_code==200
    response=a.get('/api/me/security-questions').json()
    assert response['configured']==[1,2,3] and 'secret' not in json.dumps(response).lower()
    with main.db() as c:
        hashes=[r[0] for r in c.execute('SELECT answer_hash FROM security_questions WHERE user_id=?',(ids[0],))]
        assert all('secret' not in h.lower() and ':' in h for h in hashes)
        assert len(set(hashes))==3
    assert setup(a,2).status_code==200
    assert a.get('/api/me/security-questions').json()['configured']==[2]


def test_recover_requires_all_configured_answers_and_revokes_sessions(env):
    a,b,_,_=env
    setup(a,1,2,3)
    b.post('/api/auth/login',json={'username':'alice','password':'Campus2026!'})
    assert recover(a,answers(1)).status_code==400
    assert b.get('/api/me').status_code==200
    values=[{'question_id':i,'answer':'  MY   SECRET '+str(i)+'  '} for i in [1,2,3]]
    assert recover(a,values).status_code==200
    assert a.get('/api/me').status_code==401
    assert b.get('/api/me').status_code==401
    assert a.post('/api/auth/login',json={'username':'alice','password':'Campus2026!'}).status_code==401
    assert a.post('/api/auth/login',json={'username':'alice','password':'Recovered2026!'}).status_code==200


def test_unknown_unset_and_disabled_have_same_failure(env):
    a,b,_,ids=env
    unknown=recover(a,username='missing').json()
    assert recover(a).json()==unknown
    setup(a,1)
    with main.db() as c:c.execute('UPDATE users SET disabled=1 WHERE id=?',(ids[0],))
    assert recover(b).json()==unknown
    assert len(b.get('/api/auth/recovery-questions').json()['questions'])==3


def test_recovery_attempt_limit_persists_without_locking_login(env):
    a,_,_,_=env
    setup(a,1)
    wrong=[{'question_id':1,'answer':'Incorrect'}]
    for _ in range(5):assert recover(a,wrong).status_code==400
    assert recover(a).status_code==429
    assert a.post('/api/auth/login',json={'username':'alice','password':'Campus2026!'}).status_code==200
    with main.db() as c:c.execute('UPDATE recovery_attempts SET window_start=0')
    assert recover(a).status_code==200


def test_recovery_rejects_bad_new_password_and_cross_site(env):
    a,_,_,_=env
    setup(a,1)
    assert a.post('/api/auth/recover',json={'username':'alice','new_password':'short','answers':answers(1)}).status_code==422
    assert a.post('/api/auth/recover',headers={'Origin':'https://evil.test'},json={'username':'alice','new_password':'Recovered2026!','answers':answers(1)}).status_code==403
    assert a.get('/api/me').status_code==200


def test_direct_messages_are_unique_in_both_directions_and_private(env):
    a,b,outsider,ids=env
    cid=a.post('/api/conversations',json={'peer_id':ids[1]}).json()['id']
    assert b.post('/api/conversations',json={'peer_id':ids[0]}).json()['id']==cid
    assert a.post(f'/api/conversations/{cid}/messages',json={'content':'仅给对方的私信'}).status_code==201
    row=b.get('/api/conversations').json()[0]
    assert row['source_type']=='direct' and row['peer_id']==ids[0] and row['title']=='直接私信'
    assert row['last_message']=='仅给对方的私信'
    assert outsider.get(f'/api/conversations/{cid}/messages').status_code==404
    assert a.post('/api/conversations',json={'peer_id':ids[0]}).status_code==422
    assert a.post('/api/conversations',json={'peer_id':9999}).status_code==404
    assert a.post('/api/conversations',json={'peer_id':ids[1],'product_id':1}).status_code==422


def test_message_source_types_and_latest_reply_order(env):
    a,b,_,ids=env
    p={'title':'来源商品','description':'说明完整的来源测试商品','price':10,'category':'教材书籍','image_url':'/assets/book.svg','contact':'测试联系','location':'图书馆','condition':'全新'}
    pid=a.post('/api/products',json=p).json()['id']
    with main.db() as c:c.execute("UPDATE products SET review_status='approved' WHERE id=?",(pid,))
    product_cid=b.post('/api/conversations',json={'product_id':pid}).json()['id']
    direct_cid=b.post('/api/conversations',json={'peer_id':ids[0]}).json()['id']
    assert direct_cid!=product_cid
    b.post(f'/api/conversations/{direct_cid}/messages',json={'content':'直接联系'})
    b.post(f'/api/conversations/{product_cid}/messages',json={'content':'商品来源咨询'})
    rows=a.get('/api/conversations').json()
    assert rows[0]['id']==product_cid and rows[0]['source_type']=='product'
    assert rows[0]['title']=='来源商品' and rows[0]['last_message_at']
