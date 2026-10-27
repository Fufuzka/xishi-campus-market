// Session state regressions without browser credentials or production writes.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
let definition;
let fetcher;
const pending=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve}};
const response=(status,data)=>({status,ok:status>=200&&status<300,json:async()=>data});
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/app.js'),'utf8'),{
 Vue:{createApp(value){definition=value;return{mount(){}}}},campusFeatures:{},experienceFeatures:{},
 fetch:(...args)=>fetcher(...args),AbortController,FormData,setTimeout,clearTimeout,URLSearchParams,
 document:{addEventListener(){}},window:{}
});
function client(){const c=definition.data();for(const [k,m] of Object.entries(definition.methods))c[k]=m.bind(c);c.messages=[];c.notify=t=>c.messages.push(t);c.load=async()=>{};c.ensureHistory=async()=>{};c.loadRecommendations=async()=>{};return c}
const account={id:1,username:'session_test',nickname:'会话验收',role:'student'};
const checks=[];
async function check(name,fn){await fn();checks.push(name)}
(async()=>{
 await check('Login is published only after the session round trip',async()=>{
  const c=client(),verify=pending();c.authOpen=true;
  fetcher=async(url,options)=>{assert.equal(options.credentials,'same-origin');return url.includes('/auth/')?response(200,account):verify.promise};
  const login=c.authenticate();await Promise.resolve();await Promise.resolve();await Promise.resolve();
  assert.equal(c.user,null);assert.equal(c.authOpen,true);
  verify.resolve(response(200,account));await login;
  assert.equal(c.user.id,1);assert.equal(c.authOpen,false);assert.ok(c.messages.some(x=>x.startsWith('欢迎')))
 });
 await check('Rejected Cookie keeps login open with an actionable error',async()=>{
  const c=client();c.authOpen=true;c.auth.password='temporary';
  fetcher=async url=>url.includes('/auth/')?response(200,account):response(401,{detail:'请先登录'});
  await c.authenticate();assert.equal(c.user,null);assert.equal(c.authOpen,true);assert.equal(c.auth.password,'');assert.ok(c.messages.at(-1).includes('Cookie'));assert.ok(!c.messages.some(x=>x.startsWith('欢迎')))
 });
 await check('Wrong password retains its own error',async()=>{
  const c=client();fetcher=async()=>response(401,{detail:'用户名或密码错误'});
  await c.authenticate();assert.equal(c.messages.at(-1),'用户名或密码错误')
 });
 await check('Delayed old 401 cannot erase a newer login',async()=>{
  const c=client(),old=pending();fetcher=()=>old.promise;
  const request=c.api('/api/me').catch(e=>e);c.authRevision++;c.user=account;
  old.resolve(response(401,{detail:'请先登录'}));assert.equal((await request).status,401);assert.equal(c.user.id,1)
 });
 await check('Initial page probe cannot overwrite a completed login',async()=>{
  const c=client(),old=pending(),started=pending();fetcher=async url=>{if(url==='/api/categories')return response(200,[]);started.resolve();return old.promise};
  const mount=definition.mounted.call(c);await started.promise;
  c.authRevision++;c.user=account;old.resolve(response(401,{detail:'请先登录'}));await mount;assert.equal(c.user.id,1)
 });
 await check('A request sent during login cannot invalidate the confirmed session',async()=>{
  const c=client(),loginResponse=pending(),started=pending(),old=pending();
  fetcher=async url=>{if(url.includes('/auth/')){started.resolve();return loginResponse.promise}return url==='/api/me'?response(200,account):old.promise};
  const login=c.authenticate();await started.promise;const request=c.api('/api/orders').catch(e=>e);
  loginResponse.resolve(response(200,account));await login;old.resolve(response(401,{detail:'请先登录'}));await request;
  assert.equal(c.user.id,1)
 });
 await check('Current session expiry still clears the logged in state',async()=>{
  const c=client();c.user=account;fetcher=async()=>response(401,{detail:'请先登录'});
  await assert.rejects(c.api('/api/orders'));assert.equal(c.user,null)
 });
 await check('Unexpected account identity is not accepted',async()=>{
  const c=client();fetcher=async url=>response(200,url.includes('/auth/')?account:{...account,id:2});
  await c.authenticate();assert.equal(c.user,null);assert.ok(c.messages.at(-1).includes('不一致'))
 });
 await check('Session verification network failure is not success',async()=>{
  const c=client();fetcher=async url=>{if(url.includes('/auth/'))return response(200,account);throw Error('offline')};
  await c.authenticate();assert.equal(c.user,null);assert.ok(!c.messages.some(x=>x.startsWith('欢迎')))
 });
 console.log(JSON.stringify({passed:checks.length,checks},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
