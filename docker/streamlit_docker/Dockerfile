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
RUN apt install -y python3 python3-dev python3-pip build-essential 
RUN pip install --upgrade pip


# pyenvに必要なパッケージのインストール
RUN apt update && apt install -y git curl build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget llvm libncurses5-dev \
    libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev vim

# pyenv, pyenv-virtualenvのインストール
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv
RUN git clone https://github.com/pyenv/pyenv-virtualenv.git ~/.pyenv/plugins/pyenv-virtualenv
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init --path)"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Pythonバージョンの固定 (バージョンを指定)
RUN /root/.pyenv/bin/pyenv install 3.10.13
RUN /root/.pyenv/bin/pyenv global 3.10.13
RUN /root/.pyenv/bin/pyenv virtualenv 3.10.13 deploy
ENV PATH "/root/.pyenv/versions/3.10.13/envs/deploy/bin:$PATH"


# Streamlitのインストール (ここでStreamlitをインストール)
#RUN /root/.pyenv/versions/3.10.13/envs/deploy/bin/pip install streamlit openai==0.28 tiktoken==0.3.3
RUN pip install streamlit openai==0.28 tiktoken==0.3.3 Flask redis

# Streamlitのポート
EXPOSE 8501

# 環境変数の設定 (APIキー等を外部ファイルから読み込む)
ENV OPENAI_API_KEY=""

# AzureGPTをクローン
RUN cd ~ && git clone https://github.com/tomo2357/AzureGPT.git
