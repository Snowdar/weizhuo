from .zhajinhua import Engine
GAMES = {"zhajinhua": Engine}

from .mahjong import Engine as MahjongEngine, fresh as mahjong_fresh
from .zhajinhua import fresh as zhajinhua_fresh
GAMES["mahjong"] = MahjongEngine
FRESH = {"zhajinhua": zhajinhua_fresh, "mahjong": mahjong_fresh}
GAME_NAMES = {"zhajinhua": "炸金花", "mahjong": "自由记分"}

from .holdem import Engine as HoldemEngine, fresh as holdem_fresh
GAMES["holdem"] = HoldemEngine
FRESH["holdem"] = holdem_fresh
GAME_NAMES["holdem"] = "德州扑克"
