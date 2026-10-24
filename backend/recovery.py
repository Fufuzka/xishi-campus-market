"""测试版安全问题设置与密码找回；答案仅保存带盐摘要。"""
import hashlib
import time
import unicodedata
from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator

QUESTIONS = [
    {'id':1,'text':'你童年最喜欢的虚构角色是什么？'},
    {'id':2,'text':'你最难忘的一位老师叫什么？'},
    {'id':3,'text':'一个只有你记得的特别地点叫什么？'},
]


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


class Answer(BaseModel):
    question_id: int = Field(ge=1,le=3)
    answer: str = Field(min_length=2,max_length=128)

    @field_validator('answer')
    @classmethod
    def valid_answer(cls,value):
        value=normalize(value)
        if len(value)<2:raise ValueError('答案至少需要两个字符')
        return value


class Answers(BaseModel):
    answers: list[Answer] = Field(min_length=1,max_length=3)

    @model_validator(mode='after')
    def distinct(self):
        if len({x.question_id for x in self.answers})!=len(self.answers):
            raise ValueError('安全问题不能重复')
        return self


class Settings(Answers):
    current_password: str = Field(min_length=8,max_length=128)


class Recovery(Answers):
    username: str = Field(min_length=3,max_length=30,pattern=r'^[A-Za-z0-9_]+$')
    new_password: str = Field(min_length=8,max_length=128)


def install(app,b):
    @app.get('/api/auth/recovery-questions',tags=['找回密码'])
    def questions():
        # 所有人看到同一组问题，不公开某个账号是否存在或已配置哪些问题。
        return {'questions':QUESTIONS}

    @app.get('/api/me/security-questions',tags=['个人中心'])
    def settings(user=Depends(b.current_user)):
        with b.db() as c:
            configured=[r[0] for r in c.execute('SELECT question_id FROM security_questions WHERE user_id=? ORDER BY question_id',(user['id'],))]
        return {'questions':QUESTIONS,'configured':configured}

    @app.put('/api/me/security-questions',tags=['个人中心'])
    def save(p:Settings,user=Depends(b.current_user)):
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            stored=c.execute('SELECT password_hash FROM users WHERE id=?',(user['id'],)).fetchone()[0]
            if not b.verify_password(p.current_password,stored):raise HTTPException(400,'当前密码不正确')
            c.execute('DELETE FROM security_questions WHERE user_id=?',(user['id'],))
            c.executemany('INSERT INTO security_questions VALUES(?,?,?)',[(user['id'],a.question_id,b.hash_password(a.answer)) for a in p.answers])
        return {'ok':True,'configured':[a.question_id for a in p.answers]}

    @app.post('/api/auth/recover',tags=['找回密码'])
    def recover(p:Recovery,request:Request,response:Response):
        now=int(time.time())
        peer=request.client.host if request.client else 'unknown'
        limits=[('account:'+p.username,5),('ip:'+peer,20)]
        blocked=False
        # 先提交尝试次数，后续校验失败不能通过回滚清除限流记录。
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM recovery_attempts WHERE window_start<=?',(now-900,))
            keys=[(hashlib.sha256(key.encode()).hexdigest(),limit) for key,limit in limits]
            for key,limit in keys:
                row=c.execute('SELECT attempts FROM recovery_attempts WHERE key=?',(key,)).fetchone()
                if row and row[0]>=limit:blocked=True
            if not blocked:
                for key,_ in keys:
                    c.execute('INSERT INTO recovery_attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1',(key,now))
        if blocked:raise HTTPException(429,'尝试过于频繁，请 15 分钟后再试；正常登录仍可使用')
        with b.db() as c:
            c.execute('BEGIN IMMEDIATE')
            user=c.execute('SELECT id,disabled FROM users WHERE username=?',(p.username,)).fetchone()
            stored={r['question_id']:r['answer_hash'] for r in c.execute('SELECT question_id,answer_hash FROM security_questions WHERE user_id=?',(user['id'] if user else -1,))}
            supplied={a.question_id:a.answer for a in p.answers}
            valid=bool(user and not user['disabled'] and stored)
            # 始终执行三次摘要校验，缺失问题使用占位摘要；不暴露哪个答案错误。
            dummy='0'*32+':'+'0'*64
            for q in QUESTIONS:
                correct=b.verify_password(supplied.get(q['id'],''),stored.get(q['id'],dummy))
                if q['id'] in stored and not correct:valid=False
            if not valid:raise HTTPException(400,'无法找回，请确认账号并正确回答所有已设置的问题；未设置安全问题的账号需联系管理员')
            c.execute('UPDATE users SET password_hash=? WHERE id=?',(b.hash_password(p.new_password),user['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        response.delete_cookie('market_session')
        return {'ok':True}
