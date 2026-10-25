# CloudStudio 导入与一键启动

网页测试版 0.2.0-beta.1 · 2026-10-21 · 尚非正式版

## 1. 仓库与项目结构

仓库使用单服务结构：FastAPI 同时提供前端页面和 API。运行数据库、用户图片、认证证明、环境文件与密钥不纳入版本管理。

公开导入地址：`https://github.com/Fufuzka/xishi-campus-market.git`。

夕拾采用 FastAPI 同时提供 Vue 页面、静态资源和 API，所有请求为同源相对路径。不需要 Node、Vite、前端单独端口、`VITE_API_BASE_URL` 或 Vite proxy，接口路径以当前 OpenAPI 为准。

## 2. CloudStudio 操作

1. 选择 Python 3.11 或 3.12 环境（已有 3.11.1 可直接使用），从上面的公开 GitHub 地址导入仓库，选择 main 分支。
2. 在项目根目录打开终端，执行 `sh start.sh --cloud`。脚本自动创建 Python 虚拟环境、安装锁定依赖，并在 `0.0.0.0:8000` 启动一个服务，同时提供网页和接口。
3. 在平台端口／应用预览中打开 **8000** 端口的 HTTPS 预览地址。项目已有 `.vscode/preview.yml`，支持读取该配置的平台可直接点运行／启动。
4. 浏览器打开平台生成的完整 HTTPS 地址，检查 `/api/health`，再注册学生、提交认证图片、创建管理员审核并验收业务。

如果平台要求其他 Git 托管源，可通过同步仓库导入。创建代码工作区后仍需运行服务并开放预览端口。

## 3. 测试数据和管理员

默认不生成演示账号，也不自动创建管理员。需要仅供功能演示的数据时，使用 `sh start.sh --cloud --demo`，并清楚标注演示环境；对已有用户的数据库，seed 不重复写入。

首次依赖安装后，另开终端创建管理员：

```sh
.venv/bin/python -m backend.create_admin your_admin_name
```

如果启动日志显示使用 `.venv-3.11`，请将上面命令中的 `.venv/bin/python` 换成 `.venv-3.11/bin/python`；以启动日志显示的实际环境目录为准。

密码交互输入，不写进代码或 Git，不把本机演示管理员的密码用于公开站点。普通用户仍只能由管理员人工审核认证。

## 4. 端口、HTTPS 与代理

默认一键命令使用 8000；需要其他端口时，例如 `PORT=8080 sh start.sh --cloud`，同时把平台预览端口和 preview.yml 调整为 8080。服务必须监听 0.0.0.0，预览地址里的端口必须一致。

Cloud 模式默认 `COOKIE_SECURE=1`，供 HTTPS 预览使用。不要使用 HTTP 预览地址验证登录 Cookie。在本机模拟云端启动时可显式设 `COOKIE_SECURE=0`，这只是本机 HTTP 测试选项。

平台如提供完整的 `X_IDE_SPACE_KEY`、`X_IDE_SPACE_REGION`、`X_IDE_SPACE_HOST`，脚本按官方规则自动生成 `MARKET_PUBLIC_ORIGIN`。平台的外部 HTTPS 来源与内部 HTTP 地址不同时，后端允许这个精确来源提交，仍拒绝其他来源，不开放任意跨站访问。

如这些变量不存在或实际预览地址不同，请把平台提供的真实站点根地址配置到环境变量：

```sh
export MARKET_PUBLIC_ORIGIN=https://your-real-preview-host
sh start.sh --cloud
```

地址不加 `/api`、页面路径、账号密码、查询参数或片段。脚本只读取导出的环境变量；根目录 `.env.example` 是说明模板，不会自动被当成 shell 脚本执行。

| 环境变量 | 作用 |
|---|---|
| PORT | 监听端口，默认 8000，1024–65535 |
| MARKET_HOST | Cloud 默认 0.0.0.0；普通本机默认 127.0.0.1 |
| MARKET_PYTHON | 可选 Python 3.11 或 3.12 可执行文件路径 |
| MARKET_VENV | 虚拟环境目录，默认 .venv；默认目录异常时自动选择 .venv-版本号，保留旧目录 |
| MARKET_DATA_DIR | 数据库、商品上传、认证证明的持久化目录，默认项目 data |
| MARKET_PUBLIC_ORIGIN | 可选精确 HTTPS 预览来源，脚本可从平台变量生成 |
| COOKIE_SECURE | Cloud 默认为 1；仅本机 HTTP 测试可设 0 |
| FORWARDED_ALLOW_IPS | 信任的代理 IP，默认 127.0.0.1，不默认信任所有客户端 |
| MARKET_SKIP_INSTALL | 仅预装依赖的测试环境使用 1，正常一键启动无需设置 |

## 5. 数据与运行状态

数据库、上传商品图片和认证证明都在 MARKET_DATA_DIR 下。若平台磁盘是临时的，应先配置持久化目录并做备份；工作环境停止、重置或到期时，预览服务也可能停止。开发预览与长期运行的公网生产部署应分别记录。

当前代码仍为测试版。预览地址由平台生成；长期运行环境需完成身份校验、限流、HTTPS 与数据备份恢复验证。

## 6. 验证和官方参考

本机通过 Git Bash 实际执行 `start.sh --cloud`，使用已有 Python 3.12 依赖和空隔离数据库，验证同端口页面及接口、无自动演示数据、精确 HTTPS 来源注册和登录 Cookie、非法来源拒绝、认证图片私有权限、认证提交、无自动管理员权限及退出，共 10 项。模拟测试的 HTTP 端口显式关闭 Secure Cookie，不冒称已经验证平台 HTTPS 证书。

新增 Ubuntu GitHub Actions 任务，从公开代码安装依赖并执行同一启动脚本与验收，结果见仓库 Actions。接口自动化覆盖代理来源配置和 Secure Cookie，Linux 任务状态以真实运行结果为准。

依据腾讯云官方 [配置运行文件](https://cloud.tencent.com/document/product/1039/131807) 使用 `.vscode/preview.yml` 的 apps、root、run、port、mainPort；依据 [URL 访问异常排查](https://cloud.tencent.com/document/product/1039/131933) 采用 0.0.0.0 监听及平台预览地址变量。

## 7. Python 版本与创建环境失败

报错 `ensurepip is not available` 表示所选 Python 缺少虚拟环境的 pip 引导组件，不表示必须换成 3.12。已选择 `pyenv shell 3.11.1` 的工作区可执行：

```sh
git pull
pyenv shell 3.11.1
sh start.sh --cloud
```

脚本优先使用当前终端选择的 Python 3.11／3.12。若旧 `.venv` 创建失败或版本不同，会保留旧目录，自动创建／复用 `.venv-3.11` 等新环境。创建时优先使用 ensurepip；缺失时尝试使用现有 Python 的 pip 引导新虚拟环境，不安装系统级依赖。若两种方式均不可用，脚本明确报错，需选用带 ensurepip 或 pip 的 Python。

## 8. 更新后的前端资源缓存

首页 HTML 使用 no-store，核心脚本与样式使用 no-cache, must-revalidate。首页根据 HTML、应用脚本、样式和 Vue 文件的内容生成统一资源指纹，并在引用 URL 中附加 v 参数。内容变化后指纹更新，使页面与对应脚本重新加载，避免旧缓存缺少新交互方法。

部署更新后需刷新已打开的页面一次；服务不会在后台强制刷新正在编辑的页面。若出现旧脚本相关报错，先确认代码已拉取并重启服务，再刷新浏览器。
