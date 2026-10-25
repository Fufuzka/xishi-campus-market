"""显式初始化演示数据；生产环境不要运行。"""
from backend.main import init_db, db, hash_password

def seed():
    init_db()
    with db() as c:
        if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            print('已有用户，跳过演示数据，避免修改现有数据。')
            return
        uid=c.execute('INSERT INTO users(username,nickname,password_hash) VALUES(?,?,?)',('demo','夕拾同学',hash_password('Campus2026!'))).lastrowid
        uid2=c.execute('INSERT INTO users(username,nickname,password_hash) VALUES(?,?,?)',('buyer','小林同学',hash_password('Campus2026!'))).lastrowid
        c.execute("UPDATE users SET verification='approved',real_name='演示学生',student_no=printf('DEMO%04d',id),college='演示学院'")
        rows=[('高等数学 · 同济第七版','教材书籍',18,'book','图书馆南门','轻微使用'),('无线降噪耳机，学习好搭子','数码电子',159,'headphones','一号教学楼','几乎全新'),('暖光护眼台灯','生活日用',35,'lamp','东区宿舍','轻微使用'),('轻便运动鞋 · 42 码','运动户外',68,'shoes','体育馆门口','几乎全新'),('复古数码相机，记录校园日常','数码电子',299,'camera','学生活动中心','正常使用'),('简约帆布包 · 奶油色','服饰配件',22,'bag','西区食堂','全新'),('无线键盘，安静码字','数码电子',89,'keyboard','图书馆南门','轻微使用'),('宿舍绿植 · 一点小小的绿意','其他好物',12,'plant','东区宿舍','几乎全新')]
        for i,(title,category,price,image,location,condition) in enumerate(rows):
            c.execute('INSERT INTO products(owner_id,title,description,price_cents,category,image_url,contact,location,condition) VALUES(?,?,?,?,?,?,?,?,?)',(uid if i%2==0 else uid2,title,'【演示商品】物品保存完好，细节可留言询问。毕业整理闲置，希望转给需要的同学。支持校园当面检查后交易，图片为项目自有示意插画。',price*100,category,f'/assets/{image}.svg','演示联系方式，请勿用于真实交易',location,condition))
        c.execute("UPDATE products SET review_status='approved'")
        c.execute('INSERT INTO messages(product_id,user_id,content) VALUES(?,?,?)',(1,uid2,'请问教材有很多笔记吗？可以在图书馆面交吗？'))
        c.execute('INSERT INTO messages(product_id,user_id,content,parent_id) VALUES(?,?,?,?)',(1,uid,'有少量铅笔笔记，可以图书馆南门面交。',1))
        c.execute('INSERT INTO favorites(user_id,product_id) VALUES(?,?)',(uid,2))
    print('演示数据就绪。账号 demo / buyer；密码 Campus2026!。仅供本地功能验证。')

if __name__=='__main__':
    seed()
