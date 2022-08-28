import logging
import re

from requests import session

logger = logging.getLogger(__name__)


def guild_sign_in(session: session) -> str:
    text = ''
    guildtext = session.get(
        'https://api.gamer.com.tw/ajax/common/topBar.php?type=forum').text
    guild = re.findall(r'guild\.php\?gsn=(\d*)', guildtext)

    if not guild:
        logger.info('⏭️ 無參加工會')
        return '⏭️ 無參加工會\n'

    for _gsn in re.findall(r'guild\.php\?gsn=(\d*)', guildtext):
        resp = session.post(
            'https://guild.gamer.com.tw/ajax/guildSign.php', data={'sn': _gsn})

        if resp.status_code == 200:
            logger.info(resp.json()['msg'])
            text += resp.json()['msg'] + '\n'
    return text
