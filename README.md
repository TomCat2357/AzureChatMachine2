# chatroboに関するReadMe

## 概要
OPENAIのAPIを用いて、GPTとチャットするためのプロジェクトです。Dockerを使用してApacheサーバー、Streamlitアプリケーション、およびRedisデータベースを組み合わせて、ウェブアプリケーション基盤を構築します。認証にはAzure Entra IDを使用

## 特徴
- Apache、Streamlit、Redisを各々コンテナ化し、統合したアプリケーション構成。
- Azure Entra IDを利用した認証システム。
- 初期セットアップを手軽に行うためのスクリプト。
- certbotを用いたLet's Encrypt証明書の自動更新機能。

![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Apache](https://img.shields.io/badge/Apache-D22128?logo=apache&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Let's Encrypt](https://img.shields.io/badge/Let's%20Encrypt-003A70?logo=letsencrypt&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-007FFF?logo=microsoftazure&logoColor=white)

## 必要な準備
- **Azureのリソース**: VNet、仮想マシン及びそのパブリックIPアドレス、OPENAI APIのPrivate Endpoint(URLとAPIキー）、Private DNS Server（VNet内の名前解決用） 
- **ドメイン名**: 仮想マシンのパブリックIPアドレスに紐づけられたドメイン名 (例: www.example.com)
- **Azure Entra ID**: 認証用。ユーザー登録およびアプリ登録を行い（ドメイン名が必要）、TENANT_ID、CLIENT_ID、CLIENT_SECRETを控えておく。

## Dockerコンテナ構成
- **apache**: Apacheサーバーを実行するコンテナ。
- **streamlit**: Streamlitアプリケーションを実行するコンテナ。
- **redis**: Redisデータベースを実行するコンテナ。
- 
## Dockerファイル
- **apache_docker/Dockerfile**: Apacheコンテナ用の構成ファイル。
- **streamlit_docker/Dockerfile**: Streamlitコンテナ用の構成ファイル。
- **redis_conf/6379/redis.conf**: Redisコンテナの設定ファイル。

## サービス構成
- **apache**: Apacheサーバーを実行し、80番および443番ポートでリッスンします。これらのポートへのアクセスはStreamlitへ転送されます。
- **streamlit**: Streamlitアプリケーションを実行し、8501番ポートを公開します。プロンプトやその他データの保存にはredisコンテナを使用します。
- **redis**: Redisデータベースを実行し、6379番ポートを公開します。

## その他
- **init_setup_20231223.sh**: Docker関連パッケージの初回インストール用スクリプト。
- **dns_challenge_20240212.sh**: DNS01チャレンジ用。LetsEncryptの証明書がなければ実行
- **.env**: APIの利用制限、使用モデル、トークン数の限界、ドメイン名、Azure Entra IDで取得したTENANT_IDなどを設定するファイル。

## セットアップ方法

1. このリポジトリをクローンします
```bash
git clone https://github.com/TomCat2357/chatrobo.git
```

2. リポジトリ内に移動します。
```bash
cd chatrobo
```

3. `init_setup_20231223.sh`を実行し、必要なDocker関連パッケージをインストールします。また、このステップで`.env`ファイルが作成されます。
```bash
sudo bash ./init_setup_20231223.sh
```

4. `.env`を編集して、必要な情報を入力してください。
```bash
sudo vim .env
```

```
.envの中身
# これは各種設定、秘密鍵や固有のID等を保存するためのファイルです。
# ".env"にファイル名を変更し、内容も正しいものに書き換えてください。

### 秘密情報
## apache2
#LetsEncryptから連絡するためのあなたのメールアドレス 例 hogehoge@hogemail.com
EMAIL=hogehoge@hogemail.com
#あなたのドメイン名 例 hogehoge.com
DOMAIN_NAME=hogehoge.com
#Azureでアプリを登録したテナントID
TENANT_ID=**********************************
#Azureでアプリを登録したクライアントID
CLIENT_ID=**********************************
#Azureでアプリを登録したクライアントのシークレット
CLIENT_SECRET=**********************************
#Apache2で暗号化だかなんだかに使うパスフレーズ
PASSPHRASE=**********************************

## streamlit
# OPENAIのAPIキー
OPENAI_API_KEY=**********************************
# OPENAIのAPIタイプ。例 azure
OPENAI_API_TYPE=""
# OPENAIのAPI_BASE。Private Endpointのurlを指定する。
OPENAI_API_BASE=""
# OPENAIのAPIのVERSION。日付を入れたりしていた。
OPENAI_API_VERSION=""
# DATAをDOWNLOADしたいときにプロンプトに入れるワード
DOWNLOAD_DATA_WORD=""

### 設定
## streamlit
# GPTへのアクセス回数の上限。PERIOD秒にCOUNT回を超えるアクセスがあれば、ビジーエラーが出る。
LATE_LIMIT={"COUNT":1, "PERIOD":1}
# 使用可能なモデルと限界のトークン数。{"モデル名" : 限界トークン数}となっている。
AVAILABLE_MODELS={"gpt-3.5-turbo":256, "gpt-4":128}
# タイトル用のモデルと限界文字数。{"モデル名" : 限界文字数}となっている。
TITLE_MODEL={"gpt-3.5-turbo":512}
# REDISのKEYの寿命。
EXPIRE_TIME=2592000
# API_COST
API_COST={"prompt_gpt-3.5-turbo":0.0002216,"response_gpt-3.5-turbo":0.000296,"prompt_gpt-4":0.004431,"response_gpt-4":0.008861}
```

5. Let's Encryptの証明書と秘密鍵をまだ持っていない場合、DNS01チャレンジを実行します。
```bash
sudo bash dns_challenge_20240212.sh
```

6. Let's Encryptの証明書と秘密鍵がもともとあれば、ホストの以下の場所に保存します。
```bash
/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem # 証明書
/etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem # 秘密鍵
```

7. Dockerコンテナをビルドし、実行します。
```bash
sudo docker-compose up --build -d
```

8. ブラウザでURLを入力し、Chatを開始します。
```bash
https://<DOMAIN_NAME>
```
