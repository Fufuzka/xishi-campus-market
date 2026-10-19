"""打包源码、文档与证据，排除运行数据和缓存。"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

root=Path(__file__).resolve().parents[1]
archive=root.parent/'校园二手交易集市-完整交付.zip'
excluded={'data','.venv','__pycache__','.pytest_cache','.git','node_modules','build','dist','desktop-test','desktop','test-data'}
files=sorted(p for p in root.rglob('*') if p.is_file() and not any(part in excluded for part in p.relative_to(root).parts) and p.suffix not in ('.zip','.spec') and p.name!='delivery-manifest.json')
manifest={'project':'校园二手交易集市','version':'0.2.0-beta.1','date':'2026-10-19','stack':'FastAPI + Vue + SQLite','api_tests_passed':57,'release_stage':'beta','browser_checks_passed':57,'remote_deployed':False,'mentor_reviewed':False,'files':{str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
manifest_path=root/'delivery-manifest.json'
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for p in files+[manifest_path]:
        z.write(p,Path('campus-market')/p.relative_to(root))
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/data/' in n or '/test-data/' in n or '__pycache__' in n for n in z.namelist())
print(json.dumps({'archive':str(archive),'files':len(files)+1,'bytes':archive.stat().st_size},ensure_ascii=False))
