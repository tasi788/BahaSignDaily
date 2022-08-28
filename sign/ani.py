import logging
import re
from time import time

from requests import session

logger = logging.getLogger(__name__)


def ani_sign_in(session: session) -> str:
    api_url = 'https://api.gamer.com.tw'
    ani_url = 'https://ani.gamer.com.tw'
    text = ''
    # get answer from blackXblue
    page = session.get(api_url + '/mobile_app/bahamut/v1/home.php?owner=blackXblue&page=1')
    sn = page.json()['creation'][0]['sn']

    answer_content = session.get(
        api_url + '/mobile_app/bahamut/v1/home_creation_detail.php?sn={sn}'.format(sn=sn))
    answer = re.findall(r"A:(\d)<", answer_content.json()['content'])[0]
    logger.debug(f'答案：{answer}')

    # get token
    r = session.get(
        ani_url + '/ajax/animeGetQuestion.php?t=' + str(int(time() * 1000)))
    token = r.json().get('token')
    if not token:
        # logger.critical('找不到 token')
        msg = r.json()['msg']
        logger.critical(msg)

        if '今日已經答過題目了' in msg:
            return '⏭️ 動畫瘋簽到略過，已答題。\n'
        else:
            return '⁉️ 動畫瘋簽到發生未預期錯誤。' + msg + '\n'

    # answer to sign-in
    # struct post data
    data = {
        'token': token,
        'ans': answer,
        't': str(int(time() * 1000))
    }
    resp = session.post(
        ani_url + '/ajax/animeAnsQuestion.php',
        data=data
    )

    if resp.status_code == 200:
        resp = resp.json()
        if resp['ok'] == 1:
            text += '✅ 動畫瘋\n'
            logger.info('✅ 動畫瘋簽到成功！')
            logger.info(resp['gift'])
    else:
        text += '❌ 動畫瘋答題錯誤\n'
        logger.critical('動畫瘋簽到答案錯誤！')

    return text
