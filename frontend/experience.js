const experienceFeatures={
 data(){return{settingsOpen:false,layout:'garden',viewer:null,proofUploading:false,inboxFilter:'all',layouts:[{id:'garden',name:'林间集市',description:'侧栏导航与舒展卡片，适合日常浏览'},{id:'horizon',name:'轻简横栏',description:'顶部导航与宽屏内容，让商品更突出'},{id:'compact',name:'清单浏览',description:'紧凑列表与完整摘要，方便比较商品'}]}},
 computed:{
  previousOrders(){return this.activeChat?this.orders.filter(o=>this.matchesOrder(this.activeChat,o)&&o.id!==this.activeOrder?.id):[]},
  activeOrder(){return this.activeChat?this.orderForChat(this.activeChat):null},
  inboxThreads(){if(!this.user)return [];const rows=this.chats.map(c=>({...c,order:this.orderForChat(c)}));for(const o of this.orders){if(!rows.some(c=>c.order?.id===o.id||this.matchesOrder(c,o)))rows.push({id:'order-'+o.id,order:o,title:o.title,peer:this.user.id===o.buyer_id?o.seller:o.buyer,last_message:'查看面交安排，继续沟通',product_id:o.product_id})}return rows.filter(c=>this.inboxFilter==='all'||this.inboxFilter==='orders'&&c.order||this.inboxFilter==='active'&&c.order&&['pending_communication','pending_trade'].includes(c.order.status)||this.inboxFilter==='completed'&&c.order?.status==='completed')}
 },
 mounted(){try{const saved=localStorage.getItem('xishi-layout');if(this.layouts.some(x=>x.id===saved))this.layout=saved}catch{}document.body.dataset.layout=this.layout;document.addEventListener('keydown',this.galleryKey)},
 beforeUnmount(){document.removeEventListener('keydown',this.galleryKey)},
 methods:{
 setLayout(id){if(!this.layouts.some(x=>x.id===id))return;this.layout=id;document.body.dataset.layout=id;try{localStorage.setItem('xishi-layout',id)}catch{this.notify('布局已切换，本次浏览器无法保存设置')}},
 imagesOf(p){return p?.image_urls?.length?p.image_urls:p?.image_url?[p.image_url]:[]},
 openGallery(images,index=0,title='图片预览'){if(images?.length)this.viewer={images:[...images],index,title}},
 galleryKey(e){if(!this.viewer)return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();this.viewer.index=(this.viewer.index+(e.key==='ArrowRight'?1:-1)+this.viewer.images.length)%this.viewer.images.length}},
 async uploadBatch(event,kind){const files=Array.from(event.target.files||[]);event.target.value='';if(!files.length)return;const list=kind==='proof'?(this.verificationForm.image_urls||=[]):(this.form.image_urls||=[]);if(list.length+files.length>3){this.notify('最多提交 3 张图片，请先移除不需要的图片');return}if(files.some(f=>f.size>5*1024*1024)){this.notify('每张图片不能超过 5 MB');return}if(kind==='proof')this.proofUploading=true;else this.uploading=true;try{for(const file of files){const body=new FormData();body.append('file',file);const r=await this.api(kind==='proof'?'/api/verification-images':'/api/uploads',{method:'POST',body});list.push(r.url)}if(kind==='product'){this.form.image_url=list[0]||'';this.imageUrlInput=''}this.notify('图片已上传')}catch(e){if(kind==='product')this.form.image_url=list[0]||'';this.notify(e.message)}finally{if(kind==='proof')this.proofUploading=false;else this.uploading=false}},
 removeImage(kind,index){if(this.uploading||this.proofUploading)return;const list=kind==='proof'?this.verificationForm.image_urls:this.form.image_urls;list.splice(index,1);if(kind==='product')this.form.image_url=list[0]||''},
 applyImageUrl(){const value=this.imageUrlInput.trim();if(!value)return;if(!value.startsWith('https://')){this.notify('图片链接应以 https:// 开头');return}const list=this.form.image_urls||=[];if(list.includes(value))return;if(list.length>=3){this.notify('最多提交 3 张图片');return}list.push(value);this.form.image_url=list[0];this.imageUrlInput=''},
 matchesOrder(c,o){return c.product_id===o.product_id&&c.starter_id===o.buyer_id&&c.recipient_id===o.seller_id},
 orderForChat(c){return this.orders.find(o=>this.matchesOrder(c,o))||null},
 async loadInbox(){const [chats,orders,user]=await Promise.all([this.api('/api/conversations'),this.api('/api/orders'),this.api('/api/me')]);if(this.tab!=='inbox')return;this.user=user;this.chats=chats;this.orders=orders;if(this.activeChat){this.activeChat=chats.find(c=>c.id===this.activeChat.id)||null;if(this.activeChat)await this.refreshChat()}},
 async selectThread(c){try{if(typeof c.id==='string'){const result=await this.api('/api/orders/'+c.order.id+'/conversation',{method:'POST'});await this.loadInbox();c=this.chats.find(x=>x.id===result.id)}if(c)await this.selectChat(c)}catch(e){this.notify(e.message)}},
 async focusOrder(oid){const o=this.orders.find(x=>x.id===oid);if(!o)return;const r=await this.api('/api/orders/'+oid+'/conversation',{method:'POST'});await this.loadInbox();await this.selectThread(this.chats.find(c=>c.id===r.id))},
 async createOrder(p){if(!this.requireStudent())return;await this.guarded(async()=>{const result=await this.api('/api/orders',{method:'POST',body:JSON.stringify({product_id:p.id})});await this.go('inbox');await this.focusOrder(result.id);this.notify('交易约定已建立，可以在这里沟通和确认面交')})},
 async openOrderChat(o){await this.go('inbox');await this.focusOrder(o.id)}
 }};
