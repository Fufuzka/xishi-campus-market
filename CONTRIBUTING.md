# 夕拾的个人开发流程

此仓库用于私人开发，默认不邀请协作者、不开放公开访问；未为项目附加开源许可。第三方组件仍适用各自许可，见 THIRD_PARTY_NOTICES.md。仓库可见性与软件部署是两件事：代码保存到 GitHub 不会自动将网站部署到公网。

## 日常修改

小改动可以在 main 开发并提交；较大功能建议新建分支，如 `feature/product-management`，完成检查后合并。提交信息说明实际改变，例如“增加密码查看按钮”，不要伪造过去的开发历史。

```powershell
git status
git add frontend/app.js frontend/index.html frontend/style.css
git commit -m "完善商品列表交互"
git push
```

首次从其他电脑使用：克隆仓库，安装 Python 3.12，按 README 启动。在浏览器打开服务地址进行测试。

## 检查与自动测试

```powershell
python -m pytest -q
node --check frontend/app.js
```

main 推送和 Pull Request 会触发 GitHub Actions，执行 JavaScript 语法及 API 测试。该工作流不会启动图形窗口，不做公网部署，不替代浏览器验收。已有截图与结果是历史验收材料，代码变动后应按影响范围更新。

## 不纳入 Git 的文件

运行数据库、用户上传、日志、环境文件与密钥、虚拟环境、构建缓存、EXE 和 ZIP 均被 .gitignore 排除。演示用公开账号的初始化脚本属于可重现测试材料；它不是 GitHub 或服务器凭据。

提交前检查 `git status` 和 `git diff --cached`，确认没有真实账号、密码、Cookie、访问令牌或用户数据。无需把 Python 虚拟环境和生成的安装包放进仓库。

## 测试版管理

当前为网页测试版 0.1.0-beta.1。后续用 beta 编号记录迭代，例如 0.1.0-beta.2；未经用户明确确认，不标为正式版，不创建稳定版发布。

1. 完成改动，运行 API 与浏览器验收，更新实际证据和文档。
2. 代码通过 Git 提交管理；每次修改不必创建 Release。
3. 如需保存测试节点，标签包含 beta；GitHub Release 必须勾选 Pre-release，不上传 EXE。
4. 未来部署到服务器后，仍在浏览器验收并保持测试版标识，公网部署不等于正式发布。

不要提交公网服务器凭据。部署凭据使用受限 Secrets，不把密钥写入代码。
