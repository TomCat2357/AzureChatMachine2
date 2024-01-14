#%%

import redis,time,json, random
# %%
redis_client = redis.Redis(host='localhost', port=6379, db=0)
# %%

user = ['Tanaka','Abe', 'Bob']

for i in range(10000):
    send_message = dict(
        user = user[random.randint(0,2)],
        timestamp = int(time.time())+i,
        value = [{'type' : 'user', 'text' : random.randint(0,999)}])

    redis_client.rpush("prompt2",json.dumps(send_message))
# %%
#%%
data = []
for d in redis_client.lrange('prompt2', -1, 0)[::-1]:
    data.append(json.loads(d))
data[:1]
    
# %%
{'user' : 'NAME',
 'timestamp' : 'TIMESTAMP',
 'prompt' : [{'type' : 'user', 'content' : 'Hello World!',
              }],
 'model_type' : 'gpt4 etc.',
 }
# %%
%%timeit
keys = redis_client.keys('*')  # ワイルドカードを使ってすべてのキーを取得

#%%

# キーの一覧を表示
for key in keys:
    print(key.decode('utf-8'))  # バイト列を文字列にデコードして表示

# %%
