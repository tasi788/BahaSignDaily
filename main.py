import importlib
import json
import logging
import os
import sys
from base64 import b64encode
from datetime import datetime, timezone, timedelta
from glob import glob
from inspect import getmembers, isfunction, signature
from random import getrandbits

import pyotp
import requests
from git import Repo
from nacl import encoding, public

tz = timezone(timedelta(hours=+8))
today = datetime.now(tz)
logger = logging.getLogger(__name__)
logging.basicConfig(level='INFO',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

GH_REPO = os.getenv('GH_REPO')
GH_TOKEN = os.getenv('GH_TOKEN')
TOTP = os.getenv('BAHA_2FA')
COOKIES = os.getenv('BAHA_COOKIE')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')


# RUN_PERIOD = os.getenv('RUN_PERIOD', None)


class Bot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f'https://api.telegram.org/bot{self.token}'

    def sendMessage(self, text: str):
        r = requests.post(self.api_url + '/sendMessage',
                          json={
                              'chat_id': self.chat_id,
                              'text': text,
                              'parse_mode': 'html'
                          })


def update_secret(keys: str, value: str):
    base_url = f'https://api.github.com/repos/{GH_REPO}/actions/secrets'
    headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {GH_TOKEN}'}
    resp = requests.get(base_url + '/public-key', headers=headers)
    if 'key' not in resp.json():
        logger.critical('讀取 GH 公鑰失敗')
        sys.exit(1)
    public_key = resp.json()['key']
    key_id = resp.json()['key_id']

    public_key = public.PublicKey(public_key.encode('utf-8'), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = b64encode(
        sealed_box.encrypt(value.encode('utf-8'))).decode('utf-8')

    data = {'encrypted_value': encrypted, 'key_id': key_id}
    resp = requests.put(
        base_url + f'/{keys}',
        headers=headers,
        json=data)
    if resp.status_code in [201, 204]:
        logger.info('上傳 SECRET 成功')
    else:
        logger.critical('上傳 SECRET 失敗。')


def loads_plugins() -> list:
    pluginslist = glob('./sign/*.py')
    registered_plugin = list()
    for plugin in pluginslist:
        mod = importlib.import_module(f'sign.{plugin.split("/")[-1][:-3]}')
        functions_name = getmembers(mod, isfunction)[0]
        if 'session' in signature(functions_name[1]).parameters.keys():
            registered_plugin.append(getattr(mod, functions_name[0]))
    logger.debug(f'loads {len(registered_plugin)} plugins')
    return registered_plugin


def login() -> requests.session:
    session = requests.session()
    normal_header = {
        'user-agent': 'Bahadroid (https://www.gamer.com.tw/)',
        'x-bahamut-app-instanceid': 'cc2zQIfDpg4',
        'x-bahamut-app-android': 'tw.com.gamer.android.activecenter',
        'x-bahamut-app-version': '251',
        'accept-encoding': 'gzip'
    }
    login_header = {
        'user-agent': 'Bahadroid (https://www.gamer.com.tw/)',
        'x-bahamut-app-instanceid': 'cc2zQIfDpg4',
        'x-bahamut-app-android': 'tw.com.gamer.android.activecenter',
        'x-bahamut-app-version': '251',
        'content-type': 'application/x-www-form-urlencoded',
        'content-length': '44',
        'accept-encoding': 'gzip',
        'cookie': 'ckAPP_VCODE=7045'
    }
    # test if cookies expires
    expires = False
    baha_cookies = COOKIES
    if baha_cookies:
        session.cookies.update(
            json.loads(COOKIES)
        )
        session.headers = normal_header

        check_status = session.get(
            'https://api.gamer.com.tw/mobile_app/bahamut/v1/app_create.php?OSVersion=14.4.2'
        )
        if not check_status.json()['login']:
            expires = True
            # 極度重要。
            session.cookies.clear()
            logger.warning('餅乾過期')
        else:
            logger.info('已成功登入')
    else:
        logger.warning('找不到餅乾')
        expires = True

    # load login info from SECRET
    if expires:
        login_data = {
            'uid': os.getenv('BAHA_UID'),
            'passwd': os.getenv('BAHA_PASSWD'),
            'vcode': '7045'
        }
        # 2fa
        if TOTP:
            totp = pyotp.TOTP(TOTP)
            login_data.update({'twoStepAuth': totp.now()})
        session.headers = login_header
        account = session.post(
            'https://api.gamer.com.tw/mobile_app/user/v3/do_login.php',
            data=login_data
        )
        if account.status_code == 200:
            login_status = account.json()
            if 'code' in login_status.keys():
                logger.critical('登入發生錯誤')
                logger.critical(login_status['message'])
                sys.exit(1)
            elif 'error' in login_status.keys():
                logger.critical('登入發生錯誤')
                logger.critical(login_status['error']['message'])
                sys.exit(1)

            logger.info('已登入')
            update_secret('BAHA_COOKIE', json.dumps(account.cookies.get_dict()))
        else:
            logger.critical('登入發生錯誤')
            logger.critical(account.text)
            sys.exit(1)
    session.headers = normal_header
    return session


def get_self(session: requests.Session):
    url = 'https://api.gamer.com.tw/mobile_app/bahamut/v3/profile.php'
    resp = session.get(url).json()['data']
    gold = resp['gold']
    gp = resp['gp']
    days = resp['signDays']
    return gold, gp, days


def run(session: requests.session, bot: Bot):
    plugins = loads_plugins()
    text = '巴哈簽到\n'
    gold, _, __ = get_self(session)
    for sign in plugins:
        resp = sign(session)
        text += resp

    # 新增更多文字
    gold_today, gp, days = get_self(session)
    diff = gold_today - gold
    now = datetime.now(tz)
    text += '\n'
    text += f'💰 {gold_today}(+{diff}) 巴幣\n'
    text += f'🚀 {gp}GP\n'
    text += f'📆 連續簽到 {days} 天\n'
    text += f'#baha #{now.strftime("%Y%m%d")}'
    bot.sendMessage(text)


def run_check(check: bool = True, flags: bool = False) -> bool:
    repo = Repo('./')
    branches = repo.refs
    format = '%Y.%m.%d'
    today_date = today.strftime(format)

    if check:
        result = list(filter(lambda x: x.name == f'origin/{today_date}', list(branches)))
        logger.info(branches)
        logger.info(result)
        if result:
            logger.info('今天已經執行過。')
            return False
        if today.hour == 23 and not result:
            return True
        if not result and bool(getrandbits(1)):
            return True
        return False
    if flags:
        new_branch = repo.create_head(today_date)
        yesterday = today - timedelta(days=1)
        yesterday_date = yesterday.strftime(format)

        refspec = (f'{today_date}')
        for branch in branches:
            if branch.name == f'origin/{yesterday_date}':
                # repo.delete_head(branch)
                refspec += f':{yesterday_date}'

        # switch branch
        repo.head.reference = new_branch
        open(today_date, 'wb').close()
        repo.index.add([today_date])
        repo.index.commit(today_date)
        repo.remotes.origin.push(refspec=refspec)
        return True


if __name__ == "__main__":
    if run_check(check=True):
        session = login()
        bot = Bot(BOT_TOKEN, CHAT_ID)
        run(session, bot)
        run_check(check=False, flags=True)
