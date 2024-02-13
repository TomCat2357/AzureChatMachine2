# %%

import streamlit as st
from streamlit.web.server.websocket_headers import _get_websocket_headers
import logging
from logging.handlers import TimedRotatingFileHandler
from bokeh.models.widgets import Div
from typing import Set, Any, List, Generator, Iterable, Dict
import openai, os, redis, time, json, tiktoken, datetime
import numpy as np
from copy import copy
from concurrent.futures import ThreadPoolExecutor


hide_deploy_button_style = """
<style>
.stDeployButton {display:none;}
</style>
"""
st.markdown(hide_deploy_button_style, unsafe_allow_html=True)

def trim_tokens(
    messages: List[dict], max_tokens: int, model: str = "gpt-3.5-turbo-0301"
) -> List[dict]:
    """
    メッセージのトークン数が指定した最大トークン数を超える場合、
    メッセージの先頭から順に削除し、トークン数を最大トークン数以下に保つ。

    引数:
        messages (List[dict]): メッセージのリスト。
        max_tokens (int): 最大トークン数。
        model (str): モデル名（デフォルトは'gpt-3.5-turbo-0301'）。

    戻り値:
        List[dict]: トークン数が最大トークン数以下になったメッセージのリスト。
    """
    # 無限ループを開始
    while True:
        # 現在のメッセージのトークン数を計算
        total_tokens = calc_token_tiktoken(str(messages), model=model)
        # トークン数が最大トークン数以下になった場合、ループを終了
        if total_tokens <= max_tokens:
            break
        # トークン数が最大トークン数を超えている場合、メッセージの先頭を削除
        messages.pop(0)

    # 修正されたメッセージ���リストを返す
    return messages


def response_chatgpt(
    prompt: List[dict], model: str = "gpt-3.5-turbo", stream: bool = True
) -> Generator:
    """
    ChatGPTからのレスポンスを取得します。

    引数:
        prompt (List[dict]): 過去のメッセージとユーザーのメッセージが入ったリストユーザーからのメッセージ。
        model (str): 使用するChatGPTのモデル名。デフォルトは"gpt-3.5-turbo"。

    戻り値:
        response: ChatGPTからのレスポンス。
    """
    # logger.debug(role(user_msg))
    logger.debug(f"trim_tokens前のprompt: {prompt}")
    logger.debug(f"trim_tokens前のpromptのトークン数: {calc_token_tiktoken(str(prompt))}")
    # logger.debug(f"trim_tokens前のmessages_role: {type(messages)}")

    prompt = trim_tokens(prompt, INPUT_MAX_TOKENS)
    logger.debug(f"trim_tokens後のprompt: {str(prompt)}")
    logger.debug(f"trim_tokens後のpromptのトークン数: {calc_token_tiktoken(str(prompt))}")
    try:
        logger.info(
            f"Sending request to OpenAI API with prompt: {prompt}, model : {model}"
        )

        response = openai.ChatCompletion.create(
            model=model,
            messages=prompt,
            stream=stream,
        )
    except Exception as e:
        logger.error(f"Error while communicating with OpenAI API: {e}")
        raise

    return response, prompt


def calc_token_tiktoken(
    chat: str, encoding_name: str = "", model: str = "gpt-3.5-turbo-0301"
) -> int:
    """
    # 引数の説明:
    # chat: トーク��数を計算するテキスト。このテキストがAIモデルによってどのようにエンコードされるかを分析します。

    # encoding_name: 使用するエンコーディングの名前。この引数を指定すると、そのエンコーディングが使用されます。
    # 例えば 'utf-8' や 'ascii' などのエンコーディング名を指定できます。指定しない場合は、modelに基づいてエンコーディングが選ばれます。

    # model: 使用するAIモデルの名前。この引数は、特定のAIモデルに対応するエンコーディングを自動で選択するために使用されます。
    # 例えば 'gpt-3.5-turbo-0301' というモデル名を指定すれば、そのモデルに適したエンコーディングが選ばれます。
    # encoding_nameが指定されていない場合のみ、この引数が使用されます。
    """
    chat = str(chat)
    # エンコーディングを決定する
    if encoding_name:
        # encoding_nameが指定されていれば、その名前でエンコーディングを取得する
        encoding = tiktoken.get_encoding(encoding_name)
    elif model:
        # modelが指定されていれば、そのモデルに対応するエンコーディングを取得する
        encoding = tiktoken.get_encoding(tiktoken.encoding_for_model(model).name)
    else:
        # 両方とも指定されていない場合はエラーを投げる
        raise ValueError("Both encoding_name and model are missing.")

    # テキストをトークンに変換し、その数を数える
    num_tokens = len(encoding.encode(chat))
    return num_tokens


def check_rate_limit_exceed(
    redis_client: redis.Redis,
    key_name: str = "access",
    late_limit: int = 1,
    late_limit_period: float = 1.0,
) -> bool:
    """
    Checks if the rate limit exceeds for a given period.

    Args:
        redis_client (redis.Redis): The Redis client object.
        key_name : Redis client key name.
        late_limit (int, optional): The maximum number of access data within a certain period. Defaults to 1.
        late_limit_period (float, optional): The period in seconds. If the number of access data within this period is less than `late_limit`, the data from the previous day is also retrieved. Defaults to 1.0.

    Returns:
        bool: True if the rate limit is exceeded, False otherwise.
    """
    # Get the current timestamp
    now = time.time()
    # Retrieve the access data for the current date from the Redis client
    access_data = redis_client.zrangebyscore(
        key_name,
        now - late_limit_period,
        "+inf",
    )

    # Log the number of past access data
    logger.debug(f"Number of past access data: {len(access_data)}")
    # If the number of access data is less than the late limit, return False
    if len(access_data) < late_limit:
        return False
    # Otherwise, return True
    else:
        return True


def initialize_logger(user_id=""):
    class CustomLogger(logging.LoggerAdapter):
        def __init__(self, logger, user_id):
            super().__init__(logger, {})
            self.user_id = user_id

        def process(self, msg, kwargs):
            return f"{self.user_id} - {msg}", kwargs

    # ロガーを初期化する関数
    # ロガーオブジェクトを取得または作成します
    logger = logging.getLogger(__name__)
    # ロガーのレベルをDEBUGに設定します
    logger.setLevel(logging.DEBUG)

    # ログメッセージのフォーマットを設定します
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # コンソールへのハンドラを作成し、設定します
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # ファイルへのハンドラを作成し、設定します
    file_handler = TimedRotatingFileHandler(
        "../log/streamlit_logfile.log", when="midnight", interval=1, backupCount=7
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    # ログファイルの日付形式を設定します
    file_handler.suffix = "%Y-%m-%d"

    # ロガーにハンドラを追加します
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    if user_id:
        return CustomLogger(logger, user_id)
    else:
        return logger
def logout(login_time=0):
    # 新しいタブでログアウトページを開く
    js_open_new_tab = f"window.location.replace('{LOGOUT_URL}')"
    # JavaScriptを組み合わせる
    js = f"{js_open_new_tab}"
    html = '<img src onerror="{}">'.format(js)
    div = Div(text=html)
    if login_time:
        redisCliLoginTime.hset(USER_ID, login_time, str(False))
    st.bokeh_chart(div)
    time.sleep(10)
    st.rerun()

def redisCliTitleAtUserRecord(prompt: List[Dict[str, str]], timestamp: int, model: str, session_id: str, prompt_id: str, user_id: str) -> None:
    """
    過去のチャットをRedisに記録します。

    Args:
        prompt (List[Dict[str, str]]):   チャットのプロンプトのリスト。
        timestamp (int):   チャットのタイムスタンプ。
        model (str):   チャットに使用されるモデルの名前。
        session_id (str):   チャットのセッションID。
        prompt_id (str):   プロンプトのID。
        user_id (str):   ユーザーのID。
    """
    # Redisにチャットの記録がすでに存在するかチェック
    if not redisCliTitleAtUser.hexists(user_id, session_id):
        #   タイトルを生成するためのプロンプトを作成
        prompt_for_title = copy(prompt[:1])
        add_prompt = (
            "以下のユーザーメッセージから適切なタイトルを生成してください。"
            "メッセージの主要な内容とトーンを考慮し、簡潔かつ的確なタイトルを提案してください。"
            "メッセージ: "
        )
        add_prompt_token_num = calc_token_tiktoken(add_prompt)
        count =   0
        #   タイトルの生成を試みるループ
        while True:
            #   入力トークン数が最大トークン数を超えないかチェック
            if (
                INPUT_MAX_TOKENS
                >= calc_token_tiktoken(str(prompt_for_title))
                + add_prompt_token_num
            ):
                break
            #   カウンタをインクリメント
            count += 1
            #   カウンタが100を超えたら終了
            if count >   100:
                return
            #   プロンプトの内容を1文字削除
            prompt_for_title[0]["content"] = prompt_for_title[0]["content"][:-1]
        #   プロンプトに追加のプロンプトを追加
        prompt_for_title[0]["content"] = add_prompt + prompt_for_title[0]["content"]
        # ChatGPTからタイトルのレスポンスを取得
        response, prompt_for_title = response_chatgpt(
            prompt_for_title,
            model="gpt-3.5-turbo",
            stream=False,
        )

        #   タイトルの送信に使用したトークン数を記録
        redisCliChatData.hset(
            f'sendForTitle_{model}',
            prompt_id,
            calc_token_tiktoken(prompt_for_title)
        )
        #   レスポンスからタイトルを抽出
        title = response["choices"][0]["message"].get("content", "")
        logger.info(f"タイトルのレスポンス: {title}")
        #   タイトルの受け入れに使用したトークン数を記録
        redisCliChatData.hset(
            f'acceptForTitle_{model}',
            prompt_id,
            calc_token_tiktoken(title)
        )
    else:
        #   チャットの記録が存在する場合、タイトルを取得
        title = redisCliTitleAtUser.hget(user_id, session_id).decode()
    #   チャットをRedisに記録
    redisCliTitleAtUser.hset(
        user_id,
        session_id,
        title,
    )

# 定数定義
# 環境変数からDOMAIN_NAMEを取得
DOMAIN_NAME = os.environ.get('DOMAIN_NAME', 'localhost')

headers = _get_websocket_headers()



#"""
try:
    USER_ID = headers["Oidc_claim_sub"]
    MY_NAME = (
        (headers.get("Oidc_claim_family_name", " ") + " " +\
            headers.get("Oidc_claim_given_name", " "))
        .encode("latin1")
        .decode("utf8")
    )
except Exception as e:
    st.warning(e)
    USER_ID = "ERRORID"
    MY_NAME = "ERROR IAM"
    headers = {"Oidc_claim_exp" : int(time.time())}
    #logout(0)

LOGOUT_URL = f"https://{DOMAIN_NAME}/logout"

# Streamlitのsession_stateを使ってロガーが初期化されたかどうかをチェック
if "logger_initialized" not in st.session_state:
    logger = initialize_logger(USER_ID)
    st.session_state["logger_initialized"] = True
else:
    logger = logging.getLogger(__name__)

executor1 = ThreadPoolExecutor(1)

# USER_ID : AzureEntraIDで与えられる"Oidc_claim_sub"
# session_id : 一連のChatのやり取りをsessionと呼び、それに割り振られたID。USER_IDとsession作成時間のナノ秒で構成。"{}_{:0>20}".format(USER_ID, int(time.time_ns())
# prompt_id : sessionのうち、そのchat数で管理されているID。session_idとそのchat数で構成。f"{session_id}_{chat数:0>6}"

# redisCliPrompt : session_idでchat_messageを管理する。構造 {session_id : [{"role": "user", "content": user_msg},{"role": "assistant", "content": assistant_msg} ,...]}
redisCliPrompt = redis.Redis(host="redis_6379", port=6379, db=0)
# redisCliUserSetting : USER_IDでmodelを管理する。構造{USER_ID : model}
redisCliUserSetting = redis.Redis(host="redis_6379", port=6379, db=1)
# redisCliTitleAtUser : USER_IDとsession_idでタイトルを管理する。構造{USER_ID : {session_id, timestamp}}
redisCliTitleAtUser = redis.Redis(host="redis_6379", port=6379, db=2)
# redisCliAccessTime : prompt_idとscoreとしてunixtimeを管理。構造{'access' : {prompt_id : unixtime(as score)}}
redisCliAccessTime = redis.Redis(host="redis_6379", port=6379, db=3)
# redisCliLoginTime : USER_IDとlogin_timeを管理する。ログイン済みだとTrue、ログアウト済みだとFalse。構造{USER_ID : {login_time : status(True or False)}}
redisCliLoginTime = redis.Redis(host="redis_6379", port=6379, db=4)
# redisCliChatData : kind（送信、受信、タイトル送信、タイトル送信）とprompt_idでトークン数を管理。構造{kind: {prompt_id : token_count(int)}}
redisCliChatData = redis.Redis(host="redis_6379", port=6379, db=5)




login_time = (int(headers["Oidc_claim_exp"]) - 3600) * 10**9
# st.warning(str(int(time.time()) - login_time))
if not redisCliLoginTime.hexists(USER_ID, login_time):
    redisCliLoginTime.hset(USER_ID, login_time, str(True))

if not eval(redisCliLoginTime.hget(USER_ID, login_time).decode()):
    st.warning("ログアウトされました。ブラウザを閉じてください")
    time.sleep(5)
    st.rerun()


# APIキーの設定
openai.api_key = os.environ["OPENAI_API_KEY"]
ASSISTANT_WARNING = (
    "注意：私はAIチャットボットで、情報が常に最新または正確であるとは限りません。重要な決定をする前には、他の信頼できる情報源を確認してください。"
)
# 利用可能なGPTモデルのリスト
AVAILABLE_MODELS: dict = json.loads(os.environ["AVAILABLE_MODELS"])

LATE_LIMIT: dict = json.loads(os.environ["LATE_LIMIT"])
LATE_LIMIT_COUNT: int = LATE_LIMIT["COUNT"]
LATE_LIMIT_PERIOD: float = LATE_LIMIT["PERIOD"]


# %%




# Streamlitアプリの開始時にセッション状態を初期化
if "id" not in st.session_state:
    logger.debug("session initialized")
    st.session_state['id'] = "{}_{:0>20}".format(USER_ID, int(time.time_ns()))
    # もしUSER_IDに対応するモデルが設定されていない場合、最初の利用可能なモデルを設定
    if not redisCliUserSetting.hexists(USER_ID, "model"):
        redisCliUserSetting.hset(USER_ID, "model", list(AVAILABLE_MODELS.keys())[0])
    # もしUSER_IDに対応するモデルが利用可能なモデルのリストに含まれていない場合、最初の利用可能なモデルを設定
    if redisCliUserSetting.hget(USER_ID, "model").decode() not in AVAILABLE_MODELS:
        redisCliUserSetting.hset(USER_ID, "model", list(AVAILABLE_MODELS.keys())[0])


# 過去の最大トークン数
# INPUT_MAX_TOKENS = 20

logger.debug(f"session_id first : {st.session_state['id']}")

st.title(MY_NAME + "さんとのチャット")




if st.sidebar.button("Logout"):
    
    logout(login_time)

# Streamlitのサイドバーに利用可能なGPTモデルを選択するためのドロップダウンメニューを追加
model = redisCliUserSetting.hget(USER_ID, "model").decode()

redisCliUserSetting.hset(
    USER_ID,
    "model",
    st.sidebar.selectbox(
        "GPTモデルを選択してください",  # GPTモデルを選択するためのドロップダウンメニューを表示
        AVAILABLE_MODELS,  # 利用可能なGPTモデルのリスト
        index=list(AVAILABLE_MODELS).index(  # 現在のモデルのインデックスを取得
        model      # 現在のモデルを取得
        ),
    ),  # 選択されたモデルを設定
)
INPUT_MAX_TOKENS = AVAILABLE_MODELS[model]


# サイドバーに「New chat」ボタンを追加します。
# ボタンがクリックされたときにアプリケーションを再実行します。
if st.sidebar.button("🔄 **New chat**"):
    del st.session_state['id']
    st.rerun()

#  7日前の日時を取得し、その日の深夜0時を表すdatetimeオブジェクトを作成
seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
seven_days_ago_midnight = seven_days_ago.replace(
    hour=0, minute=0, second=0, microsecond=0
)

#  7日前の深夜0時をUNIXタイムスタンプ（秒単位の時間）に変換
seven_days_ago_unixtime = int(seven_days_ago_midnight.timestamp())

# Redisの"access"スコアレッドにおいて、7日前のUNIXタイムスタンプよりも大きいスコアを持つpromptIDを取得
prompt_id_with_chat_num_within_last_seven_days : List[bytes] = redisCliAccessTime.zrangebyscore(
    "access", seven_days_ago_unixtime, "+inf"
)

#  取得したpromptIDからsessionIDを抽出し、セットに格納
session_id_within_last_seven_days : Set[str] = {
    "_".join(id_num.decode().split("_")[:-1])
    for id_num in prompt_id_with_chat_num_within_last_seven_days
}

#  USER_IDについての、7日以内のsession_idとtitleを抽出し、辞書に格納
user_chats_within_last_seven_days : Dict[str, str] = {
    session_id.decode(): title.decode()
    for session_id, title \
        in redisCliTitleAtUser.hgetall(USER_ID).items()
    if session_id.decode() in session_id_within_last_seven_days
}

#  7日以内のチャットデータをタイムスタンプの降順でソート
user_chats_within_last_seven_days_sorted: list[tuple] = sorted(
    user_chats_within_last_seven_days.items(), reverse=True
)

st.sidebar.markdown(
    "<p style='font-size:20px; color:#FFFF00;'>過去のチャット</p>", unsafe_allow_html=True
)

for session_id, title in user_chats_within_last_seven_days_sorted:
    if len(title) > 15:
        title = title[:15] + "..."
    if st.sidebar.button(title):
        # ボタンがクリックされた場合、session_idをst.session_state['id']に代入
        st.session_state['id'] = session_id
        # logger.debug(f'sessin id button : {st.session_state['id']} clicked')
        # 画面をリフレッシュ
        st.rerun()

# アシスタントからの警告を載せる
with st.chat_message("assistant"):
    st.write(ASSISTANT_WARNING)


# with st.chat_message("assistant"):
#    for key, value in headers.items():
##        st.write(f'key : {key}, value : {value}')

# 以前のチャットログを表示
for chat in redisCliPrompt.lrange(st.session_state['id'], 0, -1):
    chat = json.loads(chat)
    with st.chat_message(chat["role"]):
        st.write(chat["content"])

# ユーザー入力
user_msg: str = st.chat_input("ここにメッセージを入力")

# 処理開始
if user_msg:
    # logger.debug(f'session_id second : {st.session_state['id']}')

    # 最新のメッセージを表示
    with st.chat_message("user"):
        st.write(user_msg)
    new_prompt: dict = {"role": "user", "content": user_msg}
    redisCliPrompt.rpush(st.session_state['id'], json.dumps(new_prompt))
    error_flag = False
    try:
        now = time.time()
        # 入力メッセージのトークン数を計算
        user_msg_tokens: int = calc_token_tiktoken(str([new_prompt]))
        logger.debug(f"入力メッセージのトークン数: {user_msg_tokens}")
        if user_msg_tokens > INPUT_MAX_TOKENS:
            # st.text_area("入力メッセージ", user_msg, height=100)  # メッセージを再表示
            # st.warning("メッセージが長すぎます。短くしてください。" f"({user_msg_tokens}tokens)")
            raise Exception("メッセージが長すぎます。短くしてください。" f"({user_msg_tokens}tokens)")
        if check_rate_limit_exceed(
            redisCliAccessTime,
            key_name="access",
            late_limit=LATE_LIMIT_COUNT,
            late_limit_period=LATE_LIMIT_PERIOD,
        ):
            raise Exception("アクセス数が多いため、接続できません。しばらくお待ちください。")
        prompt = [
            json.loads(prompt)
            for prompt in redisCliPrompt.lrange(st.session_state['id'], 0, -1)
        ]
        response, prompt = response_chatgpt(
            prompt,
            model=model,
            stream=True,
        )
    except Exception as e:
        error_flag = True
        st.warning(e)
        # エラーが出たので今回のユーザーメッセージを削除する
        redisCliPrompt.rpop(st.session_state['id'], 1)
    if not error_flag:
        
        
        prompt_id = f"{st.session_state['id']}_{redisCliPrompt.llen(st.session_state['id']):0>6}"
        
        redisCliAccessTime.zadd(
            "access",
            {
                prompt_id: now
            },
        )
        redisCliChatData.hset(
            f'send_{model}',
            prompt_id,
            calc_token_tiktoken(prompt)
        )



        # logger.debug('redisCliTitleAtUserRecord submit')

        executor1.submit(
            redisCliTitleAtUserRecord,
            prompt,
            now,
            model,
            st.session_state['id'],
            prompt_id, 
            USER_ID,
        )

        assistant_prompt = {"role": "assistant", "content": ""}
        redisCliPrompt.rpush(st.session_state['id'], json.dumps(assistant_prompt))
        prompt_length = redisCliPrompt.llen(st.session_state['id'])


        with st.chat_message("assistant"):
            assistant_msg = ""
            assistant_response_area = st.empty()
            #num_prompt = 0
            for chunk in response:
                # 回答を逐次表示
                tmp_assistant_msg = chunk["choices"][0]["delta"].get("content", "")
                assistant_msg += tmp_assistant_msg
                assistant_prompt["content"] = assistant_msg
                redisCliPrompt.lset(
                    st.session_state['id'], prompt_length - 1, json.dumps(assistant_prompt)
                )
                num_prompt = calc_token_tiktoken(assistant_msg)
                redisCliChatData.hset(
                    f'accept_{model}',
                    prompt_id,
                    num_prompt                    
                    )
                
                assistant_response_area.write(assistant_msg)
            logger.info(f"Response for chat : {assistant_msg}")
        # logger.debug('Rerun')
        st.rerun()

    # 処理終了

# %%
