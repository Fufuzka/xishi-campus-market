import importlib.util
import os
from pathlib import Path
import pytest

MODULE = Path(__file__).parents[1] / 'scripts/create-running-admin.py'
spec = importlib.util.spec_from_file_location('admin_runtime', MODULE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def process(tmp_path, pid, cwd, python, data=None, launcher=None):
    proc = tmp_path / 'proc'
    entry = proc / str(pid)
    entry.mkdir(parents=True)
    args = [str(launcher or python), '-m', 'uvicorn', 'backend.main:app']
    (entry / 'cmdline').write_bytes(b'\0'.join(x.encode() for x in args))
    env = {'VIRTUAL_ENV':str(python.parents[1]), 'PATH':str(python.parent)}
    if data is not None:env['MARKET_DATA_DIR']=str(data)
    (entry / 'environ').write_bytes(b'\0'.join((k+'='+v).encode() for k,v in env.items()))
    return entry / 'cwd', str(cwd)


def test_running_admin_selects_same_data_and_venv(tmp_path,monkeypatch):
    root=tmp_path/'site';root.mkdir()
    python=tmp_path/'venv/bin/python';python.parent.mkdir(parents=True);python.touch()
    links=dict([process(tmp_path,111,root,python,'private-data'),process(tmp_path,112,root,python,'private-data'),process(tmp_path,113,tmp_path/'other',python,'other-data')])
    monkeypatch.setattr(os,'readlink',lambda p:links[Path(p)])
    choices=runtime.running_sites(root,tmp_path/'proc')
    assert choices==[((root/'private-data').resolve(),python.absolute())]


def test_running_admin_does_not_guess_between_databases(tmp_path,monkeypatch):
    root=tmp_path/'site';root.mkdir()
    python=tmp_path/'venv/bin/python';python.parent.mkdir(parents=True);python.touch()
    links=dict([process(tmp_path,111,root,python,'data-one'),process(tmp_path,112,root,python,'data-two')])
    monkeypatch.setattr(os,'readlink',lambda p:links[Path(p)])
    assert len(runtime.running_sites(root,tmp_path/'proc'))==2


def test_running_admin_empty_environment_uses_project_data(tmp_path,monkeypatch):
    root=tmp_path/'site';root.mkdir()
    python=tmp_path/'venv/bin/python';python.parent.mkdir(parents=True);python.touch()
    links=dict([process(tmp_path,111,root,python)])
    monkeypatch.setattr(os,'readlink',lambda p:links[Path(p)])
    assert runtime.running_sites(root,tmp_path/'proc')[0][0]==(root/'data').resolve()


def test_running_admin_reads_venv_launcher_without_virtual_env(tmp_path,monkeypatch):
    root=tmp_path/'site';root.mkdir()
    python=tmp_path/'venv/bin/python';python.parent.mkdir(parents=True);python.touch()
    launcher=python.parent/'uvicorn';launcher.write_text('#!'+python.as_posix()+'\n')
    links=dict([process(tmp_path,111,root,python,launcher=launcher)])
    (tmp_path/'proc/111/environ').write_bytes(('PATH='+str(python.parent)).encode())
    monkeypatch.setattr(os,'readlink',lambda p:links[Path(p)])
    assert runtime.running_sites(root,tmp_path/'proc')==[((root/'data').resolve(),python.absolute())]


def test_running_admin_passes_same_data_and_interactive_password(tmp_path,monkeypatch):
    (tmp_path/'market.db').touch()
    python=tmp_path/'python'
    monkeypatch.setattr(runtime,'running_sites',lambda root:[(tmp_path,python)])
    monkeypatch.setattr(runtime.sys,'argv',['create-running-admin.py','new_admin'])
    monkeypatch.setenv('MARKET_ADMIN_PASSWORD','must-not-be-used')
    called=[]
    def run(args,**kwargs):
        called.append((args,kwargs))
        return type('Result',(),{'returncode':0})()
    monkeypatch.setattr(runtime.subprocess,'run',run)
    original=runtime.Path.is_dir
    monkeypatch.setattr(runtime.Path,'is_dir',lambda self:True if self.as_posix()=='/proc' else original(self))
    with pytest.raises(SystemExit) as result:runtime.main()
    assert result.value.code==0
    args,kwargs=called[0]
    assert args==[str(python),'-m','backend.create_admin','new_admin']
    assert kwargs['env']['MARKET_DATA_DIR']==str(tmp_path)
    assert 'MARKET_ADMIN_PASSWORD' not in kwargs['env']
    assert 'stdin' not in kwargs
