"""仅向空数据库导入明确标注的模拟数据：python -m backend.seed_experiments。"""
from backend.main import init_db, db
from backend.seed import seed


def seed_experiments():
    init_db()
    with db() as c:
        if c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            raise ValueError('实验数据仅允许导入空数据库。请设置新的 MARKET_DATA_DIR，不会修改已有账号或交易。')
    seed()
    with db() as c:
        c.execute("UPDATE users SET is_demo=1,bio='【模拟资料】仅用于功能演示，不是真实交易记录。',nickname='模拟 · '||nickname")
        c.execute("UPDATE users SET last_active_at=datetime('now','-2 days') WHERE username='demo'")
        c.execute("UPDATE users SET last_active_at=datetime('now','-2 hours') WHERE username='buyer'")
        c.execute("UPDATE products SET title='【模拟】'||title")
        users={r['username']:r['id'] for r in c.execute('SELECT id,username FROM users')}
        products=c.execute('SELECT * FROM products ORDER BY id').fetchall()
        for row,status in zip(products[::2],['pending_communication','pending_trade','completed','cancelled']):
            complete=status=='completed'
            c.execute('INSERT INTO orders(product_id,buyer_id,seller_id,price_cents,title,status,meeting_place,meeting_time,buyer_confirmed,seller_confirmed) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (row['id'],users['buyer'],users['demo'],row['price_cents'],row['title'],status,'模拟：图书馆南门' if status=='pending_trade' else '', '2030-01-01T14:00' if status=='pending_trade' else '',int(complete),int(complete)))
            c.execute('INSERT INTO conversations(starter_id,recipient_id,product_id) VALUES(?,?,?)',(users['buyer'],users['demo'],row['id']))
            if complete:
                c.execute("UPDATE products SET status='sold' WHERE id=?",(row['id'],))
        for row in products[1::2][:2]:
            old=row['price_cents']+2000
            c.execute('INSERT INTO price_changes(product_id,old_price_cents,new_price_cents) VALUES(?,?,?)',(row['id'],old,row['price_cents']))
            c.execute('UPDATE products SET previous_price_cents=?,price_reduced_at=CURRENT_TIMESTAMP WHERE id=?',(old,row['id']))
    print('模拟降价、活动时间与四种交易状态已导入。账号 demo / buyer，密码 Campus2026!；不得用于真实交易。')


if __name__=='__main__':
    seed_experiments()
