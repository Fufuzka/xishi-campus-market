const campusFeatures={
 data(){return{campus:'',wantedItems:[],wantedTotal:0,wantedPage:1,wantedQuery:'',wantedMine:false,wantedOpen:false,wantedId:null,wantedForm:{},verificationForm:{real_name:'',student_no:'',college:'',image_urls:[]},verificationInfo:null,chats:[],activeChat:null,chatMessages:[],chatText:'',chatTimer:null,chatLoading:false,orders:[],appointmentOrder:null,appointmentForm:{meeting_place:'',meeting_time:''},reportProduct:null,reportReason:'',myReports:[],deleteProductTarget:null,adminTab:'verifications',adminData:[],adminOverview:{},adminNote:'',categoryName:'',categoryRows:[],actionBusy:false,campusError:''}},
 computed:{tabTitle(){return{browse:'校园集市',mine:'我的发布',favorites:'我的收藏',wanted:'校园求购',verification:'学生认证',inbox:'消息与交易',reports:'我的举报',admin:'平台管理'}[this.tab]||'夕拾'}},
 beforeUnmount(){clearInterval(this.chatTimer)},
 methods:{
 verificationName(v){return{unverified:'未认证',pending:'待审核',approved:'已认证',rejected:'已退回'}[v]||v},
 reviewName(v){return{pending:'待审核',approved:'审核通过',rejected:'已退回'}[v]||v},
 orderName(v){return{pending_communication:'待沟通',pending_trade:'待交易',completed:'已完成',cancelled:'已取消'}[v]||v},
 async guarded(action){if(this.actionBusy)return;this.actionBusy=true;try{await action()}catch(e){this.notify(e.message)}finally{this.actionBusy=false}},
 requireStudent(){if(!this.user){this.authOpen=true;return false}if(this.user.verification!=='approved'){this.notify('请先完成学生认证');this.go('verification');return false}return true},
 async load(){if(['browse','mine','favorites'].includes(this.tab))return this.loadProducts();this.campusError='';try{
   if(this.tab==='wanted'){const r=await this.api('/api/wanted?'+new URLSearchParams({q:this.wantedQuery,mine:this.wantedMine,page:this.wantedPage}));this.wantedItems=r.items;this.wantedTotal=r.total}
   if(this.tab==='verification'){this.verificationInfo=await this.api('/api/me/verification');this.user=await this.api('/api/me')}
   if(this.tab==='inbox')await this.loadInbox();
   if(this.tab==='reports')this.myReports=await this.api('/api/me/reports');
   if(this.tab==='admin')await this.loadAdmin();
 }catch(e){this.campusError=e.message}},
 async go(tab){if(tab==='chats'||tab==='orders')tab='inbox';if(!['browse','wanted'].includes(tab)&&!this.user){this.authOpen=true;this.notify('请先登录');return}if(tab==='admin'&&this.user?.role!=='admin')return;clearInterval(this.chatTimer);this.tab=tab;if(!this.user)this.wantedMine=false;this.page=1;this.detail=null;this.activeChat=null;this.searchOpen=false;await this.load();if(tab==='inbox')this.chatTimer=setInterval(()=>{if(!document.hidden&&this.tab==='inbox'&&!this.chatLoading)this.loadInbox().catch(()=>{})},4000);window.scrollTo({top:0,behavior:'smooth'})},
 async submitVerification(){if(!this.verificationForm.image_urls?.length){this.notify('请上传 1–3 张认证证明图片');return}await this.guarded(async()=>{await this.api('/api/me/verification',{method:'POST',body:JSON.stringify(this.verificationForm)});this.user=await this.api('/api/me');await this.load();this.notify('认证申请已提交，等待管理员审核')})},
 openWanted(p){if(!this.requireStudent())return;this.wantedId=p?.id||null;this.wantedForm=p?{title:p.title,description:p.description,budget:p.budget,condition:p.condition,campus:p.campus}:{title:'',description:'',budget:'',condition:'不限',campus:'主校区'};this.wantedOpen=true},
 async saveWanted(){await this.guarded(async()=>{await this.api('/api/wanted'+(this.wantedId?'/'+this.wantedId:''),{method:this.wantedId?'PUT':'POST',body:JSON.stringify(this.wantedForm)});this.wantedOpen=false;await this.load();this.notify('求购已保存')})},
 async closeWanted(p){await this.guarded(async()=>{await this.api('/api/wanted/'+p.id,{method:'DELETE'});await this.load();this.notify('求购已结束')})},
 async startChat(target){if(!this.requireStudent())return;await this.guarded(async()=>{const r=await this.api('/api/conversations',{method:'POST',body:JSON.stringify(target)});await this.go('chats');await this.selectChat(this.chats.find(x=>x.id===r.id))})},
 async selectChat(chat){this.activeChat=chat;this.chatMessages=[];this.chatText='';await this.refreshChat()},
 async refreshChat(){if(!this.activeChat||this.chatLoading)return;const id=this.activeChat.id;this.chatLoading=true;try{let after=this.chatMessages.at(-1)?.id||0;for(let i=0;i<10;i++){const rows=await this.api('/api/conversations/'+id+'/messages?after='+after);if(this.activeChat?.id!==id)return;for(const m of rows)if(!this.chatMessages.some(x=>x.id===m.id))this.chatMessages.push(m);if(rows.length<100)break;after=rows.at(-1).id}}finally{this.chatLoading=false}},
 async sendPrivate(){if(!this.chatText.trim())return;await this.guarded(async()=>{await this.api('/api/conversations/'+this.activeChat.id+'/messages',{method:'POST',body:JSON.stringify({content:this.chatText})});this.chatText='';await this.refreshChat()})},
 openAppointment(o){this.appointmentOrder=o;this.appointmentForm={meeting_place:o.meeting_place||'',meeting_time:o.meeting_time||''}},
 async saveAppointment(){await this.guarded(async()=>{await this.api('/api/orders/'+this.appointmentOrder.id+'/appointment',{method:'PATCH',body:JSON.stringify(this.appointmentForm)});this.appointmentOrder=null;await this.load();this.notify('面交安排已确认')})},
 async orderAction(o,action){await this.guarded(async()=>{await this.api('/api/orders/'+o.id+'/'+action,{method:'POST'});await this.load();this.notify(action==='cancel'?'约定已取消':'已记录你的完成确认，双方确认后结束交易')})},
 openReport(p){if(!this.user){this.authOpen=true;return}this.reportProduct=p;this.reportReason='';this.detail=null},
 async sendReport(){await this.guarded(async()=>{await this.api('/api/reports',{method:'POST',body:JSON.stringify({product_id:this.reportProduct.id,reason:this.reportReason})});this.reportProduct=null;this.notify('举报已提交，可在我的举报查看处理结果')})},
 async deleteProduct(){await this.guarded(async()=>{await this.api('/api/products/'+this.deleteProductTarget.id,{method:'DELETE'});this.deleteProductTarget=null;await this.load();this.notify('商品已删除，历史交易记录保留')})},
 async loadAdmin(){this.adminOverview=await this.api('/api/admin/overview');this.adminData=await this.api('/api/admin/'+this.adminTab);if(this.adminTab==='categories')this.categoryRows=this.adminData},
 async switchAdmin(tab){this.adminTab=tab;this.adminNote='';await this.load()},
 async reviewAdmin(row,status){await this.guarded(async()=>{if(status==='rejected'&&!this.adminNote.trim()){this.notify('请在审核意见填写退回原因');return}await this.api('/api/admin/'+this.adminTab+'/'+row.id,{method:'PATCH',body:JSON.stringify({status,note:this.adminNote})});this.adminNote='';await this.load();this.notify('审核已保存')})},
 async resolveReport(row,status,remove_product=false){await this.guarded(async()=>{if(this.adminNote.trim().length<2){this.notify('请填写处理意见');return}await this.api('/api/admin/reports/'+row.id,{method:'PATCH',body:JSON.stringify({status,resolution:this.adminNote,remove_product})});this.adminNote='';await this.load();this.notify('举报已处理')})},
 async toggleUser(row){await this.guarded(async()=>{await this.api('/api/admin/users/'+row.id,{method:'PATCH',body:JSON.stringify({disabled:!row.disabled})});await this.load()})},
 async saveCategory(name,active){await this.guarded(async()=>{await this.api('/api/admin/categories',{method:'PUT',body:JSON.stringify({name,active})});this.categoryName='';this.categories=await this.api('/api/categories');await this.load()})}
 }};
