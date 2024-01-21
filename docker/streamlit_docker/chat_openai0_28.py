# %%

import streamlit as st
import logging
from logging.handlers import TimedRotatingFileHandler


def initialize_logger(user_id=""):
    class CustomLogger(logging.LoggerAdapter):
        def __init__(self, logger, user_id):
            super().__init__(logger, {})
            self.user_id = user_id

        def process(self, msg, kwargs):
            return f"{self.user_id} - {msg}", kwargs
    #ロガーを初期化する関数
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

USER_ID = "TESTID"

# Streamlitのsession_stateを使ってロガーが初期化されたかどうかをチェック
if "logger_initialized" not in st.session_state:
    logger = initialize_logger(USER_ID)
    st.session_state["logger_initialized"] = True
else:
    logger = logging.getLogger(__name__)

from typing import Any, List, Generator, Iterable
import openai, os, redis, time, json, tiktoken, datetime, requests
import numpy as np
from threading import Thread
from queue import Queue, Empty
from copy import copy
from concurrent.futures import ThreadPoolExecutor

executor1 = ThreadPoolExecutor(1)

redisCliPrompt = redis.Redis(host="redis_6379", port=6379, db=0)
redisCliUserSetting = redis.Redis(host="redis_6379", port=6379, db=1)
redisCliPastChat = redis.Redis(host="redis_6379", port=6379, db=2)
redisCliAccessTime = redis.Redis(host="redis_6379", port=6379, db=3)


def trim_tokens(
    messages: List[dict], max_tokens: int, model_name: str = "gpt-3.5-turbo-0301"
) -> List[dict]:
    """
    メッセージのトークン数が指定した最大トークン数を超える場合、
    メッセージの先頭から順に削除し、トークン数を最大トークン数以下に保つ。

    引数:
        messages (List[dict]): メッセージのリスト。
        max_tokens (int): 最大トークン数。
        model_name (str): モデル名（デフォルトは'gpt-3.5-turbo-0301'）。

    戻り値:
        List[dict]: トークン数が最大トークン数以下になったメッセージのリスト。
    """
    # 無限ループを開始
    while True:
        # 現在のメッセージのトークン数を計算
        total_tokens = calc_token_tiktoken(str(messages), model_name=model_name)
        # トークン数が最大トークン数以下になった場合、ループを終了
        if total_tokens <= max_tokens:
            break
        # トークン数が最大トークン数を超えている場合、メッセージの先頭を削除
        messages.pop(0)

    # 修正されたメッセージ���リストを返す
    return messages


def response_chatgpt(
    prompt: List[dict], model_name: str = "gpt-3.5-turbo", stream: bool = True
) -> Generator:
    """
    ChatGPTからのレスポンスを取得します。

    引数:
        prompt (List[dict]): 過去のメッセージとユーザーのメッセージが入ったリストユーザーからのメッセージ。
        model_name (str): 使用するChatGPTのモデル名。デフォルトは"gpt-3.5-turbo"。

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
            f"Sending request to OpenAI API with prompt: {prompt}, model_name : {model_name}"
        )

        response = openai.ChatCompletion.create(
            model=model_name,
            messages=prompt,
            stream=stream,
        )
    except Exception as e:
        logger.error(f"Error while communicating with OpenAI API: {e}")
        raise

    return response


def calc_token_tiktoken(
    chat: str, encoding_name: str = "", model_name: str = "gpt-3.5-turbo-0301"
) -> int:
    """
    # 引数の説明:
    # chat: トーク��数を計算するテキスト。このテキストがAIモデルによってどのようにエンコードされるかを分析します。

    # encoding_name: 使用するエンコーディングの名前。この引数を指定すると、そのエンコーディングが使用されます。
    # 例えば 'utf-8' や 'ascii' などのエンコーディング名を指定できます。指定しない場合は、model_nameに基づいてエンコーディングが選ばれます。

    # model_name: 使用するAIモデルの名前。この引数は、特定のAIモデルに対応するエンコーディングを自動で選択するために使用されます。
    # 例えば 'gpt-3.5-turbo-0301' というモデル名を指定すれば、そのモデルに適したエンコーディングが選ばれます。
    # encoding_nameが指定されていない場合のみ、この引数が使用されます。
    """
    # エンコーディングを決定する
    if encoding_name:
        # encoding_nameが指定されていれば、その名前でエンコーディングを取得する
        encoding = tiktoken.get_encoding(encoding_name)
    elif model_name:
        # model_nameが指定されていれば、そのモデルに対応するエンコーディングを取得する
        encoding = tiktoken.get_encoding(tiktoken.encoding_for_model(model_name).name)
    else:
        # 両方とも指定されていない場合はエラーを投げる
        raise ValueError("Both encoding_name and model_name are missing.")

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




# APIキーの設定
openai.api_key = os.environ["OPENAI_API_KEY"]
ASSISTANT_WARNING = (
    "注意：私はAIチャットボットで、情報が常に最新または正確であるとは限りません。重要な決定をする前には、他の信頼できる情報源を確認してください。"
)
# 利用可能なGPTモデルのリスト
AVAILABLE_MODELS : dict = json.loads(os.environ["AVAILABLE_MODELS"])

LATE_LIMIT : dict = json.loads(os.environ["LATE_LIMIT"])
LATE_LIMIT_COUNT : int = LATE_LIMIT["COUNT"]
LATE_LIMIT_PERIOD : float = LATE_LIMIT["PERIOD"]


# %%
# Streamlitアプリの開始時にセッション状態を初期化
if "id" not in st.session_state:
    logger.debug("session initialized")
    st.session_state["id"] = "{}_{:0>20}".format(USER_ID, int(time.time_ns()))
    # もしUSER_IDに対応するモデルが設定されていない場合、最初の利用可能なモデルを設定
    if not redisCliUserSetting.hexists(USER_ID, "model"):
        redisCliUserSetting.hset(USER_ID, "model", list(AVAILABLE_MODELS.keys())[0])
    # もしUSER_IDに対応するモデルが利用可能なモデルのリストに含まれていない場合、最初の利用可能なモデルを設定
    elif redisCliUserSetting.hget(USER_ID, "model").decode() not in AVAILABLE_MODELS:
        redisCliUserSetting.hset(USER_ID, "model", list(AVAILABLE_MODELS.keys())[0])


# 過去の最大トークン数
# INPUT_MAX_TOKENS = 20

logger.debug(f"session_id first : {st.session_state.id}")

st.title("StreamlitのChatGPTサンプル")

# 定数定義


# Streamlitのサイドバーに利用可能なGPTモデルを選択するためのドロップダウンメニューを追加
redisCliUserSetting.hset(
    USER_ID,
    "model",
    st.sidebar.selectbox(
        "GPTモデルを選択してください",  # GPTモデルを選択するためのドロップダウンメニューを表示
        AVAILABLE_MODELS,  # 利用可能なGPTモデルのリスト
        index=list(AVAILABLE_MODELS).index(  # 現在のモデルのインデックスを取得
            redisCliUserSetting.hget(USER_ID, "model").decode()  # 現在のモデルを取得
        ),
    ),  # 選択されたモデルを設定
)
INPUT_MAX_TOKENS = AVAILABLE_MODELS[redisCliUserSetting.hget(USER_ID, "model").decode()]


# サイドバーに「New chat」ボタンを追加します。
# ボタンがクリックされたときにアプリケーションを再実行します。
if st.sidebar.button("🔄 **New chat**"):
    del st.session_state["id"]
    st.rerun()

# 7日分の時間を戻る
seven_days_ago = datetime.datetime.now()
seven_days_ago_midnight = seven_days_ago.replace(
    hour=0, minute=0, second=0, microsecond=0
)
seven_days_ago_unixtime = int(seven_days_ago_midnight.timestamp())
session_id_with_chat_num_within_last_seven_days = redisCliAccessTime.zrangebyscore(
    "access", seven_days_ago_unixtime, "+inf"
)
session_id_within_last_seven_days = {
    "_".join(id_num.decode().split("_")[:-1])
    for id_num in session_id_with_chat_num_within_last_seven_days
}
user_chats = redisCliPastChat.hgetall(USER_ID)
user_chats_within_last_seven_days: dict = {
    session_id.decode(): json.loads(chat_data)
    for session_id, chat_data in user_chats.items()
    if session_id.decode() in session_id_within_last_seven_days
}

user_chats_within_last_seven_days_sorted: list[tuple] = sorted(
    user_chats_within_last_seven_days.items(), reverse=True
)

st.sidebar.markdown(
    "<p style='font-size:20px; color:#FFFF00;'>過去のチャット</p>", unsafe_allow_html=True
)

for session_id, info in user_chats_within_last_seven_days_sorted:
    # print(info)
    title = info["title"]
    if len(title) > 15:
        title = title[:15] + "..."
    if st.sidebar.button(title):
        # ボタンがクリックされた場合、session_idをst.session_state.idに代入
        st.session_state["id"] = session_id
        # logger.debug(f'sessin id button : {st.session_state.id} clicked')
        # 画面をリフレッシュ
        st.rerun()

# アシスタントからの警告を載せる
with st.chat_message("assistant"):
    st.write(ASSISTANT_WARNING)


# 以前のチャットログを表示
for chat in redisCliPrompt.lrange(st.session_state.id, 0, -1):
    chat = json.loads(chat)
    with st.chat_message(chat["role"]):
        st.write(chat["content"])

# ユーザー入力
user_msg: str = st.chat_input("ここにメッセージを入力")

# 処理開始
if user_msg:
    # logger.debug(f'session_id second : {st.session_state.id}')

    # 最新のメッセージを表示
    with st.chat_message("user"):
        st.write(user_msg)
    new_prompt: dict = {"role": "user", "content": user_msg}
    redisCliPrompt.rpush(st.session_state.id, json.dumps(new_prompt))
    error_flag = False
    try:
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
            for prompt in redisCliPrompt.lrange(st.session_state.id, 0, -1)
        ]
        response = response_chatgpt(
            prompt,
            model_name=redisCliUserSetting.hget(USER_ID, "model").decode(),
            stream=True,
        )
    except Exception as e:
        error_flag = True
        st.warning(e)
        # エラーが出たので今回のユーザーメッセージを削除する
        redisCliPrompt.rpop(st.session_state.id, 1)
    if not error_flag:
        now = time.time()
        redisCliAccessTime.zadd(
            "access",
            {
                f"{st.session_state.id}_{redisCliPrompt.llen(st.session_state.id):0>6}": now
            },
        )

        def redisCliPastChatRecord(prompt, timestamp, model, session_id):
            # logger.debug('redisCliPastChatRecord start')
            if not redisCliPastChat.hexists(USER_ID, session_id):
                prompt_for_title = copy(prompt[0])
                add_prompt = "以下のユーザーメッセージから適切なタイトルを生成してください。メッセージの主要な内容とトーンを考慮し、簡潔かつ的確なタイトルを提案してください。メッセージ: "
                add_prompt_token_num = calc_token_tiktoken(add_prompt)
                count = 0
                while True:
                    if (
                        INPUT_MAX_TOKENS
                        >= calc_token_tiktoken(str([prompt_for_title]))
                        + add_prompt_token_num
                    ):
                        break
                    count += 1
                    if count > 100:
                        return
                    prompt_for_title["content"] = prompt_for_title["content"][:-1]
                prompt_for_title["content"] = add_prompt + prompt_for_title["content"]
                # logger.debug(f'prompt_for_title : {prompt_for_title}')
                response = response_chatgpt(
                    [prompt_for_title],
                    model_name="gpt-3.5-turbo",
                    stream=False,
                )
                title = response["choices"][0]["message"].get("content", "")
                logger.info(f"Response for title : {title}")
                # logger.debug(f"title : {title}")
            else:
                title = json.loads(redisCliPastChat.hget(USER_ID, session_id))["title"]
            redisCliPastChat.hset(
                USER_ID,
                session_id,
                json.dumps({"timestamp": timestamp, "model": model, "title": title}),
            )
            # except Exception:
            #    traceback.print_exc()

        # logger.debug('redisCliPastChatRecord submit')

        executor1.submit(
            redisCliPastChatRecord,
            prompt,
            now,
            redisCliUserSetting.hget(USER_ID, "model").decode(),
            st.session_state.id,
        )

        assistant_prompt = {"role": "assistant", "content": ""}
        redisCliPrompt.rpush(st.session_state.id, json.dumps(assistant_prompt))
        prompt_length = redisCliPrompt.llen(st.session_state.id)

        with st.chat_message("assistant"):
            assistant_msg = ""
            assistant_response_area = st.empty()
            for chunk in response:
                # 回答を逐次表示
                tmp_assistant_msg = chunk["choices"][0]["delta"].get("content", "")
                assistant_msg += tmp_assistant_msg
                assistant_prompt["content"] = assistant_msg
                redisCliPrompt.lset(
                    st.session_state.id, prompt_length - 1, json.dumps(assistant_prompt)
                )
                assistant_response_area.write(assistant_msg)
            logger.info(f"Response for chat : {assistant_msg}")
        # logger.debug('Rerun')
        st.rerun()

    # 処理終了

