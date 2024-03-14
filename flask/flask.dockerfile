# Python 3.11をベースイメージとして使用
FROM python:3.11

# 必要なパッケージをインストール
RUN pip install --no-cache-dir gunicorn flask pyjwt cryptography==39.0.1 redis

# 作業ディレクトリを設定
WORKDIR /app

# アプリケーションファイルをコンテナにコピー
#COPY . /app

# ポート番号の指定
EXPOSE 5000

# 本番用の設定ファイルを作成
RUN echo "bind = '0.0.0.0:5000'" > /app/gunicorn.conf.py && \
    echo "workers = 4" >> /app/gunicorn.conf.py && \
    echo "threads = 2" >> /app/gunicorn.conf.py && \
    echo "timeout = 120" >> /app/gunicorn.conf.py && \
    echo "worker_class = 'gevent'" >> /app/gunicorn.conf.py

# Gunicornを使用してFlaskアプリケーションを実行
#CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
# Flaskアプリケーションの実行コマンド
CMD ["python", "app.py"]