const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage();const steps=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.BASE_URL||'http://127.0.0.1:8007';
 const button=name=>page.getByRole('button',{name,exact:true});
 const check=async(name,fn)=>{await fn();steps.push({name,result:'PASS'})};
 const open=()=>button('登录 / 注册').click();
 const fill=async()=>{await page.getByLabel('用户名',{exact:true}).fill('partial_user');await page.getByLabel('密码',{exact:true}).fill('PartialPassword!')};
 const empty=async()=>{if(await page.getByLabel('用户名',{exact:true}).inputValue()||await page.getByLabel('密码',{exact:true}).inputValue())throw Error('关闭后输入仍残留');if(await page.getByLabel('密码',{exact:true}).getAttribute('type')!=='password')throw Error('密码可见状态残留')};
 try{
 await page.goto(base);await page.locator('.product-card').first().waitFor();
 await check('关闭按钮清空用户名密码并复位密码可见性',async()=>{await open();await fill();await button('显示密码').click();await button('关闭').click();await open();await empty()});
 await check('Escape 不关闭，点击叉后清空输入',async()=>{await fill();await page.keyboard.press('Escape');if(!await page.getByRole('dialog',{name:'登录注册'}).isVisible())throw Error('Escape 关闭了登录');await button('关闭').click();await open();await empty()});
 await check('点击遮罩不关闭，点击叉后清空输入',async()=>{await fill();await page.locator('.auth-overlay').click({position:{x:5,y:5}});if(!await page.getByRole('dialog',{name:'登录注册'}).isVisible())throw Error('遮罩关闭了登录');await button('关闭').click();await open();await empty()});
 await check('退出注册后清空昵称并返回空白登录表单',async()=>{await button('还没有账号？注册一个').click();await fill();await page.getByLabel('昵称',{exact:true}).fill('未提交昵称');await button('关闭').click();await open();await empty();await button('登录').waitFor();await button('还没有账号？注册一个').click();if(await page.getByLabel('昵称',{exact:true}).inputValue())throw Error('昵称残留');await button('关闭').click()});
 await check('网络断开显示中文提示且允许重试',async()=>{await open();await page.getByLabel('用户名',{exact:true}).fill('demo');await page.getByLabel('密码',{exact:true}).fill('Campus2026!');await page.route('**/api/auth/login',route=>route.abort('connectionfailed'));await button('登录').click();await page.getByRole('status').filter({hasText:'无法连接服务，请检查网络'}).waitFor();if(await button('登录').isDisabled())throw Error('失败后登录按钮仍被禁用');await page.unroute('**/api/auth/login')});
 await check('服务恢复可登录且退出后登录表单为空',async()=>{await button('登录').click();await page.locator('.account').getByText('夕拾同学',{exact:true}).waitFor();await button('退出').click();await open();await empty();await button('关闭').click()});
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync(path.resolve(__dirname,'../evidence/auth-browser-results.json'),JSON.stringify({status:'PASS',steps,pageErrors:errors},null,2));console.log(JSON.stringify({status:'PASS',checks:steps.length}));
 }finally{await browser.close()}
})();
