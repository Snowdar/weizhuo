"""Headless native UI smoke check; not a substitute for device testing."""
import os,sys,asyncio
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from pathlib import Path
os.environ['TOGA_BACKEND']='toga_dummy'
sys.path.insert(0,str(Path(__file__).parent/'src'))
from weizhuomobile.app import main
live={'wifi':'192.168.1.20','hotspot':''}
discovery=patch('weizhuomobile.app.wifi_address',side_effect=lambda mode='wifi':live[mode])
discovery.start()
app=main();app.startup()
try:
    assert app.main_window.content is app.launcher
    with patch('weizhuomobile.app.wifi_address',return_value='172.20.10.1') as discover:
        app.select_network_mode('本机热点')
        assert app.start_button.enabled
        discover.assert_called_with('hotspot')
        assert app.address.value=='172.20.10.1'
        assert app.wifi_button.text=='同一 Wi-Fi' and app.hotspot_button.text=='本机热点'
        assert app.status.style.height==96
        assert not hasattr(app,'confirm_network_button')
    with patch('weizhuomobile.app.wifi_address',return_value=''):
        app.refresh_address(None)
        assert app.address.value=='' and '尚未检测' in app.status.text
        assert not app.start_button.enabled and not app.wifi_button.enabled
    live['hotspot']='172.20.10.1'
    app.refresh_address(None)
    live['hotspot']=''
    app.refresh_address(None)
    assert app.wifi_button.enabled and app.network_mode=='本机热点'
    assert app.address.value=='' and not app.start_button.enabled
    live['hotspot']='172.20.10.1'
    app.refresh_address(None)
    app.host.server=object()
    app.show_table(None);assert app.main_window.content is app.table
    app.show_service(None);assert app.main_window.content is app.launcher
    app.show_table(None);assert app.main_window.content is app.table
    app.host.server=None
    with patch.object(app.host,'start',side_effect=RuntimeError('服务初始化失败')),patch('weizhuomobile.app.traceback.print_exc'):
        asyncio.run(app.start_host(None))
        assert app.start_button.enabled and '启动失败' in app.status.text
    app.address.value='192.168.1.20'
    def started(address):
        assert app.status.text=='正在启动服务…'
        assert not app.start_button.enabled
        app.host.server=SimpleNamespace(server_port=23456)
        return 'http://192.168.1.20:23456/'
    with patch.object(app.host,'start',side_effect=started):
        asyncio.run(app.start_host(None))
        assert app.stop_button.enabled and app.main_window.content is app.table
        assert app.web.url=='http://127.0.0.1:23456/'
    running=app.host.server
    with patch('weizhuomobile.app.wifi_address',return_value='192.168.1.20'):
        app.select_network_mode('同一 Wi-Fi')
        assert app.network_changed and app.start_button.text=='重启服务'
        app.select_network_mode('本机热点')
        assert not app.network_changed
    app.show_service(None)
    assert app.host.server is running and app.stop_button.enabled
    assert app.start_button.text=='进入大厅'
    with patch.object(app.host,'start',side_effect=AssertionError('返回不可重启服务')):
        asyncio.run(app.start_host(None))
        assert app.main_window.content is app.table
    # A detected change must preserve the live server until explicit restart.
    with patch('weizhuomobile.app.wifi_address',return_value='192.168.2.20'),patch.object(app.host,'stop') as unchanged,patch.object(app.host,'update_address') as advertised:
        app.refresh_address(None)
        assert app.network_changed and app.start_button.text=='重启服务'
        assert '网络连接已变化' in app.status.text
        unchanged.assert_not_called();advertised.assert_not_called()
    with patch.object(app.main_window,'dialog',new=AsyncMock(return_value=False)),patch.object(app.host,'stop') as unchanged:
        asyncio.run(app.start_host(None))
        unchanged.assert_not_called();assert app.host.server is running
    with patch('weizhuomobile.app.wifi_address',return_value='192.168.1.20'):
        app.refresh_address(None)
        assert not app.network_changed and app.start_button.text=='进入大厅'
    # Automatic polling ignores a single transient address, accepts a stable pair.
    async def poll_sequence():
        with patch('weizhuomobile.app.asyncio.sleep',new=AsyncMock(side_effect=[None,None,None,asyncio.CancelledError()])),patch('weizhuomobile.app.wifi_address',side_effect=['192.168.2.30','192.168.2.30','192.168.1.20','192.168.1.20','192.168.2.30','192.168.2.30']):
            try:await app.watch_network()
            except asyncio.CancelledError:pass
        assert app.address.value=='192.168.1.20'
        with patch('weizhuomobile.app.asyncio.sleep',new=AsyncMock(side_effect=[None,None,asyncio.CancelledError()])),patch('weizhuomobile.app.wifi_address',return_value='192.168.2.30'):
            try:await app.watch_network()
            except asyncio.CancelledError:pass
        assert app.address.value=='192.168.2.30' and app.network_changed
    asyncio.run(poll_sequence())
    live['wifi']='192.168.2.30';live['hotspot']='192.168.2.30'
    def restarting():
        assert app.network_transition
        app.host.server=None
    def restarted(address):
        assert address=='192.168.2.30'
        app.host.server=SimpleNamespace(server_port=34567)
        return 'http://192.168.2.30:34567/'
    with patch.object(app.main_window,'dialog',new=AsyncMock(return_value=True)),patch.object(app.host,'stop',side_effect=restarting),patch.object(app.host,'start',side_effect=restarted):
        asyncio.run(app.start_host(None))
        assert not app.network_changed and not app.network_transition
        assert app.running_address=='192.168.2.30' and app.start_button.text=='进入大厅'
        assert app.web.url=='http://127.0.0.1:34567/'
        running=app.host.server

    with patch.object(app.main_window,'dialog',new=AsyncMock(return_value=False)),patch.object(app.host,'stop') as stopped:
        asyncio.run(app.stop_host(None))
        stopped.assert_not_called()
        assert app.host.server is running
    def stopped_host():app.host.server=None
    with patch.object(app.main_window,'dialog',new=AsyncMock(return_value=True)),patch.object(app.host,'stop',side_effect=stopped_host):
        asyncio.run(app.stop_host(None))
        assert app.main_window.content is app.launcher
        assert app.start_button.enabled and app.start_button.text=='启动服务'
        assert not app.stop_button.enabled
    print('无界面检查通过：启动反馈、异常恢复、返回不停服、网络自动检测及重启提示。')
finally:
    discovery.stop()
    if app.network_task:app.network_task.cancel()
    if app.navigation_task:app.navigation_task.cancel()
    app.host.server=None;app.resources.__exit__(None,None,None)
