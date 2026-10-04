"""Lifecycle shared by Android and iOS; resource bundles are read-only."""
import importlib.util,ipaddress,sys,threading
from pathlib import Path

def validate_wifi_address(value):
    address=ipaddress.IPv4Address(value.strip())
    if address.is_reserved or address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
        raise ValueError('请填写手机在当前局域网中的 IPv4 地址')
    if not address.is_private:
        from weizhuomobile.network import wifi_address
        if str(address) not in (wifi_address(),wifi_address('hotspot')):
            raise ValueError('请填写手机在当前局域网中的 IPv4 地址')
    return str(address)

class Host:
    def __init__(self,resources,data):
        self.resources=Path(resources);self.data=Path(data);self.server=None;self.thread=None
    def start(self,address,port=0):
        address=validate_wifi_address(address)
        if self.server:raise ValueError('服务已运行，请先停止再切换网络')
        sys.path.insert(0,str(self.resources))
        # Chaquopy compiles Android app modules to sourceless .pyc files.
        entry=next((self.resources/name for name in ('server.py','server.pyc') if (self.resources/name).is_file()),None)
        if entry is None:raise RuntimeError('安装包缺少服务入口，请重新构建客户端')
        spec=importlib.util.spec_from_file_location('weizhuo_mobile_server',entry)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.server=module.make_server(port,data_dir=self.data,resource_root=self.resources,lan_address=address,service_device='phone')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return f'http://{address}:{self.server.server_port}/'
    def stop(self):
        if not self.server:return
        server=self.server;server.shutdown();server.server_close();self.thread.join(timeout=3)
        self.server=None;self.thread=None
    def update_address(self,address):
        address=validate_wifi_address(address)
        if self.server:self.server.lan_address=address
        return address
