"""
    backlog api よりチケットの情報を取得し、資産化未入力チケットをslackに送信します。

"""
from logging import getLogger, DEBUG
import traceback
import os
import json
import requests
import datetime

# ログの設定
logger = getLogger(__name__)
logger.setLevel(DEBUG)

# 定数
BACKLOG_ISSUE_PATH = ''
# 資産化プロジェクト(ロボ開発)のプロジェクトid
BACKLOG_ISSUE_TYPE_ID = [

]
BACKLOG_API_KEY = ''
BACKLOG_PROJECT_ID = ''
BACKLOG_TASK_API_URL = ''
SLACK_API_TOKEN = ''
SLACK_URL = ''
SLACK_CHANNEL_ID = ''
SLACK_CHANNEL_NAME_WEBHOOK = ''
SLACK_USER_NAME = 'Backlog'
SLACK_ICON_EMOJI_BUG = ':heavy_dollar_sign:'
MAX_RESPONSE_COUNT = 100
PARENT_TICKET = 1  # 親チケット
MONDAY = 0


def lambda_handler(event, context):
    """ メイン関数
    """
    try:
        result_tickets = check_capitalization_input()
        text = make_text(result_tickets)

    except:
        logger.error(traceback.format_exc())
        text = make_exception_text(traceback.format_exc())

    send_to_slack(text)


# 前日に起票もしくは更新されたチケットを取得して資産化チェックが必要なものを返却する
def check_capitalization_input():
    # 対象チケット取得
    created_tickets = get_tickets_created_previous_business_day(BACKLOG_API_KEY, BACKLOG_TASK_API_URL,
                                                                BACKLOG_ISSUE_TYPE_ID,
                                                                BACKLOG_PROJECT_ID)
    updated_tickets = get_tickets_updated_previous_business_day(BACKLOG_API_KEY, BACKLOG_TASK_API_URL,
                                                                BACKLOG_ISSUE_TYPE_ID,
                                                                BACKLOG_PROJECT_ID)
    # 資産化入力有無チェック
    result_tickets = check_capitalization(created_tickets, updated_tickets)

    return result_tickets


# 対象チケットをslackに送信する
def send_to_slack(text):
    try:
        send_text_to_slack(SLACK_URL, SLACK_CHANNEL_NAME_WEBHOOK, SLACK_USER_NAME, SLACK_ICON_EMOJI_BUG, text)
    except:
        logger.error(traceback.format_exc())


# 前営業日に起票された親チケット取得
def get_tickets_created_previous_business_day(apiKey, url, issueTypeId, projectId):
    """ backlogAPIから前営業日に作成されたチケットを取り出し、json形式でresponseを返す
    """
    today = datetime.date.today()
    weekday = today.weekday()

    # 月曜日なら金曜日から取得
    date_diff = 3 if weekday == MONDAY else 1
    previous_business_day = today - datetime.timedelta(days=date_diff)

    headers = {'content-type': 'application/json'}
    params = {
        'apiKey': apiKey,
        'issueTypeId[]': issueTypeId,
        'projectId[]': projectId,
        'createdSince': previous_business_day,
        'createdUntil': today,
        'count': MAX_RESPONSE_COUNT,
        'parentChild': PARENT_TICKET,
    }

    auth = requests.auth.HTTPBasicAuth(apiKey, 'apiKey')
    response = requests.get(url, auth=auth, headers=headers, params=params)

    return json.loads(response.text)


# 前営業日に更新された親チケット取得
def get_tickets_updated_previous_business_day(apiKey, url, issueTypeId, projectId):
    """ backlogAPIから前営業日に更新されたバグチケットを取り出し、json形式でresponseを返す
    """
    today = datetime.date.today()
    weekday = today.weekday()

    # 月曜日なら金曜日から取得
    date_diff = 3 if weekday == MONDAY else 1
    previous_business_day = today - datetime.timedelta(days=date_diff)
    before_previous_business_day = previous_business_day - datetime.timedelta(days=1)

    headers = {'content-type': 'application/json'}
    params = {
        'apiKey': apiKey,
        'issueTypeId[]': issueTypeId,
        'projectId[]': projectId,
        'updatedSince': previous_business_day,
        'updatedUntil': today,
        'createdUntil': before_previous_business_day,
        'count': MAX_RESPONSE_COUNT,
        'parentChild': PARENT_TICKET,
    }

    auth = requests.auth.HTTPBasicAuth(apiKey, 'apiKey')
    response = requests.get(url, auth=auth, headers=headers, params=params)

    return json.loads(response.text)


# 資産化入力なしのチケットのみを取得する
def check_capitalization(created_tickets, updated_tickets):
    result_tickets = []
    total_tickets = created_tickets + updated_tickets

    for total_ticket in total_tickets:
        if not (is_capitalization(total_ticket['customFields'])):
            result_tickets.append(total_ticket)
    return result_tickets


# 資産化入力有無確認
def is_capitalization(customFields):
    for customField in customFields:
        # 資産化入力値チェック
        if (customField['name'] == '資産化'
                and customField['value'] is not None
                and (customField['value']['name'] == 'あり'
                     or customField['value']['name'] == 'なし')):
            return True
    return False


# 文章整形
def make_text(result_tickets):
    """slack通知文を作成する
    """
    text = ''
    text += '対象チケット数:' + str(len(result_tickets)) + '個\n'

    if len(result_tickets) == 0:
        text += '本日のチケット発番の承認と資産化の判定はありません。'
        return text
    else:
        text += 'チケット発番の承認と資産化の判定をお願いします。' + '\n'
        for result_ticket in result_tickets:
            text += result_ticket['issueType']['name'] + ':' + BACKLOG_ISSUE_PATH + str(
                result_ticket['issueKey']) + '\n'
        return text


def make_exception_text(e):
    """ 例外時のtextを作成する
    """
    text = ''
    text += '予期せぬエラーです。\n'
    text += e
    return text


# slack送信
def send_text_to_slack(slack_url, channel_name, username, icon, text):
    """ titleとbodyを繋げて、slackに送信する
    """
    send_text = text
    payload = {
        'channel': channel_name,
        'username': username,
        'text': send_text,
        'icon_emoji': icon
    }
    data = json.dumps(payload)
    requests.post(slack_url, data)
    return
