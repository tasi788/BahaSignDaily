import logging
from time import sleep

from requests import session

logger = logging.getLogger(__name__)


def index_sign_in(session: session) -> str:
    base_url = 'https://www.gamer.com.tw/ajax'
    api_url = 'https://api.gamer.com.tw/mobile_app/bahamut/v1'
    text = ''

    # fetch token
    token = session.get(base_url + '/get_csrf_token.php').text
    sign_status = session.post(
        base_url + '/signin.php',
        data={'action': '2'}).json()

    if sign_status['data']['signin'] == 1:
        text += '⏭️ 主頁簽到略過，已簽到。\n'
        logger.info('⏭️ 主頁簽到略過，已簽到。')
    else:
        sign_status = session.post(
            base_url + '/signin.php',
            data={
                'action': '1',
                'token': token}
        )

        if sign_status.status_code == 200:
            text += '✅ 主頁\n'
            logger.info(text)
        else:
            text += '❌ 主頁\n'
            logger.critical('❌ 主頁')
            logger.critical(sign_status.status_code)

    # 廣告簽到
    session.cookies.set('ckBahamutCsrfToken',
                        token[:16], domain='.gamer.com.tw', secure=True)
    session.post(api_url + '/sign_in_ad_start.php',
                 headers={'X-Bahamut-Csrf-Token': token[:16]}
                 )
    sleep(30)
    sign_in_ad = session.post(api_url + '/sign_in_ad_finished.php',
                              headers={'X-Bahamut-Csrf-Token': token[:16]}
                              )
    if sign_in_ad.status_code == 200:
        text += '✅ 主頁加倍\n'
    return text
