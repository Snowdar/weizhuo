"""Local IPv4 discovery without Internet probes or fixed hotspot gateways."""
import ipaddress
import sys
from .platforms import is_android


def select_address(interfaces, mode='wifi'):
    """Only known Wi-Fi / hotspot interfaces; never select cellular or VPN."""
    candidates=[]
    for name,value in interfaces:
        name=name.lower()
        wifi=name.startswith(('wlan','wifi')) or (name.startswith('en') and name[2:].isdigit())
        hotspot=name.startswith(('bridge','ap','swlan','softap'))
        if not (wifi or hotspot):continue
        try:address=ipaddress.IPv4Address(value)
        except ValueError:continue
        if address.is_reserved or address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:continue
        # A bridge may belong to another network: never silently substitute it
        # for the Wi-Fi client interface in same-Wi-Fi mode.
        if mode=='hotspot' and not hotspot:continue
        if mode!='hotspot' and not wifi:continue
        priority=0
        candidates.append((priority,name,str(address)))
    return min(candidates)[2] if candidates else ''


def wifi_address(mode='wifi'):
    interfaces=[]
    try:
        if is_android():
            from java import jclass
            collections=jclass('java.util.Collections')
            enumeration=jclass('java.net.NetworkInterface').getNetworkInterfaces()
            # Keep Enumeration dispatch in Java; vendor implementations may be
            # inaccessible anonymous classes to the Python bridge.
            if enumeration is not None:
                for interface in collections.list(enumeration).toArray():
                    if not interface.isUp():continue
                    for address in collections.list(interface.getInetAddresses()).toArray():
                        interfaces.append((str(interface.getName()),str(address.getHostAddress())))
        elif sys.platform=='ios':
            import ctypes,socket
            class IfAddrs(ctypes.Structure):pass
            IfAddrs._fields_=[('next',ctypes.POINTER(IfAddrs)),('name',ctypes.c_char_p),('flags',ctypes.c_uint),('addr',ctypes.c_void_p),('netmask',ctypes.c_void_p),('dst',ctypes.c_void_p),('data',ctypes.c_void_p)]
            libc=ctypes.CDLL(None);head=ctypes.POINTER(IfAddrs)()
            libc.getifaddrs.argtypes=[ctypes.POINTER(ctypes.POINTER(IfAddrs))];libc.freeifaddrs.argtypes=[ctypes.POINTER(IfAddrs)]
            if libc.getifaddrs(ctypes.byref(head))!=0:return ''
            try:
                node=head
                while node:
                    entry=node.contents
                    if entry.name and entry.addr and entry.flags & 1:
                        raw=ctypes.string_at(entry.addr,8)
                        if raw[1]==socket.AF_INET:
                            interfaces.append((entry.name.decode(),socket.inet_ntoa(raw[4:8])))
                    node=entry.next
            finally:libc.freeifaddrs(head)
    except Exception as error:
        # Java SocketException/SecurityException are not Python OSError subclasses.
        print('围桌网络地址检测失败：'+str(error),flush=True)
    if sys.platform=='ios':
        # Retain local interface evidence when discovery fails on a device.
        snapshot=repr(interfaces)
        if getattr(wifi_address,'_last_interfaces',None)!=snapshot:
            wifi_address._last_interfaces=snapshot
            try:
                from pathlib import Path
                (Path.home()/'Documents'/'network-diagnostic.txt').write_text(snapshot,encoding='utf-8')
            except OSError:pass
    address=select_address(interfaces,mode)
    if address or not is_android() or mode=='hotspot':return address
    # Interface names can differ on vendor builds; identify Wi-Fi by transport.
    try:
        from java import jclass
        activity=jclass('org.beeware.android.MainActivity').singletonThis
        manager=activity.getSystemService(jclass('android.content.Context').CONNECTIVITY_SERVICE)
        capabilities=jclass('android.net.NetworkCapabilities')
        for network in manager.getAllNetworks():
            caps=manager.getNetworkCapabilities(network)
            if caps is None or not caps.hasTransport(capabilities.TRANSPORT_WIFI):continue
            links=manager.getLinkProperties(network)
            if links is None:continue
            for link in links.getLinkAddresses().toArray():
                interfaces.append(('wifi',str(link.getAddress().getHostAddress())))
    except Exception as error:
        print('围桌 Wi-Fi 地址检测失败：'+str(error),flush=True)
    return select_address(interfaces,mode)

def keep_screen_awake(enabled):
    """Only while hosting; does not extend OS background execution."""
    try:
        if sys.platform=='ios':
            from rubicon.objc import ObjCClass
            ObjCClass('UIApplication').sharedApplication.idleTimerDisabled=enabled
        elif is_android():
            from java import jclass
            window=jclass('org.beeware.android.MainActivity').singletonThis.getWindow()
            flag=jclass('android.view.WindowManager$LayoutParams').FLAG_KEEP_SCREEN_ON
            if enabled:window.addFlags(flag)
            else:window.clearFlags(flag)
        return True
    except Exception:return False


def service_network_state(wifi,hotspot,mode):
    """Losing Wi-Fi selects hotspot setup; this never enables OS tethering."""
    mode=mode if wifi else '本机热点'
    return mode,bool(wifi),hotspot if mode=='本机热点' else wifi
