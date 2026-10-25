# 开发指南

## 环境

使用 Python 3.11 或 3.12，按 README 启动服务。前端依赖已随仓库保存；浏览器自动化和离线文档生成另需 Node.js 及对应依赖。

通过 MARKET_DATA_DIR 指向独立开发数据库。运行数据、上传图片、认证证明、日志、密钥与虚拟环境不提交到 Git。

## 变更流程

1. 明确问题、预期行为与受影响模块。较大功能使用独立分支。
2. 修改实现；涉及字段、状态或权限时同步更新规格、数据库或 API 文档。
3. 按影响范围验证：界面改动检查浏览器，接口改动运行相关回归。
4. 检查 git diff，提交能说明具体变化的信息。

提交信息和公开文档描述项目的实际问题、实现及验证，不包含对话记录、个人环境细节或与项目无关的说明。

## 自动化检查

```sh
python -m pytest -q
node --check frontend/app.js
node --check frontend/campus.js
node --check frontend/experience.js
```

main 推送和 Pull Request 触发 GitHub Actions：Windows 接口与语法检查，以及 Linux Python 3.11／3.12 的启动验证。CI 不会自动部署网站。

## 浏览器检查

安装 Node.js、Playwright 和 Edge，在隔离数据库启动服务，并显式创建测试管理员。设置 BASE_URL、TEST_ADMIN_USERNAME、TEST_ADMIN_PASSWORD 后执行所需脚本：

```sh
node scripts/browser-test.cjs
node scripts/search-browser-test.cjs
node scripts/campus-browser-test.cjs
node scripts/auth-browser-test.cjs
node scripts/experience-browser-test.cjs
```

账号与布局专项见 scripts/account-browser-test.cjs；导航与恢复专项见 scripts/navigation-recovery-browser-test.cjs。后两者使用独立实验数据。脚本会写入测试账号、商品、消息和恢复设置，不应指向实际使用的数据库；重复运行恢复场景时需使用新的测试数据目录或等待限流窗口结束。

## 文档与版本

技术文档入口为 [docs/README.md](docs/README.md)，OpenAPI 可由 backend.main.app.openapi() 生成。使用 scripts/build-report.cjs 将 Markdown 导出为本地离线文档，生成文件不纳入 Git。

当前版本为 0.2.0-beta.1。测试版本标签包含 beta，GitHub Release 标记为 Pre-release。日常修改通过提交记录，不必为每个变更创建 Release。

## 提交检查

- 源码和技术文档描述当前实现，测试结果注明执行范围。
- 不提交真实账号、密码、Cookie、访问令牌、用户资料和数据库。
- 保留第三方许可声明；尚无项目源码开源许可证。
