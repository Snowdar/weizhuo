"""HTTP adapter for persistent local-network game rooms."""
import io,json,os,re,sys,socket,subprocess,secrets,time,hmac,hashlib,gzip,ipaddress,threading
from urllib.request import build_opener,ProxyHandler
from pathlib import Path
from functools import lru_cache
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
ROOT=Path(__file__).resolve().parent
DATA_ROOT=ROOT/'data'
sys.path.insert(0,str(ROOT/'vendor'))
import qrcode
from qrcode.image.pure import PyPNGImage
from scoring.repository import Repository
from scoring.rooms import Rooms

def app_version(resource_root=None):
    """Read the release identity shipped with the app, or the source checkout."""
    resources=Path(resource_root) if resource_root is not None else ROOT
    for path in (resources/'build-info.json',resources.parent/'build-info.json',resources.parent/'Resources/build-info.json',resources.parent/'version.json'):
        try:
            identity=json.loads(path.read_text())
            if not re.fullmatch(r'\d+\.\d+\.\d+',identity['version']) or type(identity['build']) is not int or identity['build']<1:continue
            return f"{identity['version']}.{identity.get('prerelease', 'a'+str(identity['build']))}"
        except (OSError,ValueError,KeyError,TypeError):continue
    return None

def lan_ip():
    return cached_lan_ip(int(time.monotonic() // 30))

@lru_cache(maxsize=2)
def cached_lan_ip(_period):
    return detect_lan_ip()

def detect_lan_ip():
    if os.path.exists('/sbin/ifconfig'):
        try:
            data=subprocess.check_output(['/sbin/ifconfig'],text=True,timeout=2)
            for block in re.split(r'(?=^\w+: flags=)',data,flags=re.M):
                if re.match(r'en\d+:',block) and 'status: active' in block:
                    m=re.search(r'\binet (\d+\.\d+\.\d+\.\d+)',block)
                    if m:return m[1]
        except (OSError,subprocess.SubprocessError):pass
    return '127.0.0.1'
@lru_cache(maxsize=32)
def qr_png(url):
    qr=qrcode.QRCode(box_size=9,border=4,error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url);qr.make(fit=True)
    out=io.BytesIO();qr.make_image(image_factory=PyPNGImage).save(out);return out.getvalue()

def accepts_gzip(headers):
    for item in headers.get('Accept-Encoding','').split(','):
        encoding,*params=item.strip().split(';')
        if encoding.lower()!='gzip':continue
        try:return all(float(p.strip()[2:])>0 for p in params if p.strip().startswith('q='))
        except ValueError:return False
    return False

@lru_cache(maxsize=64)
def static_payload(path,mtime,size,compressed):
    raw=Path(path).read_bytes()
    if compressed:raw=gzip.compress(raw,compresslevel=5,mtime=0)
    return raw,'"'+hashlib.sha256(raw).hexdigest()+'"'

def network_probe(server,address):
    """Only probe this service's fixed endpoint; bypass VPN/HTTP proxy settings."""
    try:
        address=str(ipaddress.IPv4Address(address))
        opener=build_opener(ProxyHandler({}))
        with opener.open(f'http://{address}:{server.server_port}/api/network-ping',timeout=2) as response:
            result=json.loads(response.read(1024))
        return isinstance(result,dict) and result.get('instance')==server.network_instance
    except (OSError,ValueError):return False


def network_check(server,key):
    with server.network_lock:
        item=server.network_checks.get(key)
        if not item or time.monotonic()-item['created']>180:
            raise ValueError('连接检查已过期，请重新检查')
        if item['address']!=(server.lan_address or lan_ip()):
            raise ValueError('网络地址已变化，请重启服务后重新检查')
        return dict(item)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,code,data,kind='application/json; charset=utf-8',cache_control='no-store',headers=None):
        raw=json.dumps(data,ensure_ascii=False).encode() if kind.startswith('application/json') else data
        if kind.startswith('application/json') and len(raw)>1024 and accepts_gzip(self.headers):
            raw=gzip.compress(raw,compresslevel=3,mtime=0);headers={**(headers or {}),'Content-Encoding':'gzip','Vary':'Accept-Encoding'}
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control',cache_control);self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        for name,value in (headers or {}).items():self.send_header(name,value)
        if getattr(self,'device_cookie',None):self.send_header('Set-Cookie',self.device_cookie)
        self.end_headers();self.wfile.write(raw)
    def context(self):
        url=urlparse(self.path);test=url.path.startswith('/test/')
        path=url.path[5:] if test else url.path
        qs=parse_qs(url.query);rooms=self.server.test_rooms if test else self.server.rooms
        code=qs.get('room',[rooms.repo.legacy])[0]
        return path,qs,rooms,code,'/test/' if test else '/'
    def link(self,prefix,code=None):return f'http://{getattr(self.server,"lan_address",None) or lan_ip()}:{self.server.server_port}{prefix}'+(f'?room={code}' if code else '')
    def admin_secret(self,rooms):
        with rooms.lock:
            secrets_by_space=self.server.__dict__.setdefault('admin_secrets',{})
            return secrets_by_space.setdefault(str(rooms.repo.path),secrets.token_bytes(32))
    def invalidate_admin_sessions(self,rooms):
        self.server.__dict__.setdefault('admin_secrets',{})[str(rooms.repo.path)]=secrets.token_bytes(32)
    def is_service_device_request(self):
        try:
            peer=ipaddress.ip_address(self.client_address[0])
            local=ipaddress.ip_address(self.connection.getsockname()[0])
            host=urlparse('http://'+self.headers.get('Host','')).hostname
            if host=='localhost':return peer.is_loopback
            address=ipaddress.ip_address(host)
            return (peer.is_loopback and address.is_loopback) or (peer==local and address==local)
        except (ValueError,TypeError,OSError):return False
    def local_admin_reset(self):
        try:
            peer=ipaddress.ip_address(self.client_address[0]);host=urlparse('http://'+self.headers.get('Host','')).hostname
            return peer.is_loopback and (host=='localhost' or (host is not None and ipaddress.ip_address(host).is_loopback))
        except ValueError:return False
    def initial_admin_password(self):return os.environ.get('SCOREBOARD_ADMIN_CODE','1234')
    def admin_cookie_name(self,prefix):return 'weizhuo_admin_test' if prefix=='/test/' else 'weizhuo_admin'
    def admin_authorized(self,rooms,prefix):
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
        entry=cookie.get(self.admin_cookie_name(prefix))
        if not entry:return False
        try:
            expiry,nonce,signature=entry.value.split('.')
            expected=hmac.new(self.admin_secret(rooms),(prefix+expiry+'.'+nonce).encode(),hashlib.sha256).hexdigest()
            return int(expiry)>time.time() and hmac.compare_digest(signature,expected)
        except (ValueError,TypeError):return False
    def do_GET(self):
        try:
            if urlparse(self.path).path=='/test':
                self.send_response(302);self.send_header('Location','/test/');self.end_headers();return
            path,qs,rooms,code,prefix=self.context()
            if path=='/api/network-ping':
                self.respond(200,dict(instance=self.server.network_instance));return
            if path in ('/api/network-check','/network-check-qr.png'):
                if not self.is_service_device_request():self.respond(403,dict(error='仅服务设备可查看连接检查'));return
                key=qs.get('check',[''])[0];item=network_check(self.server,key)
                if path=='/network-check-qr.png':
                    self.respond(200,qr_png(self.link(prefix)+'network-check?check='+key),'image/png');return
                self.respond(200,dict(loopback=item['loopback'],lan=item['lan'],peer=item['peer'],expiresIn=max(0,int(180-(time.monotonic()-item['created'])))));return
            if path=='/network-check':
                key=qs.get('check',[''])[0];network_check(self.server,key)
                remote=not self.is_service_device_request() and not ipaddress.ip_address(self.client_address[0]).is_loopback
                if remote:
                    with self.server.network_lock:self.server.network_checks[key]['peer']=True
                message='连接成功：这台设备能访问围桌服务。请回到服务设备查看结果。' if remote else '这是服务设备自身访问，尚不能验证其他设备。请让另一台设备扫码。'
                page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>围桌连接检查</title><body style="margin:0;background:#f1f3eb;color:#234c3d;font:18px/1.7 system-ui"><main style="margin:12vh auto;padding:24px;max-width:440px"><h1>围桌 · 连接检查</h1><p>'+message+'</p><p>本次检查不创建房间，也不改变积分。</p></main></body></html>'
                self.respond(200,page.encode(),'text/html; charset=utf-8');return
            if path=='/api/admin/settings':
                self.respond(200,dict(canReset=self.local_admin_reset(),passwordChanged=rooms.repo.admin_password_changed(),configuredInitial=self.initial_admin_password()!='1234'));return
            if path=='/api/admin/rooms':
                if not self.admin_authorized(rooms,prefix):self.respond(401,dict(error='请先输入管理员授权码'));return
                self.respond(200,dict(rooms=rooms.admin_rooms()));return
            if path=='/api/bootstrap':
                self.respond(200,dict(games=[dict(id='zhajinhua',name='炸金花',description='线下发牌、线上记分'),dict(id='mahjong',name='自由记分',description='适合麻将、桌游、聚会小游戏等'),dict(id='holdem',name='德州扑克',description='无限注 · 盲注、边池与发牌流程')],entry=self.link(prefix),legacyRoom=rooms.repo.legacy,appVersion=self.server.app_version,serviceDevice=getattr(self.server,'service_device','computer'),isServiceDevice=self.is_service_device_request(),voiceChoices=getattr(getattr(self.server,'announcer',None),'choices',[]) if self.is_service_device_request() else []));return
            if path=='/api/state':
                # A service health request works even before creation or after
                # the migrated room is destroyed. Explicit invitations still fail.
                saved=rooms.repo.get(code) if code else None
                service_request='room' not in qs and not qs.get('token')
                if service_request and (not saved or saved.get('destroyedAt')):
                    out=dict(room=code,phase='lobby',hand=0,players=[],pot=0)
                else:
                    out=rooms.public(code,qs.get('token',[''])[0],self.link(prefix,code))
                if service_request:
                    out['activeRooms']=rooms.repo.active_count()
                    if out['activeRooms'] and out['phase'] in ('lobby','finished'):out['phase']='playing'
                self.respond(200,out);return
            if path=='/device-identity-qr.png':
                key=qs.get('key',[''])[0]
                rooms.device_rooms(key)
                self.respond(200,qr_png(self.link(prefix)+'#device='+key),'image/png');return
            if path=='/identity-qr.png':
                token=qs.get('token',[''])[0]
                identity=rooms.public(code,token,'')
                if not identity['me'] and not identity['isHost']:raise ValueError('身份凭证无效或已离开房间')
                url=self.link(prefix,code)+'#'+('host' if identity['isHost'] else 'player')+'='+token
                self.respond(200,qr_png(url),'image/png');return
            if path in ('/entry-qr.png','/join-qr.png'):
                if path=='/join-qr.png':rooms.room(code)
                self.respond(200,qr_png(self.link(prefix,code if path=='/join-qr.png' else None)),'image/png');return
            assets={'/admin':('admin.html','text/html'),'/admin/':('admin.html','text/html'),'/admin.js':('admin.js','application/javascript'),'/':('index.html','text/html'),'/app.js':('app.js','application/javascript'),'/zhajinhua.js':('zhajinhua.js','application/javascript'),'/style.css':('style.css','text/css')}
            assets.update({'/assets/service-home-background-v2.webp':('assets/service-home-background-v2.webp','image/webp'),'/assets/holdem-scene-iphone-v4.webp':('assets/holdem-scene-iphone-v4.webp','image/webp'),'/assets/holdem-scene-v2.webp':('assets/holdem-scene-v2.webp','image/webp'),'/assets/holdem-scene-landscape-v2.webp':('assets/holdem-scene-landscape-v2.webp','image/webp'),'/assets/free-score-scene-landscape-v1.webp':('assets/free-score-scene-landscape-v1.webp','image/webp'),'/assets/zhajinhua-scene-landscape-v1.webp':('assets/zhajinhua-scene-landscape-v1.webp','image/webp'),'/tabletop.js':('tabletop.js','application/javascript'),'/assets/zhajinhua-scene-v1.webp':('assets/zhajinhua-scene-v1.webp','image/webp'),'/assets/free-score-scene-v1.webp':('assets/free-score-scene-v1.webp','image/webp'),'/assets/holdem-floor-v1.webp':('assets/holdem-floor-v1.webp','image/webp'),'/assets/holdem-chip-stack-v1.webp':('assets/holdem-chip-stack-v1.webp','image/webp'),'/assets/holdem-table-landscape-v1.webp':('assets/holdem-table-landscape-v1.webp','image/webp'),'/assets/holdem-table-v1.webp':('assets/holdem-table-v1.webp','image/webp'),'/holdem.js':('holdem.js','application/javascript'),'/games.js':('games.js','application/javascript'),'/assets/holdem-icon.webp':('assets/holdem-icon.webp','image/webp'),'/assets/party-background-pro.webp':('assets/party-background-pro.webp','image/webp'),'/assets/mahjong-icon.webp':('assets/mahjong-icon.webp','image/webp'),'/mahjong.js':('mahjong.js','application/javascript'),'/theme.css':('theme.css','text/css'),'/assets/weizhuo-logo.png':('assets/weizhuo-logo.png','image/png'),'/assets/zhajinhua-icon.webp':('assets/zhajinhua-icon.webp','image/webp')})
            if path in assets:
                file,kind=assets[path];asset=getattr(self.server,'asset_root',ROOT)/'static'/file
                stat=asset.stat();compressed=kind.startswith(('text/','application/javascript')) and accepts_gzip(self.headers)
                raw,etag=static_payload(str(asset),stat.st_mtime_ns,stat.st_size,compressed)
                cache='public, max-age=86400' if path.startswith('/assets/') else 'no-cache'
                headers={'ETag':etag,'Vary':'Accept-Encoding'}
                if compressed:headers['Content-Encoding']='gzip'
                if etag in self.headers.get('If-None-Match','').split(', ') or self.headers.get('If-None-Match')=='*':
                    self.respond(304,b'',kind,cache,headers);return
                self.respond(200,raw,kind+('; charset=utf-8' if kind.startswith(('text/','application/javascript')) else ''),cache,headers);return
            self.respond(404,dict(error='页面不存在'))
        except (BrokenPipeError,ConnectionResetError):pass
        except ValueError as e:self.respond(404,dict(error=str(e)))
        except Exception:self.respond(500,dict(error='读取服务状态失败'))
    def do_POST(self):
        try:
            path,qs,rooms,code,prefix=self.context()
            if path not in ('/api/network-check','/api/voice','/api/action','/api/rooms','/api/device','/api/admin/login','/api/admin/logout','/api/admin/clear','/api/admin/password','/api/admin/reset'):self.respond(404,dict(error='接口不存在'));return
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):self.respond(403,dict(error='不允许跨站操作'));return
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=20000:raise ValueError('请求大小不正确')
            self.connection.settimeout(10);d=json.loads(self.rfile.read(size))
            if not isinstance(d,dict):raise ValueError('请求格式不正确')
            if path=='/api/network-check':
                if not self.is_service_device_request():self.respond(403,dict(error='仅服务设备可发起连接检查'));return
                address=self.server.lan_address or lan_ip()
                item=dict(created=time.monotonic(),address=address,loopback=network_probe(self.server,'127.0.0.1'),lan=network_probe(self.server,address),peer=False)
                key=secrets.token_urlsafe(24)
                with self.server.network_lock:
                    self.server.network_checks={k:v for k,v in self.server.network_checks.items() if time.monotonic()-v['created']<=180}
                    if len(self.server.network_checks)>=8:self.server.network_checks.pop(next(iter(self.server.network_checks)))
                    self.server.network_checks[key]=item
                self.respond(200,dict(check=key,loopback=item['loopback'],lan=item['lan'],peer=False,url=self.link(prefix)+'network-check?check='+key));return
            if path=='/api/voice':
                if not self.is_service_device_request():self.respond(403,dict(error='播报仅服务设备可调用'));return
                if not rooms.public(d.get('room',''),d.get('token',''),'').get('isHost'):self.respond(403,dict(error='仅房主可播报'));return
                announcer=getattr(self.server,'announcer',None)
                if announcer is None:raise ValueError('未配置离线音色资源')
                self.respond(200,announcer.render(d.get('text'),d.get('voice')),'audio/wav');return
            if path.startswith('/api/admin/'):
                name=self.admin_cookie_name(prefix)
                if path=='/api/admin/reset':
                    if not self.local_admin_reset():self.respond(403,dict(error='仅服务所在设备通过 localhost 或 127.0.0.1 可重置密码'));return
                    if d.get('confirmed') is not True:raise ValueError('请确认重置管理员密码')
                    with rooms.lock:
                        rooms.repo.reset_admin_password();self.invalidate_admin_sessions(rooms)
                    self.respond(200,dict(message='管理员密码已重置为服务的初始密码，请重新登录'));return
                if path=='/api/admin/login':
                    with rooms.lock:
                        if not rooms.repo.admin_password_matches(d.get('code'),self.initial_admin_password()):
                            self.respond(403,dict(error='管理员密码不正确'));return
                        expiry=str(int(time.time())+8*3600);nonce=secrets.token_hex(16)
                        signature=hmac.new(self.admin_secret(rooms),(prefix+expiry+'.'+nonce).encode(),hashlib.sha256).hexdigest()
                        self.device_cookie=f'{name}={expiry}.{nonce}.{signature}; Path={prefix}; Max-Age=28800; HttpOnly; SameSite=Strict'
                    self.respond(200,dict(message='管理员已登录'));return
                if not self.admin_authorized(rooms,prefix):self.respond(401,dict(error='管理员授权已过期，请重新进入'));return
                if path=='/api/admin/password':
                    with rooms.lock:
                        if not self.admin_authorized(rooms,prefix):self.respond(401,dict(error='管理员授权已过期，请重新登录'));return
                        if not rooms.repo.admin_password_matches(d.get('currentPassword'),self.initial_admin_password()):raise ValueError('当前密码不正确')
                        if d.get('newPassword')!=d.get('confirmPassword'):raise ValueError('两次新密码不一致')
                        rooms.repo.set_admin_password(d.get('newPassword'));self.invalidate_admin_sessions(rooms)
                    self.device_cookie=f'{name}=; Path={prefix}; Max-Age=0; HttpOnly; SameSite=Strict'
                    self.respond(200,dict(message='密码已修改，请使用新密码重新登录'));return
                if path=='/api/admin/logout':
                    self.device_cookie=f'{name}=; Path={prefix}; Max-Age=0; HttpOnly; SameSite=Strict'
                    self.respond(200,{});return
                self.respond(200,rooms.admin_clear_many(d.get('rooms'),d.get('confirmed')) if 'rooms' in d else rooms.admin_clear(d.get('room'),d.get('version'),d.get('confirmRoom')));return
            if path=='/api/device':
                cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
                cookie_name='weizhuo_device_test' if prefix=='/test/' else 'weizhuo_device'
                secret=d.get('deviceKey') or (cookie[cookie_name].value if cookie_name in cookie else None)
                if not secret:secret=secrets.token_urlsafe(32)
                bindings=d.get('bindings',[])
                if not isinstance(bindings,list):raise ValueError('设备房间记录格式不正确')
                result=rooms.device_rooms(secret,bindings)
                self.device_cookie=f'{cookie_name}={secret}; Path={prefix}; Max-Age=31536000; HttpOnly; SameSite=Lax'
                nickname=rooms.device_nickname(secret,d.get('nickname'))
                favorites=rooms.device_rule_favorites(secret,d.get('ruleFavorite'))
                self.respond(200,dict(deviceKey=secret,rooms=result,nickname=nickname,ruleFavorites=favorites));return
            if d.get('deviceKey'):rooms.device_rooms(d['deviceKey'])
            result=rooms.create(d) if path=='/api/rooms' else rooms.execute(d.get('room') or code,d)
            if result.get('token') and d.get('deviceKey'):
                rooms.device_rooms(d['deviceKey'],[dict(room=result.get('room') or d.get('room') or code,token=result['token'])])
            self.respond(200,result)
        except (ValueError,TypeError) as e:self.respond(400,dict(error=str(e)))
        except Exception:self.respond(500,dict(error='操作失败，未保存本次变更'))

def make_server(port, *, data_dir=None, lan_address=None, resource_root=None, bind='0.0.0.0', service_device=None):
    server=ThreadingHTTPServer((bind,port),Handler)
    data=Path(data_dir) if data_dir is not None else DATA_ROOT
    server.asset_root=Path(resource_root) if resource_root is not None else ROOT
    server.app_version=app_version(server.asset_root)
    server.network_instance=secrets.token_hex(16)
    server.network_lock=threading.Lock();server.network_checks={}
    server.lan_address=lan_address
    server.service_device=service_device or ('phone' if sys.platform in ('android','ios') or hasattr(sys,'getandroidapilevel') else 'computer')
    try:
        server.rooms=Rooms(Repository(data/'scoreboard.sqlite3'));server.test_rooms=Rooms(Repository(data/'test_scoreboard.sqlite3'))
    except Exception:
        server.server_close();raise
    return server
if __name__=='__main__':
    port=int(os.environ.get('PORT','8765'));server=make_server(port)
    print(f'首页：http://{lan_ip()}:{port}/\n首页二维码：http://{lan_ip()}:{port}/entry-qr.png',flush=True)
    if server.rooms.repo.legacy:
        s=server.rooms.repo.get(server.rooms.repo.legacy)
        print(f'原房主管理：http://127.0.0.1:{port}/?room={s["room"]}#host={s["host"]}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
