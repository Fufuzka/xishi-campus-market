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

首次从其他电脑使用：克隆仓库，安装 Python 3.12，按 README 启动。桌面软件打包另按 requirements-desktop.txt 与 scripts/build-desktop.ps1 执行。

## 检查与自动测试

```powershell
python -m pytest -q
node --check frontend/app.js
```

main 推送和 Pull Request 会触发 GitHub Actions，执行 JavaScript 语法及 API / 桌面配置测试。该工作流不会启动图形窗口，不做公网部署，不替代真实 EXE 或浏览器验收。已有截图与结果是历史验收材料，代码变动后应按影响范围更新。

## 不纳入 Git 的文件

运行数据库、用户上传、日志、环境文件与密钥、虚拟环境、构建缓存、EXE 和 ZIP 均被 .gitignore 排除。演示用公开账号的初始化脚本属于可重现测试材料；它不是 GitHub 或服务器凭据。

提交前检查 `git status` 和 `git diff --cached`，确认没有真实账号、密码、Cookie、访问令牌或用户数据。无需把 Python 虚拟环境和生成的安装包放进仓库。

## 软件版本发布

1. 完成并验证改动，更新桌面版本、说明和相关测试证据。
2. 运行打包脚本，在本机检查 EXE 和生成的便携包。
3. 在私有仓库创建对应版本的 Release，上传 ZIP 与 SHA-256 校验文件。
4. 发布的是私有仓库资产，不会改变代码仓库的可见性。

不要提交公网服务器凭据。未来若引入自动部署或自动发布，使用仓库 Secrets 或受限工作流，不把密钥写入代码。
