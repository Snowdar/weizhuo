import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import urllib.request
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('desktop_launcher', Path(__file__).parent / 'desktop/launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class DesktopHostTests(unittest.TestCase):
    def test_resources_and_data_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            host = launcher.DesktopHost(Path(directory) / '中文 数据')
            try:
                host.start('192.168.1.20', 0)
                room = host.server.rooms.create({'game': 'mahjong', 'name': '打包测试', 'playerName': '测试'})
                with urllib.request.urlopen(f'http://127.0.0.1:{host.server.server_port}/entry-qr.png') as response:
                    self.assertTrue(response.read().startswith(b'\x89PNG'))
                host.stop()
                host.start('192.168.1.20', 0)
                self.assertEqual(host.server.rooms.repo.get(room['room'])['name'], '打包测试')
                self.assertEqual(host.server.asset_root, launcher.RESOURCE_ROOT)
            finally:
                host.stop()

    def test_non_private_ipv4_requires_local_assignment(self):
        with patch.object(launcher.socket,'socket') as native:
            self.assertEqual(launcher.validate_address('172.40.4.86'),'172.40.4.86')
            native.return_value.__enter__.return_value.bind.assert_called_once_with(('172.40.4.86',0))
        with patch.object(launcher.socket,'socket') as native:
            native.return_value.__enter__.return_value.bind.side_effect=OSError('not assigned')
            with self.assertRaises(ValueError):launcher.validate_address('172.40.4.86')

    def test_address_and_duplicate_start(self):
        for value in ['127.0.0.1', '0.0.0.0', '8.8.8.8', '169.254.1.1', 'invalid']:
            with self.assertRaises(ValueError):
                launcher.validate_address(value)
        with tempfile.TemporaryDirectory() as directory:
            host = launcher.DesktopHost(directory)
            try:
                host.start('192.168.1.20', 0)
                with self.assertRaises(ValueError):
                    host.start('192.168.1.20', 0)
                other = launcher.DesktopHost(directory)
                with self.assertRaises(OSError):
                    other.start('192.168.1.20', host.server.server_port)
            finally:
                host.stop()

    def test_frozen_smoke(self):
        self.assertTrue(launcher.smoke_check()['ok'])


    def test_default_ports_are_available_and_invitation_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            first = launcher.DesktopHost(Path(directory) / 'first')
            second = launcher.DesktopHost(Path(directory) / 'second')
            try:
                urls = [first.start('192.168.1.20'), second.start('192.168.1.20')]
                ports = [host.server.server_port for host in (first, second)]
                self.assertTrue(all(port > 0 for port in ports))
                self.assertNotEqual(*ports)
                for host, url in zip((first, second), urls):
                    self.assertEqual(url, f'http://192.168.1.20:{host.server.server_port}/')
                    with urllib.request.urlopen(f'http://127.0.0.1:{host.server.server_port}/api/bootstrap') as response:
                        self.assertEqual(json.load(response)['entry'], url)
            finally:
                first.stop()
                second.stop()


    def test_mac_browser_uses_system_launcher_and_reports_failure(self):
        with patch.object(launcher.sys, 'platform', 'darwin'), patch.object(launcher.subprocess, 'run') as run:
            launcher.open_browser('http://127.0.0.1:50383/')
            self.assertEqual(run.call_args.args[0], ['open', 'http://127.0.0.1:50383/'])
            self.assertTrue(run.call_args.kwargs['check'])
            self.assertEqual(run.call_args.kwargs['timeout'], 10)
            run.side_effect = subprocess.CalledProcessError(1, 'open')
            with self.assertRaises(subprocess.CalledProcessError):
                launcher.open_browser('http://127.0.0.1:50383/')


class DirectButtonTests(unittest.TestCase):
    class Button:
        def __init__(self):
            self.flags = set()
            self.handlers = {}
            self.invocations = 0
        def bind(self, event, handler):self.handlers[event] = handler
        def instate(self, state):
            if isinstance(state, str):raise TypeError('Tk statespec 必须是序列，不能传字符串')
            return all(item in self.flags for item in state)
        def focus_set(self):pass
        def state(self, flags):
            for flag in flags:
                if flag.startswith('!'):self.flags.discard(flag[1:])
                else:self.flags.add(flag)
        def invoke(self):self.invocations += 1
        def winfo_width(self):return 140
        def winfo_height(self):return 44

    def test_click_after_reenable_requires_no_hover_event(self):
        button = self.Button();launcher.bind_direct_button(button)
        event = SimpleNamespace(x=30, y=20)
        button.flags.add('disabled')
        button.handlers['<ButtonPress-1>'](event)
        button.handlers['<ButtonRelease-1>'](event)
        self.assertEqual(button.invocations, 0)
        button.flags.discard('disabled')
        for _ in range(3):
            self.assertEqual(button.handlers['<ButtonPress-1>'](event), 'break')
            # Simulate ttk losing its visual flags after a dialog or pointer event.
            button.flags.discard('pressed');button.flags.discard('active')
            self.assertEqual(button.handlers['<ButtonRelease-1>'](event), 'break')
        self.assertEqual(button.invocations, 3)

    def test_drag_outside_and_disable_during_press_cancel(self):
        button = self.Button();launcher.bind_direct_button(button)
        inside = SimpleNamespace(x=20, y=20)
        button.handlers['<ButtonPress-1>'](inside)
        button.handlers['<ButtonRelease-1>'](SimpleNamespace(x=150, y=20))
        button.handlers['<ButtonPress-1>'](inside)
        button.flags.add('disabled')
        button.handlers['<ButtonRelease-1>'](inside)
        button.flags.discard('disabled')
        button.handlers['<ButtonRelease-1>'](inside)
        self.assertEqual(button.invocations, 0)
        button.handlers['<Return>'](inside)
        button.handlers['<space>'](inside)
        self.assertEqual(button.invocations, 2)
