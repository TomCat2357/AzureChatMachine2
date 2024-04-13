# %%

import streamlit as st
from streamlit.web.server.websocket_headers import _get_websocket_headers
import pytz, re, logging, csv, io, openai, os, redis, time, json, tiktoken, datetime, hashlib, jwt, anthropic
from logging.handlers import TimedRotatingFileHandler
from bokeh.models.widgets import Div
from typing import Union, Literal, Tuple, Set, Any, List, Generator, Iterable, Dict
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from cryptography.fernet import Fernet
from anthropic.types import MessageParam
import httpx, traceback
from anthropic import NOT_GIVEN, Anthropic

hide_deploy_button_style = """
<style>
.stDeployButton {display:none;}
</style>
"""
st.markdown(hide_deploy_button_style, unsafe_allow_html=True)


def trim_tokens(
    messages: List[dict],
    max_tokens: int,
    encoding_name: str = "",
    model: str = "gpt-3.5-turbo-0301",
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
        total_tokens = calc_token_tiktoken(
            str(messages), encoding_name=encoding_name, model=model
        )
        # トークン数が最大トークン数以下になった場合、ループを終了
        if total_tokens <= max_tokens:
            break
        # トークン数が最大トークン数を超えている場合、メッセージの先頭を削除
        messages.pop(0)
        
        # messagesの長さが0になったらエラー
        if len(messages) == 0:
            raise ValueError("与えられたmessageはmax_tokens以下になりません。")
        

    # 修正されたメッセージ���リストを返す
    return messages


def response_chatmodel(
    messages: List[dict],
    model: str,
    stream: bool,
    max_tokens: int,
    custom_instruction: str = "",
) -> Tuple[Generator, List[dict]]:
    """
    指定されたモデル(OpenAIまたはAnthropic)からのレスポンスを取得します。

    引数:
        messages (List[dict]): 過去のメッセージとユーザーのメッセージが入ったリスト。
        model (str): 使用するモデル名。
        stream (bool): ストリーム処理するか。
        max_tokens (int): 生成するトークンの最大数。
    戻り値:
        response: モデルからのレスポンス。
        trimed_messages: トークン数を調整した後のメッセージリスト。
    """
    # logger.debug(role(user_msg))
    logger.debug(f"trim_tokens前のmessages: {messages}")
    logger.debug(
        f"trim_tokens前のmessagesのトークン数: {calc_token_tiktoken(str(messages))}"
    )
    # logger.debug(f"trim_tokens前のmessages_role: {type(messages)}")
    # 設定により、custorm_instructionを必要ならば付加する。
    if custom_instruction:
        messages[-1]["content"] = custom_instruction + "\n" + messages[-1]["content"]
        logger.debug(f"custom_instruction付加後のmessages: {messages}")
        logger.debug(
            f"custom_instruction付加後のmessagesのmessagesのトークン数: {calc_token_tiktoken(str(messages))}")

    trimed_messages: List[dict] = trim_tokens(messages, INPUT_MAX_TOKENS, model=model)
    logger.debug(f"trim_tokens後のmessages: {str(messages)}")
    logger.debug(
        f"trim_tokens後のmessagesのトークン数: {calc_token_tiktoken(str(messages))}"
    )

    try:
        logger.info(
            f"Sending request to OpenAI API with messages: {messages}, model : {model}"
        )
        if model[:6] == "claude":
            response = anthropic_message_function(
                messages=trimed_messages,
                client=anthropic_client,
                model=model,
                stream=stream,
                max_tokens=max_tokens,
            )

        else:
            response = openai_message_function(
                client=openai,
                model=model,
                messages=trimed_messages,
                stream=stream,
                max_tokens=max_tokens,
            )

    except Exception as e:
        logger.error(f"Error while communicating with OpenAI API: {e}")
        raise Exception(e)

    return response, trimed_messages


def calc_token_tiktoken(
    chat: str, encoding_name: str = "", model: str = "claude-3-haiku-20240307"
) -> int:
    """
    # 引数の説明:
    # chat: トーク��数を計算するテキスト。このテキストがAIモデルによってどのようにエンコードされるかを分析します。

    # encoding_name: 使用するエンコーディングの名前。この引数を指定すると、そのエンコーディングが使用されます。
    # 例えば 'utf-8' や 'ascii' などのエンコーディング名を指定できます。指定しない場合は、modelに基づいてエンコーディングが選ばれます。

    # model: 使用するAIモデルの名前。この引数は、特定のAIモデルに対応するエンコーディングを自動で選択するために使用されます。
    # 例えば 'gpt-3.5-turbo-0301' というモデル名を指定すれば、そのモデルに適したエンコーディングが選ばれます。
    # encoding_nameが指定されていない場合のみ、この引数が使用されます。
    # modelが'claude'で始まる場合はanthropic.Anthropic.count_tokensが代わりに使われます。
    """
    chat = str(chat)

    if model[:6] == "claude":
        return anthropic_client.count_tokens(chat)

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
    """
    ロガーを初期化し、ユーザーIDに基づいてカスタムロガーを返します。

    引数:
        user_id (str): ユーザーID。デフォルトは空の文字列。

    戻り値:
        logger: ユーザーIDが指定された場合はカスタムロガー、そうでない場合は通常のロガー。

    この関数は以下の処理を行います:
    1. ロガーオブジェクトを取得または作成します。
    2. ロガーのレベルをDEBUGに設定します。
    3. ログメッセージのフォーマットを設定します。
    4. コンソールへのハンドラを作成し、ロガーに追加します。
    5. ファイルへのハンドラを作成し、ロガーに追加します。
       - ファイルハンドラは日付ごとにログファイルをローテーションします。
       - ログファイルは7日分保持されます。
    6. ユーザーIDが指定された場合:
       - カスタムロガークラスを定義します。
       - カスタムロガークラスはユーザーIDをログメッセージに追加します。
       - カスタムロガーオブジェクトを返します。
    7. ユーザーIDが指定されない場合:
       - 通常のロガーオブジェクトを返します。
    """

    class CustomLogger(logging.LoggerAdapter):
        """
        カスタムロガークラス。
        ユーザーIDをログメッセージに追加します。
        """

        def __init__(self, logger, user_id):
            """
            カスタムロガーを初期化します。

            引数:
                logger: 元となるロガーオブジェクト。
                user_id (str): ユーザーID。
            """
            super().__init__(logger, {})
            self.user_id = user_id

        def process(self, msg, kwargs):
            """
            ログメッセージを処理し、ユーザーIDを追加します。

            引数:
                msg (str): ログメッセージ。
                kwargs (dict): ログメッセージに関連する追加情報。

            戻り値:
                tuple: ユーザーIDを追加したログメッセージと追加情報。
            """
            return f"{self.user_id} - {msg}", kwargs

    # ロガーオブジェクトを取得または作成します
    logger = logging.getLogger(__name__)
    # ロガーのレベルをDEBUGに設定します
    logger.setLevel(logging.DEBUG)

    # ログメッセージのフォーマットを設定します
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - line: %(lineno)d - %(message)s"
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

    # ユーザーIDが指定された場合、カスタムロガーを返します
    if user_id:
        return CustomLogger(logger, user_id)
    # ユーザーIDが指定されない場合、通常のロガーを返します
    else:
        return logger


# ユーザーのログイン処理を行う関数
def login_check(login_time: float) -> None:
    """
    ユーザーのログイン状態を確認し、必要に応じてログイン・ログアウト処理を行う関数。

    引数:
        login_time (float): ユーザーがログインした時間（UNIX時間）。

    処理の流れ:
    1. ユーザーの最後のアクセスログを取得する。
    2. 最後のアクセスログが存在しない場合、ログイン時間を登録する。
    3. 最後のアクセスログが存在する場合:
       - 最後のアクセスログの種類と時間を取得する。
       - 最後のアクセスログの種類が "LOGOUT" の場合:
         - login_timeがLOGOUT時間よりも古い場合は、ログアウト処理を行う。
         - login_timeがLOGOUT時間よりも新しい場合は、ログイン処理を行う。
       - 最後のアクセスログの種類が "ACTION" または "LOGIN" の場合:
         - 最後のアクセスログの時間が現在時刻よりも未来の場合、エラーを発生させる。
         - 最後のアクセスログから現在時刻までSESSION_TIMEOUT_PERIODを超えていた場合、ログアウト処理を行う。
         - そうでない場合、活動時間とログイン時間を更新する。
    """
    # ユーザーの最後のアクセスログを取得
    last_access_log = redisCliUserAccess.zrevrange(USER_ID, 0, 0, withscores=True)

    # 最後のアクセスログが存在しない場合、ログイン時間を登録
    redisCliUserAccess.zadd(USER_ID, {f"LOGIN_{login_time*10**9}": login_time})
    # 最後のアクセスログの種類と時間を取得
    kind: str = last_access_log[0][0].decode().split("_")[0]
    last_log_time: float = last_access_log[0][1]

    # 最後のアクセスログの種類が "LOGOUT" の場合
    if kind == "LOGOUT":
        # login_timeがLOGOUT時間よりも古い場合は、ログアウト処理を行う
        if last_log_time >= login_time:
            st.warning("ログアウトされました。ブラウザを閉じてください")
            time.sleep(3)
            st.rerun()
        # login_timeがLOGOUT時間よりも新しい場合は、ログイン処理を行う

    # 最後のアクセスログの種類が "ACTION" または "LOGIN" の場合
    else:  # kind == "ACTION" or kind == "LOGIN"
        # 最後のアクセスログの時間が現在時刻よりも未来の場合、エラーを発生させる
        if last_log_time > time.time() + 1:
            raise Exception("現在時刻よりも未来の時間の行動記録があります。")
        # 最後のアクセスログから現在時刻までSESSION_TIMEOUT_PERIODを超えていた場合、ログアウト処理を行う
        if time.time() - last_log_time > SESSION_TIMEOUT_PERIOD:
            logout()
        # そうでない場合、活動時間とログイン時間を更新する
        else:
            now = time.time()
            redisCliUserAccess.zadd(USER_ID, {f"ACTION_{now*10**9}": now})


def jump_to_url(url: str, token: str = ""):
    """
    指定されたURLに新しいタブで移動する関数。

    引数:
        url (str): 移動先のURL。
        token (str, optional): トークン。デフォルトは空の文字列。

    処理の流れ:
    1. トークンが指定されている場合、URLにトークンをクエリパラメータとして追加する。
    2. JavaScriptを使用して、新しいタブで指定されたURLを開く。
    3. Streamlitの`bokeh_chart`を使用して、JavaScriptを実行するためのHTMLを表示する。
    """
    if token:
        # トークンをクエリパラメータに追加
        url = f"{url}?token={token}"
    else:
        url = f"{url}"

    # JavaScriptを組み合わせて新しいタブで指定されたURLを開く
    js_open_new_tab = f"window.location.replace('{url}')"
    html = '<img src onerror="{}">'.format(js_open_new_tab)
    div = Div(text=html)
    st.bokeh_chart(div)


def logout():
    now = time.time()
    # ログアウト時間をRedisに記録
    redisCliUserAccess.zadd(USER_ID, {f"LOGOUT_{now*10**9}": now})
    # ログアウト後に指定されたURLにリダイレクト
    jump_to_url(LOGOUT_URL)
    # リダイレクト後にアプリケーションを再起動
    time.sleep(3)
    st.rerun()


def record_title_at_user_redis(
    messages: List[Dict[str, str]],
    session_id: str,
    timestamp: int,
) -> str:
    """
    ユーザーの最初のメッセージを元に適切なタイトルを生成し、生成されたタイトルとチャットデータをRedisに保存する。

    Args:
        messages (List[Dict[str, str]]): ユーザーのメッセージのリスト
        session_id (str): セッションID
        timestamp (int): タイムスタンプ

    Returns:
        str: 整形されたタイトル

    流れ:
        1. ユーザーの最初のメッセージを取得し、タイトル生成のためのプロンプトを作成
        2. タイトルを生成し、不要な文字を削除して整形
        3. 生成されたタイトルとチャットデータをRedisに保存
        4. 整形されたタイトルを返す
    """

    # ユーザーの最初のメッセージを取得
    first_message_content = messages[0]["content"]

    # タイトル生成のための追加メッセージ
    additional_message = (
        "以下のユーザーメッセージから完結で適切なタイトルを生成してください。"
        "疑問があっても生成してください。例えば「若者の疑問」、「悩み相談」などです。"
        "<以降メッセージ>"
    )

    # メッセージの長さがタイトルモデルの最大長を超える場合、メッセージを省略
    if (
        len(first_message_content) + len(additional_message)
        > TITLE_MODEL_CHAR_MAX_LENGTH
    ):
        half_message_length = int(
            (TITLE_MODEL_CHAR_MAX_LENGTH - len(additional_message) - 3) / 2
        )
        message_for_title = (
            additional_message
            + first_message_content[:half_message_length]
            + "..."
            + first_message_content[-half_message_length:]
        )
    else:
        message_for_title = additional_message + first_message_content

    # タイトル生成のためのプロンプトを作成
    title_prompt = [{"role": "user", "content": message_for_title}]

    # プロンプトのトークン数がタイトルモデルの最大トークン数を超える場合、プロンプトを削減
    while INPUT_MAX_TOKENS < calc_token_tiktoken(str(title_prompt), model=TITLE_MODEL):
        title_prompt[0]["content"] = title_prompt[0]["content"][:-1]

    # タイトルを生成
    generated_title, title_prompt_trimed = response_chatmodel(
        title_prompt,
        model=TITLE_MODEL,
        stream=False,
        max_tokens=16,
    )

    # プロンプトを暗号化
    title_prompt_encrypted = cipher_suite.encrypt(
        json.dumps(title_prompt_trimed).encode()
    ).decode()

    # 生成されたタイトルから不要な文字を削除
    washed_title = re.sub(
        r"TITLE|title|Title|タイトル|[:：]|[\"「『」』]|[{｛(（<＜].+[>＞）)｝}]", "", generated_title
    )
    washed_title = washed_title if washed_title else generated_title

    # 整形されたタイトルと生成されたタイトルを暗号化
    encrypted_washed_title = cipher_suite.encrypt(washed_title.encode())
    encrypted_genarated_title_response = cipher_suite.encrypt(
        json.dumps([{"role": "assistant", "content": generated_title}]).encode()
    ).decode()

    # ユーザーのタイトルをRedisに保存
    redisCliTitleAtUser.hset(USER_ID, session_id, encrypted_washed_title)

    # メッセージIDを生成
    message_id = f"{session_id}_{0:0>6}"

    # チャットデータをRedisに保存
    redisCliChatData.hset(
        message_id,
        "prompt",
        json.dumps(
            {
                "USER_ID": USER_ID,
                "messages": title_prompt_encrypted,
                "timestamp": timestamp,
                "num_tokens": calc_token_tiktoken(
                    str(title_prompt_trimed), model=TITLE_MODEL
                ),
                "model": TITLE_MODEL,
            }
        ),
    )
    redisCliChatData.expire(message_id, EXPIRE_TIME)
    redisCliChatData.hset(
        message_id,
        "response",
        json.dumps(
            {
                "USER_ID": USER_ID,
                "messages": encrypted_genarated_title_response,
                "timestamp": timestamp,
                "num_tokens": calc_token_tiktoken(generated_title, model=TITLE_MODEL),
                "model": TITLE_MODEL,
            }
        ),
    )

    return washed_title


def get_user_chats_within_last_several_days_sorted(days: int) -> list[tuple]:
    """
    指定された日数以内のユーザーのチャットデータを取得し、タイムスタンプの降順でソートして返します。

    Args:
        days (int):  指定された日数。

    Returns:
        list[tuple]:  ユーザーのチャットデータのリスト。各チャットデータはタプルで、セッションIDとタイトルのペアです。
    """
    #  指定日数前の日時を取得し、その日の深夜0時を表すdatetimeオブジェクトを作成
    several_days_ago = datetime.datetime.now() - datetime.timedelta(days=days)
    several_days_ago_midnight = several_days_ago.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    #  指定日数前の深夜0時をUNIXタイムスタンプ（秒単位の時間）に変換
    several_days_ago_unixtime = int(several_days_ago_midnight.timestamp())

    # Redisの"access"スコアレッドにおいて、指定日数前のUNIXタイムスタンプよりも大きいスコアを持つmessagesIDを取得
    messages_id_with_chat_num_within_last_several_days: List[bytes] = (
        redisCliAccessTime.zrangebyscore("access", several_days_ago_unixtime, "+inf")
    )

    #  取得したmessagesIDからsessionIDを抽出し、セットに格納
    session_id_within_last_several_days: Set[str] = {
        "_".join(id_num.decode().split("_")[:-1])
        for id_num in messages_id_with_chat_num_within_last_several_days
    }

    # USER_IDについての、指定日数以内のsession_idとtitleを抽出し、辞書に格納
    user_session_id_title_within_last_several_days: Dict[str, str] = {
        session_id.decode(): cipher_suite.decrypt(title).decode()
        for session_id, title in redisCliTitleAtUser.hgetall(USER_ID).items()
        if session_id.decode() in session_id_within_last_several_days
    }

    #  指定日数以内のチャットデータをタイムスタンプの降順でソート
    user_session_id_title_within_last_several_days_sorted: list[tuple] = sorted(
        user_session_id_title_within_last_several_days.items(), reverse=True
    )
    return user_session_id_title_within_last_several_days_sorted


# Unixタイムスタンプをローカルタイムに変換する関数
def unixtime_to_localtime(unixtime):
    utc_time = datetime.datetime.utcfromtimestamp(unixtime)
    local_time = utc_time.replace(tzinfo=pytz.utc).astimezone(
        pytz.timezone(os.environ["TZ"])
    )  # Noneを指定するとローカルタイムゾーンに変換される
    formatted_time = local_time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )  # エクセルでも扱いやすい形式にフォーマット
    return formatted_time


def get_chat_data_as_csv():
    # StringIOオブジェクトを初期化してCSVデータを保持する
    csv_output = io.StringIO()
    fieldnames = [
        "messages_id",
        "kind",
        "USER_ID",
        "model",
        "timestamp",
        "messages",
        "num_tokens",
    ]
    writer = csv.DictWriter(csv_output, fieldnames=fieldnames)

    # ヘッダーを書き込む
    writer.writeheader()

    # Redisハッシュからすべてのキーを取得する（仮のコード部分）
    keys = (
        redisCliChatData.keys()
    )  # この行は仮のコードで、実際のRedisクライアントのコードに置き換えてください。
    for key in keys:
        # 各キーのデータを取得する
        data = redisCliChatData.hgetall(key)  # この行も仮のコードです。
        for kind, value in data.items():
            value_dict = json.loads(value)
            localtime = unixtime_to_localtime(value_dict["timestamp"])
            writer.writerow(
                {
                    "USER_ID": value_dict["USER_ID"],
                    "messages_id": key.decode(),
                    "kind": kind.decode(),
                    "model": value_dict["model"],
                    "timestamp": localtime,
                    # ここで ensure_ascii=False を設定
                    "messages": json.dumps(
                        value_dict["messages"], ensure_ascii=False
                    ),  # 日本語がエスケープされずに出力される
                    "num_tokens": value_dict["num_tokens"],
                }
            )

    # CSVデータをstrとして取得する
    csv_data_str = csv_output.getvalue()
    # CSVデータをShift-JISでエンコードする
    csv_data_shift_jis = csv_data_str.encode("shift_jis", errors="replace")

    return csv_data_shift_jis


def hash_string_md5_with_salt(input_string: str) -> str:
    if not input_string:
        raise ValueError("input_stringが空です。")
    # 文字列にハッシュソルトを加えてバイトに変換
    input_bytes = (input_string + HASH_SALT).encode()
    # MD5ハッシュオブジェクトを作成
    md5_hash = hashlib.md5()
    # バイトをハッシュに更新
    md5_hash.update(input_bytes)
    # ハッシュを16進数の文字列として取得
    return md5_hash.hexdigest()


def make_jwt_token(data: dict, expire_time: float = 60.0) -> str:
    now = time.time()
    expiration_time = now + expire_time

    data_with_exp = {**data, "exp": expiration_time}
    token = jwt.encode(data_with_exp, JWT_SECRET_KEY, algorithm="HS256")
    return token


def anthropic_message_function(
    *,
    client: Anthropic,
    max_tokens: int,
    messages: Iterable[MessageParam],
    model: Union[
        str,
        Literal[
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2",
        ],
    ],
    metadata: dict = NOT_GIVEN,
    stop_sequences: List[str] = NOT_GIVEN,
    stream: bool = NOT_GIVEN,
    system: str = NOT_GIVEN,
    temperature: float = NOT_GIVEN,
    top_k: int = NOT_GIVEN,
    top_p: float = NOT_GIVEN,
    extra_headers: dict | None = None,
    extra_query: dict | None = None,
    extra_body: dict | None = None,
    timeout: float | httpx.Timeout = NOT_GIVEN,
):
    if stream:

        def chat_stream():
            with client.messages.stream(
                max_tokens=max_tokens,
                messages=messages,
                model=model,
                metadata=metadata,
                stop_sequences=stop_sequences,
                system=system,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
            ) as stream_response:
                for i, text in enumerate(stream_response.text_stream):
                    if not i:
                        yield
                    yield text

        cs = chat_stream()
        cs.__next__()
        return cs
    else:
        return (
            client.messages.create(
                max_tokens=max_tokens,
                messages=messages,
                model=model,
                metadata=metadata,
                stop_sequences=stop_sequences,
                system=system,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
            )
            .content[0]
            .text
        )


def openai_message_function(*, client: openai, messages, model, max_tokens, stream):
    if stream:

        def chat_stream():
            for i, text in enumerate(
                client.ChatCompletion.create(
                    messages=messages, model=model, max_tokens=max_tokens, stream=True
                )
            ):
                if not i:
                    yield
                yield text["choices"][0]["delta"].get("content", "")

        cs = chat_stream()
        cs.__next__()
        return cs
    else:
        return client.ChatCompletion.create(
            messages=messages, model=model, max_tokens=max_tokens, stream=False
        )["choices"][0]["message"]["content"]


# USER_ID : AzureEntraIDで与えられる"Oidc_claim_sub"
# session_id : 一連のChatのやり取りをsessionと呼び、それに割り振られたID。USER_IDとsession作成時間のナノ秒で構成。"{}_{:0>20}".format(USER_ID, int(time.time_ns())
# messages_id : sessionのうち、そのchat数で管理されているID。session_idとそのchat数で構成。f"{session_id}_{chat数:0>6}"

# redisCliMessages : session_idでchat_messageを管理する。構造 {session_id : [{"role": "user", "content": user_msg},{"role": "assistant", "content": assistant_msg} ,...]}
redisCliMessages = redis.Redis(host="redis", port=6379, db=0)
# redisCliUserSetting : USER_IDで設定を管理する。構造{USER_ID : {"model" : model_name(str), "custom_instruction" : custom_instruction(str)}
redisCliUserSetting = redis.Redis(host="redis", port=6379, db=1)
# redisCliTitleAtUser : USER_IDとsession_idでタイトルを管理する。構造{USER_ID : {session_id, timestamp}}
redisCliTitleAtUser = redis.Redis(host="redis", port=6379, db=2)
# redisCliAccessTime : messages_idとscoreとしてunixtimeを管理。構造{'access' : {messages_id : unixtime(as score)}}
redisCliAccessTime = redis.Redis(host="redis", port=6379, db=3)
# redisCliUserAccess : USER_IDと'LOGIN'、'LOGOUT'の別でscoreとしてlogin_timeを管理する。構造{USER_ID : {kind('LOGOUT' or 'LOGIN') : unixtime(as score)}}
redisCliUserAccess = redis.Redis(host="redis", port=6379, db=4)
# redisCliChatData : messages_idと'prompt'か'response'の別で、messages、トークン数、timestamp及びモデル名を管理。構造{messages_id: {kind('send' or 'accept') : {'model' : mode, 'title' : title(str), 'timestamp' : timestamp, 'messages' : messages(List[dict]), 'num_tokens' : num_tokens(int)}
redisCliChatData = redis.Redis(host="redis", port=6379, db=5)


# JWTでの鍵
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]

# メッセージを暗号化する鍵と暗号化インスタンス
ENCRYPT_KEY = os.environ["ENCRYPT_KEY"].encode()
cipher_suite = Fernet(ENCRYPT_KEY)

# ハッシュ関数に加えるソルト
HASH_SALT = os.environ["HASH_SALT"]
# SESSION_TIMEOUT_PERIOD
# ログアウトしてしまう時間を環境変数から読み込む
SESSION_TIMEOUT_PERIOD = int(os.environ.get("SESSION_TIMEOUT_PERIOD", 3600))
# 環境変数からDOMAIN_NAMEを取得
DOMAIN_NAME = os.environ.get("DOMAIN_NAME", "localhost")
LOGOUT_URL = f"https://{DOMAIN_NAME}/logout"

# CustomInstructionの最大トークン数
CUSTOM_INSTRUCTION_MAX_TOKENS = int(os.environ.get("CUSTOM_INSTRUCTION_MAX_TOKENS", 0))

# redisのキーの蒸発時間を決める。基本366日
EXPIRE_TIME = int(os.environ.get("EXPIRE_TIME", 24 * 3600 * 366))

#  アシスタントの警告メッセージ
#  ユーザーに対して表示する警告メッセージを定義します。
ASSISTANT_WARNING = "注意：私はAIチャットボットで、情報が常に最新または正確であるとは限りません。重要な決定をする前には、他の信頼できる情報源を確認してください。"

#  利用可能なGPTモデルのリスト
# 環境変数から利用可能なGPTモデルのリストをJSON形式で取得し、辞書として定義します。
AVAILABLE_MODELS: dict[str, int] = json.loads(os.environ["AVAILABLE_MODELS"])

#  レート制限の設定
# 環境変数からレート制限の設定をJSON形式で取得し、辞書として定義します。
LATE_LIMIT: dict = json.loads(os.environ["LATE_LIMIT"])

#  レート制限のカウント
#  レート制限の設定からカウントを取得し、整数として定義します。
LATE_LIMIT_COUNT: int = LATE_LIMIT["COUNT"]

#  レート制限の期間
#  レート制限の設定から期間を取得し、浮動小数点数として定義します。
LATE_LIMIT_PERIOD: float = LATE_LIMIT["PERIOD"]

#  タイトル生成モデルの設定
# 環境変数からタイトル生成モデルの設定をJSON形式で取得し、タプルとして定義します。
TITLE_MODEL: str
TITLE_MODEL_CHAR_MAX_LENGTH: int
TITLE_MODEL, TITLE_MODEL_CHAR_MAX_LENGTH = tuple(
    json.loads(os.environ["TITLE_MODEL"]).items()
)[0]

# api_costの計算用
API_COST = json.loads(os.environ["API_COST"])


headers = _get_websocket_headers()
if headers is None:
    headers = {}

# st.warning(headers)
# """
try:
    # USER_IDはemailにHASH_SALTを加えてmd5でハッシュ化してから１文字飛ばしで抽出したもの
    USER_ID: str = hash_string_md5_with_salt(headers["Oidc_claim_email"])[::2]
    # USER_ID: str = headers["Oidc_claim_email"]
    if not USER_ID:
        raise Exception("No email info in claim.")
    MY_NAME = (
        headers.get("Oidc_claim_name", "")
        .encode("latin1", errors="ignore")
        .decode("utf8", errors="ignore")
    )
    login_time = int(headers["Oidc_claim_exp"]) - 3600

except Exception as e:
    st.warning(e)
    USER_ID = "ERRORID"
    MY_NAME = "ERROR IAM"
    login_time = time.time()
    #if headers.get("Host", "")[:9] != "localhost":
        time.sleep(3)
        st.rerun()
st.warning(headers)
st.warning(USER_ID)
# headers辞書をJSON文字列に変換
headers_json = json.dumps(headers, ensure_ascii=True, indent=2)

# ダウンロードボタンを設置
# st.download_button(
#    label="headersをダウンロード",
#    data=headers_json,
#    file_name="headers.json",
#    mime="application/json",
# )
# Streamlitのsession_stateを使ってロガーが初期化されたかどうかをチェック


if "logger_initialized" not in st.session_state:
    logger = initialize_logger(USER_ID)
    st.session_state["logger_initialized"] = True
    logger.info("logger initialized!!!")
else:
    logger = logging.getLogger(__name__)
    logger.info("logger not initialized!!!")
logger.debug(f"headers : {headers}")
logger.debug(f"st.session_state : {st.session_state}")
executor1 = ThreadPoolExecutor(1)

login_check(login_time)


# APIキーの設定
# OpenAIのAPIキーを環境変数から取得して設定します。
openai.api_key = os.environ["OA_API_KEY"]

# AZURE用の設定
if os.environ.get("OA_API_TYPE"):
    openai.api_type = os.environ["OA_API_TYPE"]
if os.environ.get("OA_API_BASE"):
    openai.api_base = os.environ["OA_API_BASE"]
if os.environ.get("OA_API_VERSION"):
    openai.api_version = os.environ["OA_API_VERSION"]

anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# %%


# Streamlitアプリの開始時にセッション状態を初期化
if "id" not in st.session_state:
    logger.debug("session initialized")
    st.session_state["id"] = "{}_{:0>20}".format(USER_ID, int(time.time_ns()))
    # st.warning('not id')

    # もしUSER_IDに対応するモデルが設定されていない場合、最初の利用可能なモデルを設定
    if not redisCliUserSetting.hexists(USER_ID, "model"):
        redisCliUserSetting.hset(USER_ID, "model", list(AVAILABLE_MODELS.keys())[0])
    # もしUSER_IDに対応するモデルが利用可能なモデルのリストに含まれていない場合、最初の利用可能なモデルを設定
    if redisCliUserSetting.hget(USER_ID, "model").decode() not in AVAILABLE_MODELS:
        redisCliUserSetting.hset(USER_ID, "model", list(AVAILABLE_MODELS.keys())[0])
    # 先にcalc_token_tiktokenを実行して、cashに入れておく
    model: str = redisCliUserSetting.hget(USER_ID, "model").decode()
    calc_token_tiktoken("test", model=model)

    # accesstimeのEXPIRE_TIMEよりも古いものは消す
    redisCliAccessTime.zremrangebyscore("access", "-inf", time.time() - EXPIRE_TIME)

    # もしUSER_IDに対応するcustom instructionが設定されていない場合、''を設定
    if not redisCliUserSetting.hexists(USER_ID, "custom_instruction"):
        redisCliUserSetting.hset(
            USER_ID, "custom_instruction", cipher_suite.encrypt(b"")
        )
    # もしUSER_IDに対応するuse_custom_instruction_flagが設定されていない場合、""を設定
    if not redisCliUserSetting.hexists(USER_ID, "use_custom_instruction_flag"):
        redisCliUserSetting.hset(USER_ID, "use_custom_instruction_flag", "")


# USER_IDについてEXPIRE_TIMEを設定する。これにより最後にログインした時から１年間は消えない。
redisCliUserSetting.expire(USER_ID, EXPIRE_TIME)
redisCliUserAccess.expire(USER_ID, EXPIRE_TIME)
redisCliTitleAtUser.expire(USER_ID, EXPIRE_TIME)

logger.debug(f"session_id first : {st.session_state['id']}")

#  今日のの深夜0時を表すdatetimeオブジェクトを作成
today = datetime.datetime.now()
today_midnight = today.replace(hour=0, minute=0, second=0, microsecond=0)
#  今日の深夜0時をUNIXタイムスタンプ（秒単位の時間）に変換
today_midnight_unixtime = int(today_midnight.timestamp())

# Redisの"access"スコアレッドにおいて、指定日数前のUNIXタイムスタンプよりも大きいスコアを持つmessagesIDを取得
messages_id_within_today: List[bytes] = redisCliAccessTime.zrangebyscore(
    "access", today_midnight_unixtime, "+inf"
)
logger.debug("Now model : ")

# 今日のコスト計算

cost_team, cost_mine = 0, 0
for message_id in messages_id_within_today:
    for kind, data in redisCliChatData.hgetall(message_id).items():
        data = json.loads(data)
        # logger.debug(f'data : {data}')
        key = kind.decode() + "_" + data["model"]
        try:
            cost_team += API_COST[key]
        except KeyError:
            logger.error(f"{key} is not in available model!")

        if data.get("USER_ID") == USER_ID:
            try:
                cost_mine += API_COST[key]
            except KeyError:
                pass

st.title(MY_NAME + "さんとのチャット")

# サイドボタン
# logoutボタン
if st.sidebar.button("Logout"):
    logout()

# 今日の自分のコスト/今日のチームのコスト
st.sidebar.markdown(
    f"<p style='font-size:20px; color:green;'>{cost_mine:.3f}/{cost_team:.3f}</p>",
    unsafe_allow_html=True,
)

# 設定ボタンを作る。設定画面に飛ぶ
if st.sidebar.button("Settings"):
    token = make_jwt_token({"user_id": USER_ID}, expire_time=60)
    jump_to_url(f"https://{DOMAIN_NAME}/settings", token=token)


# Streamlitのサイドバーに利用可能なGPTモデルを選択するためのドロップダウンメニューを追加
model: str = redisCliUserSetting.hget(USER_ID, "model").decode()

redisCliUserSetting.hset(
    USER_ID,
    "model",
    st.sidebar.selectbox(
        "GPTモデルを選択してください",  # GPTモデルを選択するためのドロップダウンメニューを表示
        AVAILABLE_MODELS,  # 利用可能なGPTモデルのリスト
        index=list(AVAILABLE_MODELS).index(  # 現在のモデルのインデックスを取得
            model  # 現在のモデルを取得
        ),
    ),  # 選択されたモデルを設定
)
# modelから限界トークン数を得る。
INPUT_MAX_TOKENS = AVAILABLE_MODELS[model]["INPUT_MAX_TOKENS"]
OUTPUT_MAX_TOKENS = AVAILABLE_MODELS[model]["OUTPUT_MAX_TOKENS"]


# サイドバーに「New chat」ボタンを追加します。
# ボタンがクリックされたときにアプリケーションを再実行します。
if st.sidebar.button("🔄 **New chat**"):
    del st.session_state["id"]
    st.rerun()

# 7日前のUSERに係るsession_idとtitleとのlistを得る。
user_session_id_title_within_last_7days_sorted = (
    get_user_chats_within_last_several_days_sorted(7)
)

#  サイドバーに過去のチャットのタイトルを表示するためのマークダウンを設定
#  ユーザーが過去のチャットを参照できるように、サイドバーにタイトルを表示します。
st.sidebar.markdown(
    "<p style='font-size:20px; color:red;'>過去のチャット</p>",
    unsafe_allow_html=True,
)

#  ユーザーが過去のチャットを選択できるように、サイドバーにボタンを配置
# 過去のチャットのタイトルをボタンとして表示し、ユーザーがクリックすると、そのチャットに移動します。
titles = []
for session_id, title in user_session_id_title_within_last_7days_sorted:
    if len(title) > 15:
        title = title[:15] + "..."
    titles.append(title)
    counter = Counter(titles)
    if counter[title] > 1:
        title += str(counter[title])

    if st.sidebar.button(title):
        #  ボタンがクリックされた場合、session_idをst.session_state['id']に代入
        #  これにより、選択されたチャットのIDが現在のセッションとして設定されます。
        st.session_state["id"] = session_id
        #  画面をリフレッシュして、選択されたチャットの内容を表示
        st.rerun()

# アシスタントからの警告を載せる
with st.chat_message("assistant"):
    st.write(ASSISTANT_WARNING)


# 以前のチャットログを表示
for chat_encrypted in redisCliMessages.lrange(st.session_state["id"], 0, -1):
    chat: dict = json.loads(cipher_suite.decrypt(chat_encrypted))
    with st.chat_message(chat["role"]):
        st.write(chat["content"])


# ユーザー入力
user_msg: str = st.chat_input("ここにメッセージを入力")

logger.debug(f"user_msg : {user_msg}(type : {type(user_msg)})")
if not user_msg:
    user_msg = ""

if user_msg:

    # logger.debug(f'session_id second : {st.session_state['id']}')

    # 最新のメッセージを表示
    with st.chat_message("user"):
        st.write(user_msg)
    new_messages: Dict[str, str] = {"role": "user", "content": user_msg}
    new_messages_encrypted: bytes = cipher_suite.encrypt(
        json.dumps(new_messages).encode()
    )
    redisCliMessages.rpush(st.session_state["id"], new_messages_encrypted)
    redisCliMessages.expire(st.session_state["id"], EXPIRE_TIME)
    error_flag = False
    try:
        now: float = time.time()
        # 入力メッセージのトークン数を計算
        user_msg_tokens: int = calc_token_tiktoken(str([new_messages]), model=model)
        logger.debug(f"入力メッセージのトークン数: {user_msg_tokens}")
        if user_msg_tokens > INPUT_MAX_TOKENS:
            raise Exception(
                "メッセージが長すぎます。短くしてください。"
                f"({user_msg_tokens}tokens)"
            )
        if check_rate_limit_exceed(
            redisCliAccessTime,
            key_name="access",
            late_limit=LATE_LIMIT_COUNT,
            late_limit_period=LATE_LIMIT_PERIOD,
        ):
            raise Exception(
                "アクセス数が多いため、接続できません。しばらくお待ちください。"
            )
        messages = [
            json.loads(cipher_suite.decrypt(mes))
            for mes in redisCliMessages.lrange(st.session_state["id"], 0, -1)
        ]
        # custom_instructionの読み出し
        if redisCliUserSetting.hget(USER_ID, "use_custom_instruction_flag").decode():
            custom_instruction = cipher_suite.decrypt(
                redisCliUserSetting.hget(USER_ID, "custom_instruction")
            ).decode()
        else:
            custom_instruction = ''

        # generatorだが、エラーが起きたら一個目の生成前に止まる。
        response, trimed_messages = response_chatmodel(
            messages,
            model=model,
            stream=True,
            max_tokens=OUTPUT_MAX_TOKENS,
            custom_instruction=custom_instruction,
        )
    except Exception as e:
        error_flag = True
        logger.error(e)
        traceback.print_exc()
        st.warning(e)
        # エラーが出たので今回のユーザーメッセージを削除する
        redisCliMessages.rpop(st.session_state["id"], 1)
    if not error_flag:

        encrypted_messages: str = cipher_suite.encrypt(
            json.dumps(trimed_messages).encode()
        ).decode()

        # 初回のmessages、つまりlen(messages)が1だったらタイトルを付ける。
        if len(messages) == 1:
            # タイトルを付ける処理をする。
            title_future = executor1.submit(
                record_title_at_user_redis, messages, st.session_state["id"], now
            )
            # title = record_title_at_user_redis(messages, st.session_state["id"], now)

        # messages_idを定義。session_idにmessagesの長さを加える。
        messages_id = f"{st.session_state['id']}_{redisCliMessages.llen(st.session_state['id']):0>6}"

        redisCliAccessTime.zadd(
            "access",
            {messages_id: now},
        )
        # RedisにメッセージIDと'prompt'のキーで、モデル名、メッセージ、タイムスタンプ、トークン数を保存します。
        redisCliChatData.hset(
            messages_id,
            "prompt",
            json.dumps(
                {
                    "USER_ID": USER_ID,
                    "model": model,  #  使用するAIモデルの名前
                    "timestamp": now,  #  メッセージのタイムスタンプ
                    "messages": encrypted_messages,  #  トリムされ暗号化されたメッセージのリスト
                    "num_tokens": calc_token_tiktoken(
                        str(trimed_messages), model=model
                    ),  #  トリムされたメッセージのトークン数
                }
            ),
        )
        redisCliChatData.expire(messages_id, EXPIRE_TIME)

        #  アシスタントのメッセージを格納する辞書を初期化
        assistant_messages: Dict[str, str] = {"role": "assistant", "content": ""}
        # roleも含まれたmessagesについても暗号化
        assistant_messages_encrypted: bytes = cipher_suite.encrypt(
            json.dumps(assistant_messages).encode()
        )
        #  セッションIDにアシスタントのメッセージを追加
        redisCliMessages.rpush(st.session_state["id"], assistant_messages_encrypted)
        #  セッションIDに関連するメッセージの長さを取得
        messages_length = redisCliMessages.llen(st.session_state["id"])
        # logger.info(f"messages_length : {messages_length}")

        #  アシスタントからのメッセージを表示するためのストリームを開始
        with st.chat_message("assistant"):
            #  アシスタントのメッセージを空文字列で初期化
            assistant_msg: str = ""
            #  アシスタントのレスポンスを表示するためのエリアを作成
            assistant_response_area = st.empty()
            #  レスポンスのチャンクを逐次処理
            for chunk in response:
                #  アシスタントのメッセージにチャンクの内容を追加
                assistant_msg += chunk
                # assistant_msgを暗号化
                assistant_msg_encrypted: str = cipher_suite.encrypt(
                    assistant_msg.encode()
                ).decode()

                #  アシスタントのメッセージを更新
                assistant_messages["content"] = assistant_msg
                # roleも含まれたmessagesについても暗号化
                assistant_messages_encrypted: bytes = cipher_suite.encrypt(
                    json.dumps(assistant_messages).encode()
                )

                #  セッションIDにアシスタントのメッセージを更新
                redisCliMessages.lset(
                    st.session_state["id"],
                    messages_length - 1,
                    assistant_messages_encrypted,
                )
                # logger.info(f"redisCliMessages set : {messages_length - 1}")
                #  メッセージIDにアシスタントのレスポンスを保存
                redisCliChatData.hset(
                    messages_id,
                    "response",
                    json.dumps(
                        {
                            "USER_ID": USER_ID,
                            "model": model,  #   使用するAIモデルの名前
                            "timestamp": now,  #   メッセージのタイムスタンプ
                            "messages": assistant_msg_encrypted,  #   トリムされたメッセージのリスト
                            "num_tokens": calc_token_tiktoken(
                                assistant_msg, model=model
                            ),  #   トリムされたメッセージのトークン数
                        }
                    ),
                )
                #  アシスタントのレスポンスを表示エリアに書き込む
                assistant_response_area.write(assistant_msg)
            logger.info(f"Response for chat : {assistant_msg}")
            # logger.debug('Rerun')

# %%
