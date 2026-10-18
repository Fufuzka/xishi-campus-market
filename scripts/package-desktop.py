"""生成 Windows 用户便携包，附使用说明及已安装组件的许可原文。"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from importlib import metadata
import hashlib
import json
import re

root=Path(__file__).resolve().parents[1]
version=re.search(r"StringStruct\('ProductVersion', '([^']+)'\)", (root/'desktop/version-info.txt').read_text(encoding='utf-8')).group(1)
exe=root/'dist'/version/'夕拾.exe'
archive=root.parent/'夕拾-Windows便携版.zip'
instructions='''夕拾校园集市 Windows 便携版 1.3.0

一、启动软件
解压后双击“夕拾.exe”。不需要安装 Python 或手动启动服务。
适用于 Windows 10 / 11 64 位，需要 Microsoft Edge WebView2 Runtime。
如果提示缺少该组件，安装微软官方 Evergreen Runtime 后重试：
https://developer.microsoft.com/microsoft-edge/webview2/

二、本地演示
首次启动自动准备 8 件演示商品。
账号：demo 或 buyer
密码：Campus2026!
可自行注册新账号，发布、编辑、上传图片、收藏和留言。
密码右侧眼睛按钮可显示/隐藏输入，登录与注册均支持。
新版采用固定侧栏和顶部工具栏，侧栏可直接打开连接设置与使用帮助。
搜索支持历史记录、可能想搜、输入联想；默认最相关，价格按钮切换低高排序。
筛选支持分类、成色、价格区间和发布时间，条件可逐项移除。

三、以后切换联网
在服务器部署好同一套校园集市后：
点击窗口左上角“夕拾”→“连接设置”→“联网使用”。
填写真实 HTTPS 根地址（不要加 /api），测试连接后保存并切换。
下次打开会记住选择；也可以随时切回本地演示。
本地与服务器数据、账号相互独立，切换不会自动上传或迁移。

四、数据保存
本地数据目录：%LOCALAPPDATA%\\ShiguangMarket\\data
同级 config.json 保存连接设置，desktop.log 保存运行日志。
软件退出会停止本地服务，已有商品不会删除，替换 EXE 不会清空数据。
需要备份时先关闭软件，再复制整个 ShiguangMarket 用户数据目录。
原网页项目 data 目录与桌面版独立，若要迁移须另做备份与迁入。

五、验收状态
59 项接口与桌面配置测试通过，27 项浏览器流程检查通过。
实际 EXE 已验证窗口、连接测试、本地/另一服务切换、切回后数据保留。
EXE 服务已验证新增商品和重启后数据及会话保留。
公网 HTTPS 服务器尚未部署，不将本机测试当作公网验收。

本包为免安装的便携版，可自行创建 EXE 的桌面快捷方式。
示例商品与联系方式只用于课程演示，不用于真实交易。
'''
license_count=0
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    base='夕拾校园集市/'
    z.write(exe,base+exe.name)
    z.writestr(base+'使用说明.txt',instructions.encode('utf-8-sig'))
    z.write(root/'THIRD_PARTY_NOTICES.md',base+'第三方组件说明.md')
    z.write(root/'frontend/vendor/VUE-LICENSE',base+'许可原文/Vue-LICENSE.txt')
    for dist in metadata.distributions():
        name=dist.metadata['Name']
        for file in dist.files or []:
            if not any(x in file.name.lower() for x in ('license','copying','notice')):
                continue
            if not any(x.endswith('.dist-info') for x in file.parts):
                continue
            p=Path(dist.locate_file(file))
            if p.is_file() and p.suffix not in ('.py','.pyc'):
                z.write(p,base+'许可原文/'+name+'/'+str(file).replace('\\','/'))
                license_count+=1
    z.writestr(base+'构建信息.json',json.dumps({'version':'1.3.0','platform':'Windows x64','exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'runtime':'WebView2 required','tests_passed':59},ensure_ascii=False,indent=2).encode('utf-8'))
with ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({'bytes':archive.stat().st_size,'licenses':license_count,'exe_bytes':exe.stat().st_size}))
