import json
from pathlib import Path
from unittest.mock import Mock
import pytest

from desktop.config import normalize_server_url, validate_config, read_config, write_config
from desktop.main import Controller, SettingsAPI

@pytest.mark.parametrize('url,expected',[
    (' https://Market.Example.edu/ ','https://market.example.edu'),
    ('https://market.example.edu:8443','https://market.example.edu:8443'),
    ('http://127.0.0.1:8000/','http://127.0.0.1:8000'),
    ('http://localhost:8000','http://localhost:8000'),
])
def test_server_url_normalizes(url,expected):
    assert normalize_server_url(url)==expected

@pytest.mark.parametrize('url',[
    '', 'market.example.edu','http://market.example.edu','https://user:pass@market.example.edu',
    'https://market.example.edu/api','https://market.example.edu?q=1','https://market.example.edu/#x',
    'https://market.example.edu:bad','https://market.example.edu:0','file:///data',
    'javascript:alert(1)','https://market.example.edu\\evil','https://market.example.edu\n.evil',
])
def test_server_url_rejects_unsafe_values(url):
    with pytest.raises(ValueError):normalize_server_url(url)

def test_config_persistence_and_validation(tmp_path):
    assert read_config(tmp_path)=={'mode':'local','server_url':''}
    write_config(tmp_path,{'mode':'online','server_url':'https://market.example.edu/'})
    assert read_config(tmp_path)=={'mode':'online','server_url':'https://market.example.edu'}
    assert not (tmp_path/'config.json.tmp').exists()
    with pytest.raises(ValueError):write_config(tmp_path,{'mode':'online','server_url':''})
    assert read_config(tmp_path)['mode']=='online'
    with pytest.raises(ValueError):validate_config({'mode':'invalid'})

def test_bad_config_recovers_without_overwriting_original(tmp_path):
    path=tmp_path/'config.json';path.write_text('{broken',encoding='utf-8')
    controller=Controller(tmp_path)
    assert controller.config['mode']=='local'
    assert controller.warning
    assert path.read_text(encoding='utf-8')=='{broken'

def test_failed_connection_does_not_change_mode(tmp_path,monkeypatch):
    controller=Controller(tmp_path);controller.window=Mock()
    monkeypatch.setattr(controller,'connect',Mock(side_effect=ValueError('连接失败')))
    r=SettingsAPI(controller).apply_settings({'mode':'online','server_url':'https://market.example.edu'})
    assert not r['ok'] and controller.config['mode']=='local'
    assert not (tmp_path/'config.json').exists()
    controller.window.load_url.assert_not_called()

def test_switch_online_and_back_keeps_local_data(tmp_path,monkeypatch):
    controller=Controller(tmp_path);controller.window=Mock();controller.local=Mock()
    data=tmp_path/'data';data.mkdir();(data/'sentinel').write_text('preserve',encoding='utf-8')
    monkeypatch.setattr(controller,'connect',Mock(return_value='https://market.example.edu'))
    api=SettingsAPI(controller)
    assert api.apply_settings({'mode':'online','server_url':'https://market.example.edu'})['ok']
    controller.local.stop.assert_called_once()
    assert read_config(tmp_path)['mode']=='online'
    controller.connect.return_value='http://127.0.0.1:12345'
    assert api.apply_settings({'mode':'local','server_url':'https://market.example.edu'})['ok']
    assert read_config(tmp_path)['mode']=='local'
    assert (data/'sentinel').read_text(encoding='utf-8')=='preserve'

def test_settings_bridge_has_no_public_file_operations(tmp_path):
    api=SettingsAPI(Controller(tmp_path))
    assert sorted(name for name in dir(api) if not name.startswith('_'))==['apply_settings','get_settings','test_connection']
