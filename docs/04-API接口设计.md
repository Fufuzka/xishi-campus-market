# API 接口设计

> 当前：网页测试版 0.1.0-beta.1（2026-10-19），不作为正式版。下文旧版本号、桌面和历史测试结果仅为开发过程记录；当前运行与部署以 README、10 文档及最新验收记录为准。

文档编号 SGM-API-001 · 版本 1.0 · 日期 2026-10-18

## 1. 通用约定

基路径 `/api`；普通请求 / 响应为 JSON；上传为 multipart/form-data。认证使用 `market_session` HttpOnly Cookie，前端 fetch 使用 same-origin credentials。会话时长七天，退出立即使当前 token 失效。默认不开放跨域，变更请求如携带 Origin，必须与当前站点匹配。

错误格式 `{"detail":"中文错误信息"}`。状态码：200 成功；201 新建；401 未登录 / 登录失败；403 越权 / 跨站；404 不存在；409 用户名或商品状态冲突；413 图片过大；422 参数无效。服务端验证失败统一返回中文消息，前端显示后允许修改重试。

真实字段与全部边界约束见同目录 `openapi.json`（由应用代码导出）；运行后 `/docs` 可交互测试。

## 2. 接口清单

| 方法 | 路径 | 登录 | 请求 / 返回 |
|---|---|---|---|
| POST | /auth/register | 否 | username、password、nickname → 用户，201，并设置 Cookie |
| POST | /auth/login | 否 | username、password → 用户，并设置 Cookie |
| POST | /auth/logout | 否 | 无 → ok，删除 Cookie 和当前会话 |
| GET | /me | 是 | id、username、nickname |
| GET | /health | 否 | status、version；数据库连通检查 |
| GET | /categories | 否 | 分类字符串数组 |
| GET | /products | 否 | 查询参数 → items、total、page、page_size |
| POST | /products | 是 | ProductInput → id，201 |
| GET | /products/{pid} | 否 | 商品详情和收藏状态；游客联系方式被遮蔽 |
| PUT | /products/{pid} | 本人 | 完整 ProductInput → ok |
| PATCH | /products/{pid}/status | 本人 | status → ok |
| GET | /me/products | 是 | 本人的全部状态商品数组，包含本人联系方式 |
| GET | /me/favorites | 是 | 本人收藏商品数组，保留非在售状态；不附联系方式 |
| PUT | /products/{pid}/favorite | 是 | 无 → ok，幂等收藏 |
| DELETE | /products/{pid}/favorite | 是 | 无 → ok，幂等取消 |
| GET | /products/{pid}/messages | 否 | 按留言 ID 升序的留言数组 |
| POST | /products/{pid}/messages | 是 | content、可选 parent_id → id，201 |
| POST | /uploads | 是 | file → url，201 |

## 3. 商品列表查询参数

| 字段 | 默认 / 范围 | 说明 |
|---|---|---|
| q | 空字符串；最长 100 字 | 标题、描述子串匹配，不区分英文大小写 |
| category | 空字符串 | 不传为全部；按分类精确匹配，无匹配返回空数组 |
| min_price | 0；0–999999 | 单位元，含下界 |
| max_price | 999999；0–999999 | 含上界，不能小于最低价 |
| sort | relevance | relevance / newest / price_asc / price_desc |
| condition | 不限 | 全新 / 几乎全新 / 轻微使用 / 正常使用 |
| published_within | 不限 | 1 / 3 / 7 / 14 天内发布 |
| page | 1；>=1 | 页码 |
| page_size | 12；1–48 | 每页大小 |

列表只展示 `on_sale`。价格相同时按商品 ID 倒序稳定排序。

```http
GET /api/products?q=高数&category=教材书籍&min_price=10&max_price=50&sort=price_asc&page=1&page_size=12
```

```json
{"items":[{"id":1,"owner_id":1,"title":"高数教材","description":"保存完好的高数教材","price":18,"category":"教材书籍","image_url":"/assets/book.svg","location":"图书馆南门","condition":"轻微使用","status":"on_sale","seller":"夕拾同学","created_at":"2026-10-18 01:00:00","updated_at":"2026-10-18 01:00:00"}],"total":1,"page":1,"page_size":12}
```

以上为协议示例，时间不代表真实执行时间。公共列表不含 contact；price 为数字（元），不是 price_cents。

## 4. 发布和编辑

```json
{
  "title": "高数教材",
  "description": "保存完好，含少量铅笔笔记，可当面检查。",
  "price": "18.50",
  "category": "教材书籍",
  "image_url": "/uploads/随机文件名.jpg",
  "contact": "微信：示例账号",
  "location": "图书馆南门",
  "condition": "轻微使用"
}
```

price 可传合法 JSON 数字或十进制字符串，最多两位小数；所有上述字段在 PUT 中仍必须完整提供。新建不接收 owner_id，以当前会话用户为准；默认状态在售。成色可省略，默认“轻微使用”。图片 URL 为 HTTPS 或 `/uploads/`、`/assets/` 本地安全路径。

成功新建返回 `{"id":9}`。更新返回 `{"ok":true}`。他人商品更新、状态变更返回 403。

## 5. 商品详情与状态

GET 详情在商品字段之外增加 `contact`、`favorited`。游客 contact 为“登录后查看联系方式”，favorited 为 false；已登录用户获得真实联系方式和自己的收藏状态。

PATCH 请求 `{"status":"off_shelf"}`，状态只能为 on_sale / off_shelf / sold。sold 不可转回其他状态，返回 409。已下架和已售出详情保留，便于查看历史收藏，不能继续新增留言。

## 6. 留言与回复

根留言请求：`{"content":"周末可以面交吗？"}`。卖家回复：`{"content":"可以，在图书馆南门见。","parent_id":1}`。父留言必须存在于同一商品且为根留言；否则 422。非卖家传 parent_id 返回 403。停止销售的商品返回 409。

列表单条格式：

```json
{"id":1,"product_id":1,"user_id":2,"content":"周末可以面交吗？","parent_id":null,"created_at":"2026-10-18 01:00:00","nickname":"小林同学"}
```

留言为公开商品讨论；不能在此填写私密信息。界面不执行留言中的 HTML。

## 7. 图片上传

表单字段名 `file`，内容必须可解码为 JPEG / PNG / WebP；上限 5×1024×1024 字节，最多 2000 万像素。服务端缩小到最长边 1600，并重新编码 JPEG，返回 `/uploads/<随机名>.jpg`。不保留上传文件名，不接受 SVG / HTML 上传。图片 URL 仅为浏览器展示，后端不会主动抓取远程 URL。

## 8. 接口变更与兼容

本版完整替换编辑使用 PUT；收藏 PUT / DELETE 幂等；注册不是幂等，重复用户名 409。前端不重试写请求，避免网络异常时重复发布。后续新增接口保持现有字段语义；破坏性变更需升级路径或版本并同步 Spec、OpenAPI 和测试。

## 9. 1.3 搜索接口

GET /search/suggestions 接受 q（最多 100 字）、limit（默认 8、1–24），返回 items 字符串数组；只从真实在售标题生成候选。GET /search/history 返回当前范围的 items 及 scope（account / device）。POST /search/history 接受 keyword；DELETE /search/history 通过可选 keyword 删除一条或清空当前范围。游客通过 HttpOnly 随机设备 Cookie 识别，不要求登录；登录账号与游客范围不合并。详见 12 文档和导出的 OpenAPI。
