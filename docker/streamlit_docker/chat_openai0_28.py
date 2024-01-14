# %%
import logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
from copy import copy
from typing import Any, List
import openai, os, redis, time, json, tiktoken, datetime
import streamlit as st
import numpy as np
redis_client_6379 = redis.Redis(host='localhost', port=6379, db=0)
"""
{'user_id' : USER_ID,
 'timestamp' : TIMESTAMP,
 'prompt' : [{'type' : 'user', 'content' : 'Hello World!',
              }],
 'model_type' : 'gpt4 etc.',
 'session_id' : 'SESSION_ID'
 }   
"""

def seconds_since_midnight():
    t = time.localtime()
    return t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec

def get_day_str(day : datetime.date = None, days_delta : int = 0)->str: 
    if not(day):
        day = datetime.date.today()
    if days_delta:
        day += datetime.timedelta(days=days_delta) 
    return day.isoformat().split('T')[0]



def check_rate_limit_exceed(redis_client : redis.Redis, 
                late_limit : int = 1 , 
                late_limit_perios : float= 1.0):
    """
   Checks the rate limit for a given period.

   Args:
       redis_client (redis.Redis): The Redis client object.
       late_limit (int, optional): The maximum number of access data within a certain period. Defaults to 1.
       late_limit_perios (float, optional): The period in seconds. If the number of access data within this period is less than `late_limit`, the data from the previous day is also retrieved. Defaults to 1.0.

   Returns:
       list: The final list of access data.
    """
    # Redisクライアントから現在の日付のデータを取得し、その中のタイムスタンプをaccess_dataリストに格納します。
    access_data = [
       json.loads(data)['timestamp'] for data \
           in redis_client.lrange(get_day_str(), -late_limit, -1)
    ]
    # 現在のアクセスデータの数がlate_limit未満で、かつ現在の時間がlate_limit_periods未満であれば、前日のデータも取得します。
    if len(access_data) < late_limit \
       and seconds_since_midnight() < time.time() - late_limit_perios:
       access_data = [
           json.loads(data)['timestamp'] for data \
               in redis_client.lrange(get_day_str(days_delta=-1), -late_limit, -1)
       ] + access_data
    
    logging.debug(f'past access data num : {len(access_data)}')
    if len(access_data):
        logging.debug(f'{time.time() - access_data[0]}')
    
    if not len(access_data) or access_data[0] < time.time() - late_limit_perios:
        return False
    else:
        return True



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

    # 修正されたメッセージのリストを返す
    return messages


def response_chatgpt(
    prompt: List[dict], model_name: str = "gpt-3.5-turbo"
) -> Any:
    """
    ChatGPTからのレスポンスを取得します。

    引数:
        prompt (List[dict]): 過去のメッセージとユーザーのメッセージが入ったリストユーザーからのメッセージ。
        model_name (str): 使用するChatGPTのモデル名。デフォルトは"gpt-3.5-turbo"。

    戻り値:
        response: ChatGPTからのレスポンス。
    """
    # logging.debug(type(user_msg))
    logging.debug(f"trim_tokens前のprompt: {prompt}")
    logging.debug(f"trim_tokens前のpromptのトークン数: {calc_token_tiktoken(str(prompt))}")
    # logging.debug(f"trim_tokens前のmessages_type: {type(messages)}")

    prompt = trim_tokens(prompt, PAST_INPUT_MAX_TOKENS)
    logging.debug(f"trim_tokens後のprompt: {str(prompt)}")
    logging.debug(f"trim_tokens後のpromptのトークン数: {calc_token_tiktoken(str(prompt))}")
    response = openai.ChatCompletion.create(
        model=model_name, messages=prompt, stream=True
    )
    return response
def calc_token_tiktoken(
    chat: str, encoding_name: str = "", model_name: str = "gpt-3.5-turbo-0301"
) -> int:
    """
    # 引数の説明:
    # chat: トークン数を計算するテキスト。このテキストがAIモデルによってどのようにエンコードされるかを分析します。
    
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



# 利用可能なGPTモデルのリスト
available_models = ["gpt-3.5-turbo", "gpt-4", "gpt-3.5-turbo-0301"]


# APIキーの設定
openai.api_key = os.environ["OPENAI_API_KEY"]

# 過去の最大トークン数
# PAST_INPUT_MAX_TOKENS = 20
PAST_INPUT_MAX_TOKENS = 1024

st.title("StreamlitのChatGPTサンプル")

# 定数定義

USER_ID = "TEST_ID"
#USER_NAME = "user"
#ASSISTANT_NAME = "assistant"
ASSISTANT_WARNING = (
    "注意：私はAIチャットボットで、情報が常に最新または正確であるとは限りません。重要な決定をする前には、他の信頼できる情報源を確認してください。"
)


# %%

# Streamlitのサイドバーに利用可能なGPTモデルを選択するためのドロップダウンメニューを追加
model_choice = st.sidebar.selectbox(
    "GPTモデルを選択してください", available_models, index=0  # デフォルトの選択肢
)
#use_past_data = st.sidebar.checkbox("前の会話も考慮する", value=True)

#if st.sidebar.button('設定画面を開く'):
#flask_url = "http://localhost:5000/settings"
#st.sidebar.markdown(f'<a href="{flask_url}" target="_blank">設定画面を開く</a>', unsafe_allow_html=True)

# アシスタントからの警告を載せる
with st.chat_message("assistant"):
    st.write(ASSISTANT_WARNING)

# Streamlitアプリの開始時にセッション状態を初期化
if not st.session_state.get('session_id'):
    st.session_state.past_data = []
    st.session_state.chat_log = []
    st.session_state.session_id = \
        f'{:0>9}' +  str(np.random.randint(0, 10**9))
    # 過去１週間のチャット一覧を取り寄せる
    for i in range(7):
        day_str = get_day_str(days_delta=i)
        for data in redis_client_6379.lrange(day_str, 0, -1)[::-1]:
            data = json.loads(data)
            if data["user_id"] == USER_ID:
                st.session_state.past_data.append(data)

# 以前のチャットログを表示
for chat in st.session_state.chat_log:
    with st.chat_message(chat["type"]):
        st.write(chat["content"])

# ユーザー入力
user_msg = st.chat_input("ここにメッセージを入力")

# 処理開始
if user_msg:
    # 最新のメッセージを表示
    with st.chat_message('user'):
        st.write(user_msg)

    # セッションにチャットログを追加
    st.session_state.chat_log.append({"type": "user", "content": user_msg})
    error_flag = False
    try:
        # 入力メッセージのトークン数を計算
        user_msg_tokens = calc_token_tiktoken(
            str([{"role": "user", "content": user_msg}])
        )
        logging.debug(f"入力メッセージのトークン数: {user_msg_tokens}")
        if user_msg_tokens > PAST_INPUT_MAX_TOKENS:
            # st.text_area("入力メッセージ", user_msg, height=100)  # メッセージを再表示
            # st.warning("メッセージが長すぎます。短くしてください。" f"({user_msg_tokens}tokens)")
            raise Exception("メッセージが長すぎます。短くしてください。" f"({user_msg_tokens}tokens)")
        if check_rate_limit_exceed(redis_client_6379, 1, 1):
            raise Exception("アクセス数が多いため、接続できません。お待ちください。" f"({user_msg_tokens}tokens)")
        
        response = response_chatgpt(st.session_state.chat_log)
    except Exception as e:
        error_flag = True
        st.warning(e)
        # エラーが出たので今回のユーザーメッセージを減らす
        st.session_state.chat_log = st.session_state.chat_log[:-1]
    if not error_flag:
        st.session_state.chat_log.append({"type": "assistant", "content": ""})
        with st.chat_message("assistant"):
            assistant_msg = ""
            assistant_response_area = st.empty()
            for chunk in response:
                # 回答を逐次表示
                tmp_assistant_msg = chunk["choices"][0]["delta"].get("content", "")
                assistant_msg += tmp_assistant_msg
                st.session_state.chat_log[-1]["content"] = assistant_msg
                assistant_response_area.write(assistant_msg)

        logging.debug(f"チャットログ: {st.session_state.chat_log}")

    # 処理終了

# %%
