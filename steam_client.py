"""Read the configured player's public library using a server-only API key."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException

DEFAULT_STEAM_ID = '76561198800622628'  # https://steamcommunity.com/id/R1ch11/


def get_played_games():
    key = os.getenv('STEAM_API_KEY', '').strip()
    steam_id = os.getenv('STEAM_ID', DEFAULT_STEAM_ID).strip()
    if not key:
        raise HTTPException(503, 'Добавь STEAM_API_KEY в переменные окружения сервера и перезапусти приложение.')
    if not re.fullmatch(r'\d{17}', steam_id):
        raise HTTPException(503, 'В STEAM_ID должен быть указан SteamID64 из 17 цифр.')
    query = urllib.parse.urlencode({'key': key, 'input_json': json.dumps({
        'steamid': steam_id, 'include_appinfo': True, 'include_played_free_games': True})})
    request = urllib.request.Request('https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?' + query)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        error.close()
        if error.code in (401, 403):
            raise HTTPException(502, 'Steam отклонил API-ключ. Проверь STEAM_API_KEY на сервере.') from None
        raise HTTPException(502, 'Steam временно недоступен. Повтори синхронизацию позже.') from None
    except (OSError, ValueError):
        raise HTTPException(502, 'Не удалось получить библиотеку Steam. Повтори позже.') from None
    data = payload.get('response') if isinstance(payload, dict) else None
    if not isinstance(data, dict) or 'game_count' not in data:
        raise HTTPException(403, 'Steam не открыл библиотеку. В профиле открой «Доступ к игровой информации» и отображение времени в играх.')
    games = data.get('games', [])
    if not isinstance(games, list) or (data['game_count'] and not games):
        raise HTTPException(502, 'Steam вернул неполный список игр. Повтори позже.')
    if games and not any(isinstance(game, dict) and 'playtime_forever' in game for game in games):
        raise HTTPException(403, 'Steam скрывает часы. В настройках приватности разреши показывать время в играх.')
    selected = {}
    for game in games:
        if not isinstance(game, dict):
            raise HTTPException(502, 'Steam вернул некорректные данные игры.')
        minutes = game.get('playtime_forever', 0)
        appid = game.get('appid')
        name = game.get('name')
        if type(minutes) is not int or minutes < 0 or type(appid) is not int or appid <= 0:
            raise HTTPException(502, 'Steam вернул некорректное время или идентификатор игры.')
        if minutes > 300:
            if not isinstance(name, str) or not name.strip():
                raise HTTPException(502, 'Steam не вернул название игры. Повтори позже.')
            selected[appid] = {'appid': appid, 'name': name.strip(), 'minutes': minutes}
    return steam_id, list(selected.values())
