// 仅用于隔离的浏览器验收环境；审核通过正常管理 API 执行。
async function createReviewer(browser,base){
 const username=process.env.TEST_ADMIN_USERNAME,password=process.env.TEST_ADMIN_PASSWORD;
 if(!username||!password)throw Error('请设置隔离测试管理员 TEST_ADMIN_USERNAME / TEST_ADMIN_PASSWORD');
 const context=await browser.newContext();const response=await context.request.post(base+'/api/auth/login',{data:{username,password}});
 if(!response.ok())throw Error('验收管理员登录失败');
 return{
  async verify(request){const response=await request.post(base+'/api/me/verification',{data:{real_name:'验收学生',student_no:'QA'+Date.now()+Math.floor(Math.random()*1000),college:'测试学院'}});if(!response.ok())throw Error('提交测试认证失败');const me=await(await request.get(base+'/api/me')).json();const review=await context.request.patch(base+'/api/admin/verifications/'+me.id,{data:{status:'approved'}});if(!review.ok())throw Error('测试认证审核失败')},
  async approveOwned(request){const rows=await(await request.get(base+'/api/me/products')).json();for(const row of rows){if(row.review_status==='pending'){const response=await context.request.patch(base+'/api/admin/products/'+row.id,{data:{status:'approved'}});if(!response.ok())throw Error('测试商品审核失败')}}},
  close(){return context.close()}
 };
}
module.exports={createReviewer};
