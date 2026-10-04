"""Desktop host launcher; packaged resources never contain mutable room data."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import queue
import sys
import tempfile
import threading
import urllib.request
import webbrowser

RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(RESOURCE_ROOT))
sys.path.insert(0, str(RESOURCE_ROOT / 'vendor'))
import server
from announcer import LocalAnnouncer


def data_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Weizhuo'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Weizhuo'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'weizhuo'


def validate_address(value):
    address = ipaddress.IPv4Address(value.strip())
    if address.is_reserved or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
        raise ValueError('请填写本机在局域网中的 IPv4 地址')
    if not address.is_private:
        # Public-looking IPv4 is valid when assigned to a local interface.
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as local:
                local.bind((str(address),0))
        except OSError as error:
            raise ValueError('请填写本机在局域网中的 IPv4 地址') from error
    return str(address)


def suggested_address():
    value = server.detect_lan_ip()
    if value != '127.0.0.1':
        return value
    # Query routing without sending a packet; the address can be edited for Wi-Fi.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('1.1.1.1', 80))
            return validate_address(probe.getsockname()[0])
    except (OSError, ValueError):
        return ''


class DesktopHost:
    def __init__(self, data=None):
        self.data = Path(data) if data is not None else data_directory()
        self.server = None
        self.thread = None

    def start(self, address, port=0):
        address = validate_address(address)
        if self.server:
            raise ValueError('服务已经运行')
        self.server = server.make_server(port, data_dir=self.data, resource_root=RESOURCE_ROOT, lan_address=address)
        voice=RESOURCE_ROOT/'Voice'
        if not voice.exists():voice=RESOURCE_ROOT/'mobile/.voice-assets/Voice'
        if voice.exists():self.server.announcer=LocalAnnouncer(voice)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.1), daemon=True)
        self.thread.start()
        return f'http://{address}:{self.server.server_port}/'

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None
            self.thread = None


def smoke_check():
    """Exercise the frozen server and shipped assets without touching user rooms."""
    with tempfile.TemporaryDirectory(prefix='weizhuo-package-') as data:
        host = DesktopHost(data)
        try:
            host.start('192.168.1.20', 0)
            base = f'http://127.0.0.1:{host.server.server_port}/'
            def read(path):
                with urllib.request.urlopen(base + path, timeout=5) as response:
                    return response.read()
            assert b'<html' in read('')
            assert read('entry-qr.png').startswith(b'\x89PNG')
            assert read('assets/weizhuo-logo.png').startswith(b'\x89PNG')
            state = json.loads(read('api/bootstrap'))
            assert '192.168.1.20' in state['entry']
            room = host.server.rooms.create({'game': 'mahjong', 'name': '打包自检', 'playerName': '测试'})
            if getattr(sys,'frozen',False):
                import io,wave
                assert state['voiceChoices']==[0,1,2,3]
                for voice in (1,2,3):
                    payload=json.dumps({**room,'voice':voice,'text':'三号玩家跟注二十分。三号玩家弃牌。本局已结算。'}).encode()
                    req=urllib.request.Request(base+'api/voice',data=payload,headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=30) as response:
                        assert response.headers['Cache-Control']=='no-store'
                        with wave.open(io.BytesIO(response.read())) as wav:assert wav.getnframes()>1000

            host.stop()
            host.start('192.168.1.20', 0)
            assert host.server.rooms.repo.get(room['room'])['name'] == '打包自检'
        finally:
            host.stop()
    return {'ok': True, 'platform': sys.platform, 'checks': ['HTTP', 'QR', 'assets', 'private data', 'restart']+(['four voices and WAV synthesis'] if getattr(sys,'frozen',False) else [])}


def open_browser(url):
    """Use the OS launcher in a frozen Mac app instead of Python's AppleScript controller."""
    if sys.platform == 'darwin':
        subprocess.run(['open', url], check=True, capture_output=True, timeout=10)
    elif sys.platform == 'win32':
        os.startfile(url)
    elif not webbrowser.open(url):
        raise RuntimeError('系统未找到可用的浏览器')


def bind_direct_button(button):
    """Invoke from the press/release pair, independent of Tk's hover state.

    Native dialogs and disabled-to-enabled transitions can interrupt ttk's
    pressed/active flags. Keep drag cancellation and disabled guards explicit.
    """
    pressed = False

    def down(event):
        nonlocal pressed
        pressed = not button.instate(('disabled',))
        if pressed:
            button.focus_set()
            button.state(['pressed', 'active'])
        return 'break'

    def up(event):
        nonlocal pressed
        invoke = pressed and not button.instate(('disabled',)) and 0 <= event.x < button.winfo_width() and 0 <= event.y < button.winfo_height()
        pressed = False
        button.state(['!pressed'])
        if invoke:
            button.invoke()
        return 'break'

    def key(event):
        if not button.instate(('disabled',)):
            button.invoke()
        return 'break'

    button.bind('<ButtonPress-1>', down)
    button.bind('<ButtonRelease-1>', up)
    button.bind('<space>', key)
    button.bind('<Return>', key)


def gui(exit_smoke=None, data=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    root = tk.Tk()
    root.title('围桌')
    root.geometry('480x620')
    root.minsize(440, 580)
    root.configure(background='#f7f7ed')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background='#f7f7ed', foreground='#28513f', font=('', 13))
    style.configure('TEntry', fieldbackground='#fffef9', padding=10)
    style.configure('TButton', padding=(16, 12), background='#e8eee2', foreground='#28513f', bordercolor='#bccdb6', font=('', 16, 'bold'), focusthickness=1, focuscolor='#587550')
    style.map('TButton', background=[('disabled', '#e9ece5'), ('pressed', '#b9ceb0'), ('active', '#d0e0c7')], foreground=[('disabled', '#919a8d')])
    style.configure('Primary.TButton', background='#dfb775', foreground='#493819', bordercolor='#c79c59')
    style.map('Primary.TButton', background=[('disabled', '#e9ece5'), ('pressed', '#bd904b'), ('active', '#edc98b')], foreground=[('disabled', '#919a8d')])
    style.configure('Small.TButton', font=('', 12), padding=(10, 8))
    host = DesktopHost(data)
    body = ttk.Frame(root, padding=(32, 24))
    body.pack(fill='both', expand=True)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)
    body.rowconfigure(9, weight=1)
    # Tk keeps the image reference for the lifetime of the service homepage.
    image = tk.PhotoImage(file=str(RESOURCE_ROOT / 'static/assets/weizhuo-logo.png'))
    image = image.subsample(max(1, image.width() // 128))
    ttk.Label(body, image=image).grid(row=1, column=0, pady=(0, 12))
    ttk.Label(body, text='围桌', font=('', 30, 'bold')).grid(row=2, column=0)
    ttk.Label(body, text='线下游戏，线上记分', foreground='#60776b', font=('', 16)).grid(row=3, column=0, pady=(8, 26))
    ttk.Label(body, text='本机局域网地址', foreground='#60776b').grid(row=4, column=0, sticky='w', pady=(0, 8))
    network = ttk.Frame(body)
    network.grid(row=5, column=0, sticky='ew', pady=(0, 18))
    network.columnconfigure(0, weight=1)
    address = tk.StringVar(value=suggested_address())
    entry = ttk.Entry(network, textvariable=address)
    entry.grid(row=0, column=0, sticky='ew')
    status = tk.StringVar(value='连接同一 Wi-Fi 或服务设备热点 Wi-Fi。\n无需互联网。\n主持期间保持电脑唤醒。')
    actions = ttk.Frame(body)
    actions.grid(row=6, column=0, sticky='ew')
    actions.columnconfigure((0, 1), weight=1, uniform='actions')
    ttk.Label(body, textvariable=status, wraplength=380, foreground='#60776b', justify='left').grid(row=7, column=0, sticky='w', pady=(18, 8))
    ttk.Label(body, text='返回此页不会停服；关闭应用会停止服务。', foreground='#60776b', font=('', 11)).grid(row=8, column=0, sticky='w')
    ttk.Label(body, text='娱乐为主 · 远离赌博', foreground='#60776b', font=('', 12)).grid(row=10, column=0, pady=(16, 0))
    version = server.app_version(RESOURCE_ROOT)
    ttk.Label(body, text=f'版本 {version}' if version else '版本信息不可用', foreground='#60776b', font=('', 11)).grid(row=11, column=0, pady=(6, 0))
    results = queue.Queue()
    workers = []
    closing = False
    busy = False
    pump_id = None
    poll_ticks = 0
    detected_address = address.get()
    pending_address = None
    running_address = ''
    network_changed = False
    network_polling = False
    def task(kind, action):
        def run():
            try:results.put((kind, action(), None))
            except Exception as error:results.put((kind, None, error))
        worker = threading.Thread(target=run, daemon=False)
        workers.append(worker)
        worker.start()
    def controls(working=False):
        nonlocal busy
        busy = working
        entry.configure(state='disabled' if host.server or working else 'normal')
        start_button.configure(state='disabled' if working else 'normal', text=('重启服务' if network_changed else '进入大厅') if host.server else '启动服务')
        stop_button.configure(state='normal' if host.server and not working else 'disabled')
    def open_lobby():
        if not host.server or busy:return
        controls(True)
        start_button.configure(text='正在打开…')
        status.set('正在打开浏览器大厅…')
        task('browser', lambda: open_browser(f'http://127.0.0.1:{host.server.server_port}/'))
    def start():
        if busy:return
        if host.server:
            if network_changed:
                if not address.get():messagebox.showinfo('未连接局域网', '连接 Wi-Fi 或热点后地址会自动更新。', parent=root);return
                if not messagebox.askyesno('重启服务？','网络已变化。重启会暂时断开其他玩家，房间与积分保留；请重新分享二维码。',parent=root):return
                value=address.get()
                controls(True);status.set('正在重启服务…')
                task('start',lambda:(host.stop(),host.start(value))[1])
                return
            open_lobby()
            return
        value = address.get()
        controls(True)
        start_button.configure(text='正在启动…')
        status.set('正在启动局域网服务…')
        task('start', lambda: host.start(value))
    def stop():
        if busy or not host.server:return
        if not messagebox.askyesno('关闭服务？', '其他玩家将暂时断开；房间和积分会保留。', parent=root):return
        controls(True)
        stop_button.configure(text='正在关闭…')
        status.set('正在关闭服务…')
        task('stop', host.stop)
    start_button = ttk.Button(actions, text='启动服务', style='Primary.TButton', command=start)
    start_button.grid(row=0, column=0, sticky='ew', padx=(0, 6))
    stop_button = ttk.Button(actions, text='关闭服务', state='disabled', command=stop)
    stop_button.grid(row=0, column=1, sticky='ew', padx=(6, 0))
    for button in (start_button, stop_button):bind_direct_button(button)
    def pump():
        nonlocal pump_id,poll_ticks,detected_address,pending_address,running_address,network_changed,network_polling
        workers[:]=[worker for worker in workers if worker.is_alive()]
        pump_id = None
        if closing:return
        while True:
            try:kind, value, error = results.get_nowait()
            except queue.Empty:break
            if kind=='network':
                network_polling=False
                if busy or error:continue
                if value==detected_address:pending_address=None;continue
                if value!=pending_address:pending_address=value;continue
                detected_address=value;pending_address=None;address.set(value)
                network_changed=bool(host.server and value!=running_address)
                controls()
                if network_changed:status.set('网络地址已变化：'+(value or '未连接局域网')+'\n请重启服务，重新分享二维码，让玩家重新扫码加入。房间与积分保留。')
                else:status.set('本机地址已自动更新。' if not host.server else '服务运行中 · 邀请地址\n'+f'http://{running_address}:{host.server.server_port}/')
                continue
            controls()
            stop_button.configure(text='关闭服务')
            if error:
                status.set(('服务仍在运行。\n' if host.server else '') + '操作失败：' + str(error))
                messagebox.showerror('操作失败', str(error), parent=root)
            elif kind == 'start':
                running_address=host.server.lan_address;network_changed=False;controls()
                status.set('服务已启动 · 邀请地址\n' + value+'\n请分享当前二维码，原玩家重新扫码加入。')
                open_lobby()
            elif kind == 'stop':
                running_address='';network_changed=False;controls();status.set('服务已关闭，房间与积分已保存。')
            else:status.set('服务运行中 · 邀请地址\n' + f'http://{address.get()}:{host.server.server_port}/')
        poll_ticks+=1
        if poll_ticks%25==0 and not busy and not network_polling:
            network_polling=True
            task('network',suggested_address)
        pump_id = root.after(80, pump)
    def close():
        nonlocal closing
        if closing:return
        if busy:
            messagebox.showinfo('请稍候', '正在处理服务操作，请完成后再退出。', parent=root)
            return
        if host.server and not messagebox.askyesno('退出围桌？', '退出会停止服务，房间与积分会保存。', parent=root):return
        closing = True
        if pump_id is not None:
            root.after_cancel(pump_id)
        # Unwind native menu / accessibility callbacks before leaving Tk.
        root.after_idle(root.quit)
    root.protocol('WM_DELETE_WINDOW', close)
    if sys.platform == 'darwin':root.createcommand('::tk::mac::Quit', close)
    pump_id = root.after(80, pump)
    if exit_smoke:
        host.start('192.168.1.20')
        # Isolated automated teardown test, never reads real application data.
        messagebox.askyesno = lambda *args, **kwargs: True
        if exit_smoke == 'menu' and sys.platform == 'darwin':
            root.after(300, lambda: root.tk.call('::tk::mac::Quit'))
        else:
            root.after(300, close)
    try:root.mainloop()
    finally:
        for worker in workers:worker.join(timeout=12)
        host.stop()
        root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='围桌桌面启动器')
    parser.add_argument('--self-test-report', type=Path)
    parser.add_argument('--ui-exit-smoke', choices=('window', 'menu'))
    options = parser.parse_args()
    if options.self_test_report:
        options.self_test_report.write_text(json.dumps(smoke_check(), ensure_ascii=False), encoding='utf-8')
    elif options.ui_exit_smoke:
        with tempfile.TemporaryDirectory(prefix="weizhuo-ui-exit-") as data:
            gui(options.ui_exit_smoke, data)
    else:
        gui()
