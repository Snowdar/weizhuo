import asyncio
import json
import sys
import textwrap
import traceback
from pathlib import Path
from importlib.resources import files,as_file
import toga
from toga.style import Pack
from toga.style.pack import COLUMN,ROW
from .appearance import BG,PANEL,TEXT,MUTED,SECONDARY,GOLD,GOLD_TEXT,style_native_controls,install_background,configure_webview,fit_fullscreen_web,web_safe_area,web_keyboard_state,lock_table_scroll
from .bootstrap import prepare_locale
from .host import Host
from .speech import Speaker
from . import ios_scene
from .network import wifi_address,keep_screen_awake,service_network_state
from .platforms import is_android

_voice_diagnostics=[]
_diagnostic_path=None
def voice_diagnostic(message):
    if sys.platform!='ios' and not is_android():return
    print('围桌诊断：'+message,flush=True)
    if _voice_diagnostics and _voice_diagnostics[-1]==message:return
    _voice_diagnostics.append(message)
    del _voice_diagnostics[:-20]
    try:
        path=_diagnostic_path or Path.home()/'Documents'/'voice-diagnostic.txt'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('\n'.join(_voice_diagnostics),encoding='utf-8')
    except OSError:pass

def wrap_service_text(text,width,font_size=13):
    """Toga Label does not soft-wrap; bound each line by its display width."""
    import unicodedata
    limit=max(8,(width-8)/font_size)
    lines=[]
    for paragraph in str(text).split('\n'):
        line='';used=0
        for char in paragraph:
            weight=1 if unicodedata.east_asian_width(char) in ('W','F') else .62
            if line and used+weight>limit:
                lines.append(line.rstrip());line='';used=0
            line+=char;used+=weight
        lines.append(line.rstrip())
    if len(lines)>6:lines=lines[:5]+[lines[5][:-1]+'…']
    return '\n'.join(lines)

class Weizhuo(toga.App):
    def startup(self):
        global _diagnostic_path
        _diagnostic_path=self.paths.data/'startup-diagnostic.txt'
        voice_diagnostic('startup: begin')
        try:
            self.startup_ui()
        except Exception:
            voice_diagnostic('startup failed:\n'+traceback.format_exc())
            # Preserve an actionable error screen instead of silently exiting.
            if not is_android():raise
            try:
                if not self.main_window:self.main_window=toga.MainWindow(title='围桌')
                detail=traceback.format_exc().strip().splitlines()[-1]
                self.main_window.content=toga.Box(children=[
                    toga.Label('围桌启动失败',style=Pack(font_size=22,margin_bottom=16)),
                    toga.Label(wrap_service_text(detail,300),style=Pack(font_size=13,margin_bottom=16)),
                    toga.Label('请提供此页截图或 USB 调试日志。',style=Pack(font_size=13)),
                ],style=Pack(direction=COLUMN,margin=20))
                self.main_window.show()
            except Exception:
                voice_diagnostic('startup error screen failed:\n'+traceback.format_exc())
                raise

    def startup_ui(self):
        self.resources=as_file(files('weizhuomobile.runtime'))
        self.host=Host(self.resources.__enter__(),self.paths.data/'rooms')
        # Toga iOS MainWindow inserts a native navigation/title bar.
        # A plain Window uses RootContainer and retains the status-bar safe offset.
        window_class=toga.Window if sys.platform=='ios' else toga.MainWindow
        self.main_window=window_class(title='围桌')
        if sys.platform=='ios':
            from toga_iOS.libs import UIColor
            background=UIColor.colorWithRed(241/255,green=243/255,blue=235/255,alpha=1)
            self.main_window._impl.native.backgroundColor=background
            self.main_window._impl.container.native.backgroundColor=background
        self.speaker=Speaker()
        voice_diagnostic('startup: speech adapter ready')
        self.navigation_task=None
        self.restart_notice=''
        self.network_mode='同一 Wi-Fi'
        self.wifi_button=toga.Button('同一 Wi-Fi',on_press=lambda widget:self.select_network_mode('同一 Wi-Fi'),style=Pack(flex=1,height=44,font_size=15,font_weight='bold',background_color=GOLD,color=GOLD_TEXT))
        self.hotspot_button=toga.Button('本机热点',on_press=lambda widget:self.select_network_mode('本机热点'),style=Pack(flex=1,height=44,font_size=15,font_weight='bold',background_color=SECONDARY,color=TEXT))
        self.detected_address=wifi_address();self.running_address='';self.running_network_mode='';self.network_changed=False;self.network_transition=False
        voice_diagnostic('startup: detected Wi-Fi IPv4='+self.detected_address)
        self.address=toga.TextInput(value=self.detected_address,placeholder='自动检测本机局域网 IPv4',style=Pack(flex=1,height=44,font_size=16,background_color=PANEL,color=TEXT))
        self.status_message='朋友连接同一 Wi-Fi 或本机热点。\n仅需局域网，无需互联网。\n主持时保持 App 在前台。'
        self.status=toga.Label('朋友连接同一 Wi-Fi 或本机热点。\n仅需局域网，无需互联网。\n主持时保持 App 在前台。',style=Pack(margin_top=16,height=96,font_size=13,color=MUTED))
        self.start_button=toga.Button('启动服务',on_press=self.start_host,style=Pack(flex=1,height=50,font_size=16,font_weight='bold',background_color=GOLD,color=GOLD_TEXT))
        self.stop_button=toga.Button('关闭服务',on_press=self.stop_host,enabled=False,style=Pack(flex=1,height=50,font_size=16,font_weight='bold',background_color=SECONDARY,color=TEXT))
        logo=toga.ImageView(toga.Image(str(files('weizhuomobile.runtime')/'static/assets/weizhuo-logo.png')),style=Pack(width=88,height=88,margin_bottom=12))
        self.web=toga.WebView(style=Pack(flex=1))
        configure_webview(self.web)
        voice_diagnostic('startup: web configured')
        self.service_controls=toga.Box(children=[
            toga.Label('连接方式',style=Pack(font_size=14,color=MUTED,margin_bottom=8)),
            toga.Box(children=[self.wifi_button,self.hotspot_button],style=Pack(direction=ROW,gap=10,margin_bottom=16)),
            toga.Label('本机局域网地址',style=Pack(font_size=14,color=MUTED,margin_bottom=8)),
            toga.Box(children=[self.address],style=Pack(direction=ROW,margin_bottom=18)),
            toga.Box(children=[self.start_button,self.stop_button],style=Pack(direction=ROW,gap=12)),
            self.status,
        ],style=Pack(direction=COLUMN,margin=16))
        self.service_card=toga.Box(children=[self.service_controls],style=Pack(direction=COLUMN,background_color=PANEL))
        try:
            build_info=json.loads((files('weizhuomobile.runtime')/'resources/build-info.json').read_text())
            version_text=f"版本 {build_info['version']}.{build_info.get('prerelease', 'a'+str(build_info['build']))}"
        except (OSError,ValueError,KeyError,TypeError):
            version_text='版本信息不可用'
        self.version_label=toga.Label(version_text,style=Pack(font_size=11,text_align='center',color=MUTED,margin_top=6))
        self.service_page=toga.Box(children=[
            toga.Box(style=Pack(flex=1)),
            toga.Box(children=[toga.Box(style=Pack(flex=1)),logo,toga.Box(style=Pack(flex=1))],style=Pack(direction=ROW)),
            toga.Label('围桌',style=Pack(font_size=26,font_weight='bold',text_align='center',color='#234c3d',margin_bottom=8)),
            toga.Label('线下游戏，线上记分',style=Pack(font_size=15,text_align='center',color=MUTED,margin_bottom=8)),
            toga.Label('仅需局域网 · 无需互联网',style=Pack(font_size=13,text_align='center',color=MUTED,margin_bottom=20)),
            toga.Box(children=[toga.Box(style=Pack(flex=1)),self.service_card,toga.Box(style=Pack(flex=1))],style=Pack(direction=ROW)),
            toga.Box(style=Pack(flex=1)),
            toga.Label('娱乐为主 · 远离赌博',style=Pack(font_size=13,text_align='center',color=MUTED,margin_top=16)),
            self.version_label,
        ],style=Pack(direction=COLUMN,margin=20,flex=1))
        self.launcher=toga.Box(children=[self.service_page],style=Pack(direction=COLUMN,flex=1))
        style_native_controls([self.wifi_button,self.hotspot_button,self.start_button,self.stop_button],self.address,self.service_card)
        # A full-height WebView; service navigation is a collapsed in-page control.
        self.table=toga.Box(children=[self.web],style=Pack(direction=COLUMN,flex=1))
        if sys.platform=='ios':
            container=self.main_window._impl.container
            original=container.on_refresh
            def refreshed(container):
                original(container)
                if self.main_window.content is self.table:
                    fit_fullscreen_web(self.main_window,self.web)
            container.on_refresh=refreshed
        self.main_window.on_resize=self.service_resized
        self.main_window.content=self.launcher
        voice_diagnostic('startup: home content assigned')
        self.main_window.show()
        voice_diagnostic('startup: home window shown')
        self.fit_service_page()
        self.background_view=install_background(self.main_window)
        voice_diagnostic('startup: home background installed')
        self.on_exit=self.exit_host
        self.refresh_address(None)
        self.network_task=self.loop.create_task(self.watch_network())
        if sys.platform=='ios':self.loop.create_task(self.inspect_home_layout())

    async def inspect_home_layout(self):
        await asyncio.sleep(1)
        try:
            window=self.main_window._impl.native
            for name,native in [('window',window),('container',self.main_window._impl.container.native),('launcher',self.launcher._impl.native),('page',self.service_page._impl.native),('card',self.service_card._impl.native)]:
                frame=native.frame
                voice_diagnostic(f'layout {name}: {frame.origin.x},{frame.origin.y} {frame.size.width}x{frame.size.height} hidden={native.isHidden()}')
            voice_diagnostic(f'window scene={window.windowScene is not None} key={window.isKeyWindow()}')
        except Exception:voice_diagnostic('layout failed:\n'+traceback.format_exc())
    def dismiss_address_input(self):
        if sys.platform=='ios':
            self.address._impl.native.resignFirstResponder()

    async def start_host(self,widget):
        restarted=bool(self.host.server and self.network_changed)
        self.dismiss_address_input()
        detected=wifi_address('hotspot' if self.network_mode=='本机热点' else 'wifi')
        if not detected:
            self.refresh_address(None)
            return
        if self.host.server and self.network_changed:
            if not self.address.value:self.set_status('未检测到局域网地址。\n连接 Wi-Fi 或开启热点后会自动更新。');return
            if not await self.main_window.dialog(toga.ConfirmDialog('重启服务？','网络已变化。重启会暂时断开其他玩家，房间和积分保留；之后请重新分享二维码。')):return
            self.network_transition=True
            self.start_button.enabled=False
            try:await asyncio.to_thread(self.host.stop)
            except Exception as error:
                self.network_transition=False;self.start_button.enabled=True;self.set_status('重启失败：'+str(error));return
        if self.host.server:
            self.show_table(None)
            return
        self.start_button.enabled=False
        self.network_transition=True
        self.set_status('正在启动服务…')
        try:
            url=await asyncio.to_thread(self.host.start,self.address.value)
            self.running_address=self.address.value;self.running_network_mode=self.network_mode;self.network_changed=False
            self.restart_notice='服务已重启：重新分享二维码，玩家重新扫码加入。' if restarted else ''
            self.set_status('服务运行中\n'+url+'\n'+('请重新分享二维码，玩家重新扫码加入。' if restarted else '连接同一 Wi-Fi 或本机热点后扫码。')+'\n主持期间保持 App 在前台。')
            self.web.url=f'http://127.0.0.1:{self.host.server.server_port}/'
            print('围桌服务已启动：'+url,flush=True)
            self.stop_button.enabled=True
            self.start_button.text="进入大厅"
            self.start_button.enabled=True
            awake=keep_screen_awake(True)
            if not awake:self.set_status(self.status_message + "\n请在系统中保持屏幕常亮。")
            self.show_table(None)
        except Exception as error:
            traceback.print_exc()
            self.set_status('启动失败：\n'+textwrap.fill(str(error),width=20));self.start_button.enabled=True
            self.stop_button.enabled=bool(self.host.server)
            self.start_button.text='重启服务' if self.host.server and self.network_changed else ('进入大厅' if self.host.server else '启动服务')
        finally:self.network_transition=False
    async def stop_host(self,widget):
        if not await self.main_window.dialog(toga.ConfirmDialog('关闭服务？','其他玩家将暂时断开；房间与积分仍会保存。')):return
        self.stop_button.enabled=False
        self.start_button.enabled=False
        self.set_status('正在关闭服务…')
        self.network_transition=True
        try:
            await asyncio.to_thread(self.host.stop)
        except Exception as error:
            traceback.print_exc()
            self.stop_button.enabled=True
            self.start_button.enabled=True
            self.set_status('关闭失败：\n'+textwrap.fill(str(error),width=20))
            return
        finally:self.network_transition=False
        self.speaker.stop()
        self.running_address='';self.network_changed=False
        keep_screen_awake(False)
        self.stop_button.enabled=False;self.start_button.enabled=True;self.start_button.text='启动服务';self.set_status('服务已关闭。\n房间与积分已保存。')
        self.show_service(None)
    def show_table(self,widget):
        if not self.host.server:return
        self.main_window.content=self.table
        fit_fullscreen_web(self.main_window,self.web)
        if self.navigation_task is None or self.navigation_task.done():
            self.navigation_task=self.loop.create_task(self.watch_service_navigation())
    def show_service(self,widget):
        self.speaker.stop()
        lock_table_scroll(self.web,False)
        self.main_window.content=self.launcher
        self.fit_service_page()
        if self.navigation_task:
            self.navigation_task.cancel()
            self.navigation_task=None
    async def watch_service_navigation(self):
        script=(files('weizhuomobile')/'service_navigation.js').read_text().replace('__NATIVE_SPEECH__','true' if self.speaker.native else 'false').replace('__DUAL_VOICE__','true' if self.speaker.offline else 'false')
        while self.main_window.content is self.table:
            try:
                # Toga has no cross-platform message bridge. Only local hosted pages
                # receive this UI; returning never changes the URL or stops the host.
                result=await self.web.evaluate_javascript(script.replace("__VOICE_CHOICES__",json.dumps(self.speaker.choices)).replace("__SPEECH_READY__","true" if self.speaker.ready else "false").replace("__SAFE_AREA__",json.dumps(web_safe_area(self.main_window))).replace("__KEYBOARD__",json.dumps(web_keyboard_state(self.web))).replace("__VOICE_CHOICE__",str(self.speaker.voice)).replace("__VOICE_STATUS__",json.dumps(self.speaker.status,ensure_ascii=False)).replace("__NETWORK_NOTICE__",json.dumps("网络已变化：返回重启服务，再分享二维码让玩家重新扫码加入。" if self.network_changed else self.restart_notice,ensure_ascii=False)))
                voice_diagnostic('bridge='+type(result).__name__+' native='+str(bool(self.speaker.native))+' status='+self.speaker.status)
                if isinstance(result,dict):
                    if sys.platform == 'ios':
                        lock_table_scroll(self.web,bool(result.get('tableLocked',False)))
                    self.speaker.set_voice(result.get('voice'))
                    if result.get('quiet') and not result.get('audition'):self.speaker.stop()
                    elif result.get('speech'):
                        voice_diagnostic('speech received')
                        self.speaker.say(result['speech'])
                        voice_diagnostic('speech submitted')
                if isinstance(result,dict) and result.get('returned'):
                    self.show_service(None)
                    return
            except Exception as error:
                voice_diagnostic('error='+repr(error))
                print('围桌网页播报桥接失败：'+str(error),flush=True)
                # Page may be between loads; retry after it becomes ready.
            await asyncio.sleep(.3)
    def service_resized(self,window,**kwargs):
        # Android delivers on_resize before committing its new container size.
        # Schedule after the native layout pass, instead of reading stale width.
        self.loop.call_soon(self.fit_service_page)
    def fit_service_page(self):
        width=self.main_window.size.width
        if sys.platform=='ios':width=self.main_window._impl.native.bounds.size.width
        if width<=0:return  # Android has no measured size during startup.
        layout_key=(round(width,2),self.status_message)
        if getattr(self,'_service_layout_key',None)==layout_key:return
        self._service_layout_key=layout_key
        card_width=max(180,min(420,width-40))
        self.service_card.style.width=card_width
        self.service_controls.style.width=card_width-32
        self.status.style.width=card_width-32
        self.status.text=wrap_service_text(self.status_message,card_width-32)
    def set_status(self,message):
        self.status_message=str(message)
        self.fit_service_page()
    def select_network_mode(self,mode):
        self.dismiss_address_input()
        if mode==self.network_mode:return
        self.network_mode=mode
        for value,button in [('同一 Wi-Fi',self.wifi_button),('本机热点',self.hotspot_button)]:
            selected=value==mode
            button.style.background_color=GOLD if selected else SECONDARY
            button.style.color=GOLD_TEXT if selected else TEXT
        self.refresh_address(None)
    def refresh_address(self,widget,addresses=None):
        wifi,hotspot_address=addresses or (wifi_address(),wifi_address('hotspot'))
        mode,wifi_available,address=service_network_state(wifi,hotspot_address,self.network_mode)
        self.network_mode=mode
        self.wifi_button.enabled=wifi_available
        for value,button in [('同一 Wi-Fi',self.wifi_button),('本机热点',self.hotspot_button)]:
            selected=value==mode
            button.style.background_color=GOLD if selected else SECONDARY
            button.style.color=GOLD_TEXT if selected else TEXT
        self._network_snapshot=(wifi,hotspot_address)
        self.address.value=address
        self.detected_address=address
        hotspot=mode=='本机热点'
        self.start_button.enabled=bool(address)
        if self.host.server:
            self.network_changed=address!=self.running_address or self.network_mode!=self.running_network_mode
            self.start_button.text='重启服务' if self.network_changed else '进入大厅'
            self.start_button.enabled=bool(address) or not self.network_changed
            if self.network_changed:
                message=('未检测到可用热点接口。\n请在系统设置开启个人热点，\n并让朋友连接。\n' if hotspot and not address else '网络连接已变化：\n'+(address or '未连接 Wi-Fi')+'\n')
                self.set_status(message+'网络就绪后请重启服务。\n重新分享二维码，玩家重新扫码加入。\n房间与积分保留。')
            else:self.set_status(f'服务运行中\nhttp://{address}:{self.host.server.server_port}/\n仅需局域网，无需互联网。')
            return
        if not address:
            self.set_status('已选本机热点，尚未检测到可用接口。\n请在系统设置开启个人热点，\n并让朋友连接后等待地址更新。\n选择模式不会自动开启系统热点。')
            return
        if hotspot:
            self.set_status('已检测到可用热点接口。\n朋友连接本机热点后扫码加入。\n记分无需互联网。\n热点由系统设置控制。')
        else:self.set_status('朋友连接同一 Wi-Fi 或本机热点。\n仅需局域网，无需互联网。\n主持时保持 App 在前台。')
    async def watch_network(self):
        pending=None
        while True:
            await asyncio.sleep(2)
            if self.network_transition:continue
            addresses=(wifi_address(),wifi_address('hotspot'))
            if addresses==self._network_snapshot:pending=None;continue
            if addresses!=pending:pending=addresses;continue
            self.refresh_address(None,addresses=addresses);pending=None
    async def exit_host(self,app):
        if self.host.server:
            if not await self.main_window.dialog(toga.ConfirmDialog('退出围桌？','退出会停止服务，其他玩家暂时断开。积分会保存。')):return False
            await asyncio.to_thread(self.host.stop)
        if self.navigation_task:self.navigation_task.cancel()
        if self.network_task:self.network_task.cancel()
        keep_screen_awake(False)
        self.resources.__exit__(None,None,None)
        return True

def main():
    prepare_locale()
    return Weizhuo('围桌','com.snowdar.weizhuomobile',icon=str(files('weizhuomobile.runtime')/'static/assets/weizhuo-logo.png'))
