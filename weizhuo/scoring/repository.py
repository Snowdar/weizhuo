"""Durable rooms and hand results; legacy single-room state is retained."""
import json, sqlite3, hashlib, hmac, secrets
from contextlib import nullcontext
from pathlib import Path
from .games.zhajinhua import DEFAULT, LEGACY_DEFAULT

class Repository:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.legacy=None
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS admin_credentials (id INTEGER PRIMARY KEY CHECK(id=1), salt TEXT NOT NULL, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rooms (code TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hands (room TEXT, number INTEGER, data TEXT, PRIMARY KEY(room,number));
            CREATE TABLE IF NOT EXISTS device_rooms (device TEXT, room TEXT, token TEXT, PRIMARY KEY(device,room));
            CREATE TABLE IF NOT EXISTS device_rule_favorites (device TEXT, id TEXT, name TEXT NOT NULL, text TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(device,id));
            CREATE TABLE IF NOT EXISTS device_profiles (device TEXT PRIMARY KEY, nickname TEXT NOT NULL);''')
            table=db.execute("SELECT 1 FROM sqlite_master WHERE name='state'").fetchone()
            if table:
                row=db.execute('SELECT data FROM state WHERE id=1').fetchone()
                if row:
                    old=json.loads(row[0]);self.legacy=old['room']
                    db.execute('INSERT OR IGNORE INTO rooms VALUES (?,?)',(old['room'],json.dumps(self.normalize(old))))
    def admin_password_changed(self):
        with self.connect() as db:return bool(db.execute('SELECT 1 FROM admin_credentials WHERE id=1').fetchone())
    def admin_password_matches(self,password,initial):
        if not isinstance(password,str) or len(password)>128:return False
        with self.connect() as db:row=db.execute('SELECT salt,digest FROM admin_credentials WHERE id=1').fetchone()
        if not row:return hmac.compare_digest(password.encode(),initial.encode())
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row[0]),250000).hex()
        return hmac.compare_digest(digest,row[1])
    def set_admin_password(self,password):
        if not isinstance(password,str) or not 4<=len(password)<=128:raise ValueError('新密码需为 4–128 个字符')
        salt=secrets.token_bytes(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,250000).hex()
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO admin_credentials VALUES(1,?,?)',(salt.hex(),digest))
    def reset_admin_password(self):
        with self.connect() as db:db.execute('DELETE FROM admin_credentials WHERE id=1')

    def connect(self):return sqlite3.connect(self.path,timeout=10)
    @staticmethod
    def normalize(s):
        s.setdefault('game','zhajinhua');s.setdefault('name','原有炸金花房间')
        s.setdefault('createdAt',0);s.setdefault('destroyedAt',None);s.setdefault('version',0);s.setdefault('requests',{})
        s.setdefault('hostPlayer',None)
        if s['game']=='holdem':
            return s
        if s['game']=='mahjong':
            s.setdefault('transactions',[])
            return s
        s['config']={**(DEFAULT if 'minBet' in s['config'] else LEGACY_DEFAULT),'seenRaisesFloor':0,'allowBlindCompare':0,'allowNegative':0,**s['config']}
        s['config'].setdefault('minBet',s['config'].get('base',10))
        s['config'].setdefault('minRaise',0)
        for p in s['players']:p.setdefault('ready',False)
        if 'bets' not in s:
            # Earlier versions saved only totals. Do not invent individual bets.
            s['bets']=[dict(seq=i+1,playerId=p['id'],playerName=p['name'],amount=p['spent'],kind='历史合计',round=0,time='') for i,p in enumerate(s['players']) if p.get('spent',0)>0]
        return s
    def get(self,code):
        with self.connect() as db:row=db.execute('SELECT data FROM rooms WHERE code=?',(code,)).fetchone()
        return self.normalize(json.loads(row[0])) if row else None
    def save(self,s,remove_hand=None,connection=None):
        if s.get('destroyedAt'):
            # Keep only a closed-room marker; remove room-lifetime scores/history.
            s={**s,'players':[],'requests':{},'log':[],'bets':[],'result':None,'host':'','hostPlayer':None,'pot':0,'turn':None,'pending':None,'phase':'lobby','undo':[],'transactions':[]}
        raw=json.dumps(s,ensure_ascii=False)
        with (nullcontext(connection) if connection is not None else self.connect()) as db:
            db.execute('INSERT OR REPLACE INTO rooms VALUES (?,?)',(s['room'],raw))
            if s['room']==self.legacy:db.execute('UPDATE state SET data=? WHERE id=1',(raw,))
            if s.get('destroyedAt'):
                db.execute('DELETE FROM hands WHERE room=?',(s['room'],))
                db.execute('DELETE FROM device_rooms WHERE room=?',(s['room'],))
            if remove_hand is not None:
                db.execute('DELETE FROM hands WHERE room=? AND number=?',(s['room'],remove_hand))
            if s.get('result'):
                db.execute('INSERT OR REPLACE INTO hands VALUES (?,?,?)',(s['room'],s['hand'],json.dumps(s['result'],ensure_ascii=False)))
    def histories(self,code):
        with self.connect() as db:rows=db.execute('SELECT number,data FROM hands WHERE room=? ORDER BY number DESC LIMIT 20',(code,)).fetchall()
        return [dict(hand=n,**json.loads(raw)) for n,raw in rows]

    def active_count(self):
        with self.connect() as db:rows=db.execute('SELECT data FROM rooms').fetchall()
        return sum(not s.get('destroyedAt') and s.get('phase') in ('playing','comparing','showdown','dealing') for s in (json.loads(x[0]) for x in rows))

    def bind_device(self,device,room,token):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO device_rooms VALUES(?,?,?)',(device,room,token))

    def device_rooms(self,device):
        with self.connect() as db:
            return db.execute('SELECT room,token FROM device_rooms WHERE device=?',(device,)).fetchall()

    def device_nickname(self,device,nickname=None):
        with self.connect() as db:
            if nickname is not None:
                db.execute('INSERT OR REPLACE INTO device_profiles VALUES (?,?)',(device,nickname))
            row=db.execute('SELECT nickname FROM device_profiles WHERE device=?',(device,)).fetchone()
            return row[0] if row else ''
