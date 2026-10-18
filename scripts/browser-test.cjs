// 可选浏览器验收：npm install playwright；本机需安装 Edge。
const { chromium } = require('playwright');
const fs=require('fs');
const path=require('path');
(async()=>{
 const out=path.resolve(__dirname,'../evidence');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
 const failures=[];const steps=[];
 page.on('pageerror',e=>failures.push(e.message));
 const check=async(name,fn)=>{await fn();steps.push({name,result:'PASS'});};
 const shot=async(name)=>{for(let attempt=0;attempt<3;attempt++){try{return await page.screenshot({path:path.join(out,name+'.png'),fullPage:true})}catch(e){if(attempt===2)throw e;await page.waitForTimeout(300)}}};
 const base=process.env.BASE_URL||'http://127.0.0.1:8000';
 try{
 await page.goto(base);await page.getByText('高等数学 · 同济第七版',{exact:true}).waitFor();
 await shot('01-home');
 await check('密码显示隐藏与重新打开复位',async()=>{await page.getByRole('button',{name:'登录 / 注册',exact:true}).click();const password=page.getByLabel('密码',{exact:true});if(await password.getAttribute('type')!=='password')throw Error('默认密码未隐藏');await password.fill('ExampleOnly8!');await page.getByRole('button',{name:'显示密码',exact:true}).click();if(await password.getAttribute('type')!=='text'||await password.inputValue()!=='ExampleOnly8!')throw Error('密码可见切换失败');await shot('09-password-visibility');await page.getByRole('button',{name:'隐藏密码',exact:true}).click();if(await password.getAttribute('type')!=='password')throw Error('隐藏失败');await page.getByRole('button',{name:'显示密码',exact:true}).click();await page.getByRole('button',{name:'关闭',exact:true}).click();await page.getByRole('button',{name:'登录 / 注册',exact:true}).click();if(await password.getAttribute('type')!=='password')throw Error('重开未复位');await page.getByRole('button',{name:'还没有账号？注册一个'}).click();await page.getByRole('button',{name:'显示密码',exact:true}).click();if(await password.getAttribute('type')!=='text')throw Error('注册不支持查看');await page.getByRole('button',{name:'已有账号？去登录'}).click();if(await password.getAttribute('type')!=='password')throw Error('模式切换未复位');await page.getByRole('button',{name:'关闭',exact:true}).click()});
 await check('应用侧栏与帮助入口',async()=>{const box=await page.locator('.sidebar').boundingBox();if(box.width<150||box.x!==0)throw Error('固定侧栏布局无效');await page.getByRole('button',{name:'使用帮助',exact:true}).click();await page.getByRole('heading',{name:'欢迎使用夕拾',exact:true}).waitFor();await page.getByRole('button',{name:'关闭',exact:true}).click();await page.getByRole('button',{name:'连接设置',exact:true}).click();await page.getByRole('heading',{name:'连接与数据',exact:true}).waitFor();await page.getByRole('button',{name:'关闭',exact:true}).click()});

 await check('关键词与价格筛选',async()=>{await page.getByLabel('搜索商品',{exact:true}).fill('高等数学');await page.getByRole('button',{name:'搜索',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.product-card').length===1);await page.getByLabel('最高价').fill('10');await page.getByRole('button',{name:'确定',exact:true}).click();await page.getByText('还没找到合适的好物').waitFor();await page.getByRole('button',{name:'清除筛选'}).click();await page.getByText('高等数学 · 同济第七版',{exact:true}).waitFor()});
 await page.getByRole('button',{name:'高等数学 · 同济第七版',exact:true}).click();await page.getByText('登录后查看联系方式').waitFor();await shot('02-product-detail');
 await page.getByRole('button',{name:'关闭',exact:true}).click();
 const username='ui_'+Date.now();
 await check('注册与登录状态',async()=>{await page.getByRole('button',{name:'登录 / 注册'}).click();await page.getByRole('button',{name:'还没有账号？注册一个'}).click();await page.getByLabel('用户名',{exact:true}).fill(username);await page.getByLabel('昵称',{exact:true}).fill('验收同学');await page.getByLabel('密码',{exact:true}).fill('Campus2026!');await page.getByRole('button',{name:'注册并登录',exact:true}).click();await page.locator('.account').getByText('验收同学',{exact:true}).waitFor()});
 await page.getByRole('button',{name:'＋ 发布闲置',exact:true}).click();
 await page.getByLabel('商品标题',{exact:true}).fill('验收用校园背包');await page.getByLabel('价格（元）',{exact:true}).fill('25.50');await page.getByLabel('商品描述',{exact:true}).fill('这是自动化验收商品，检查发布、上传、编辑和状态流转。');await page.getByLabel('交易地点',{exact:true}).fill('图书馆南门');await page.getByLabel('联系方式',{exact:true}).fill('验收联系方式');
 await page.locator('input[type=file]').setInputFiles({name:'bag.png',mimeType:'image/png',buffer:fs.readFileSync(path.join(out,'upload-fixture.png'))});await page.locator('.upload-box img').waitFor();await page.getByText('图片已上传',{exact:true}).waitFor();await shot('03-publish-form');
 await check('图片上传与商品发布',async()=>{await page.getByRole('button',{name:'发布好物',exact:true}).click();await page.getByRole('heading',{name:'我的发布',exact:true}).waitFor();await page.getByRole('button',{name:'验收用校园背包',exact:true}).waitFor()});await shot('04-my-products');
 await check('商品编辑',async()=>{await page.getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('价格（元）',{exact:true}).fill('20.29');await page.getByRole('button',{name:'保存修改',exact:true}).click();await page.locator('.price-row strong').filter({hasText:'20.29'}).waitFor()});
 await check('商品下架与重新上架',async()=>{await page.getByRole('button',{name:'下架',exact:true}).click();await page.locator('.status-label').filter({hasText:'已下架'}).waitFor();await page.getByRole('button',{name:'上架',exact:true}).click();await page.getByRole('button',{name:'下架',exact:true}).waitFor()});
 await page.getByRole('button',{name:'逛集市',exact:true}).click();await page.getByRole('button',{name:'高等数学 · 同济第七版',exact:true}).waitFor();
 await page.getByRole('button',{name:'高等数学 · 同济第七版',exact:true}).click();
 await check('收藏商品',async()=>{await page.getByRole('button',{name:'♡ 收藏好物',exact:true}).click();await page.getByRole('button',{name:'♥ 已收藏',exact:true}).waitFor()});
 await check('买家留言',async()=>{await page.getByLabel('留言内容',{exact:true}).fill('自动化验收：周末可以面交吗？');await page.getByRole('button',{name:'发送留言',exact:true}).click();await page.getByText('自动化验收：周末可以面交吗？',{exact:true}).last().waitFor()});await shot('05-message-and-favorite');
 await page.getByRole('button',{name:'关闭',exact:true}).click();await page.getByRole('button',{name:'我的收藏',exact:true}).click();await page.getByRole('heading',{name:'我的收藏',exact:true}).waitFor();await page.getByRole('button',{name:'高等数学 · 同济第七版',exact:true}).waitFor();await shot('06-favorites');
 await check('取消收藏',async()=>{await page.getByRole('button',{name:'取消收藏',exact:true}).click();await page.getByText('这里还没有商品').waitFor()});
 await page.getByRole('button',{name:'我的发布',exact:true}).click();await page.getByRole('button',{name:'标记售出',exact:true}).click();await page.getByRole('button',{name:'确认售出',exact:true}).click();await page.locator('.status-label').filter({hasText:'已售出'}).waitFor();steps.push({name:'售出确认与状态更新',result:'PASS'});
 await page.getByRole('button',{name:'退出',exact:true}).click();await page.getByRole('button',{name:'登录 / 注册'}).click();await page.getByRole('button',{name:'已有账号？去登录'}).click();await page.getByLabel('用户名',{exact:true}).fill('demo');await page.getByLabel('密码',{exact:true}).fill('Campus2026!');await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('.account').getByText('夕拾同学',{exact:true}).waitFor();
 await page.getByRole('button',{name:'高等数学 · 同济第七版',exact:true}).click();
 await check('卖家回复买家留言',async()=>{const msg=page.locator('.message').filter({has:page.getByText('自动化验收：周末可以面交吗？',{exact:true})}).last();await msg.getByRole('button',{name:'回复这条留言'}).click();await page.getByLabel('留言内容',{exact:true}).fill('自动化验收：可以，图书馆南门见。');await page.getByRole('button',{name:'发送回复',exact:true}).click();await page.locator('.message.reply').filter({hasText:'自动化验收：可以，图书馆南门见。'}).last().waitFor()});await shot('07-seller-reply');await page.getByRole('button',{name:'关闭',exact:true}).click();
 await page.setViewportSize({width:390,height:844});await shot('08-mobile-home');await check('移动端无横向溢出',async()=>{const ok=await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth);if(!ok)throw Error('移动端横向溢出')});
 if(failures.length)throw Error(failures.join('\n'));
 fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({status:'PASS',steps,pageErrors:failures},null,2));
 console.log(JSON.stringify({status:'PASS',checks:steps.length,screenshots:9}));
 }catch(e){await shot('browser-failure');fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({status:'FAIL',steps,error:e.message,pageErrors:failures},null,2));throw e}finally{await browser.close()}
})();
