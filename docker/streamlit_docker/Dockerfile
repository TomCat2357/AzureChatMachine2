FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
# NTPをインストールして時刻を同期する
#RUN apt-get update && apt-get install -y ntp && ntpdate pool.ntp.org


# Update packages and install essentials
RUN set -x && \
    apt update && \
    apt upgrade -y && \
    apt install -y apt-utils wget sudo curl git  



# Install Apache and necessary modules (必要に応じてmod_wsgi等を追加)
RUN apt install -y apache2 libapache2-mod-wsgi-py3

# Python関連のライブラリー
RUN apt install -y python3.10 python3-pip build-essential
RUN pip install --upgrade pip

# Pythonバージョンの固定 (バージョンを指定)
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
ENV PATH="/usr/local/bin:$PATH"


# Streamlitのインストール (ここでStreamlitをインストール)
# 暗号化ライブラリー
RUN pip install bokeh==2.4.3 cryptography==39.0.1 streamlit==1.31.1 openai==0.28 tiktoken==0.3.3 Flask redis