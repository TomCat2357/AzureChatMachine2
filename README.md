# chatroboに関するReadMe

## 概要
OPENAIのAPIを用いて、GPTとチャットするためのプロジェクトです。Dockerを使用してApacheサーバー、Streamlitアプリケーション、およびRedisデータベースを組み合わせて、ウェブアプリケーション基盤を構築します。認証にはAzure Entra IDを使用

## 特徴
- Apache, Streamlit, Redisそれぞれをコンテナ化し、組み合わせたアプリケーション構成
- Azure Entra IDによる認証
- 初期セットアップを簡単にするスクリプト
- certbotによるLet'sEncrypt証明書更新（自動）

![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Apache](https://img.shields.io/badge/Apache-D22128?logo=apache&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Let's Encrypt](https://img.shields.io/badge/Let's%20Encrypt-003A70?logo=letsencrypt&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-007FFF?logo=microsoftazure&logoColor=white)

## 必要な準備
 - **DomainName**: パブリックIPアドレスに紐づいたドメイン名（例 www.hogehoge.com)
 - **AzureEntraID**: 認証用。ユーザー登録及びアプリ登録（TENANT_ID,CLIENT_ID,CLIENT_SECRETをメモする）

## Dockerコンテナ構成
- **apache**: Apacheサーバーをホストするコンテナ
- **streamlit**: Streamlitアプリケーションをホストするコンテナ
- **redis_6379**: Redisデータベースをホストするコンテナ

## Dockerファイル
- **docker/apache_docker/Dockerfile**: Apacheコンテナの構成ファイル
- **docker/streamlit_docker/Dockerfile**: Streamlitコンテナの構成ファイル
- **docker/redis_conf/6379/redis.conf**: Redis設定ファイル

## サービス構成
- **apache**: Apacheサーバーを実行し、HOSTのポート443と80に接続しています。HOSTの443と80ポートへの接続については、streamlitに転送されます。
- **streamlit**: Streamlitアプリケーションを実行し、ポート8501を公開。プロンプト等のデータの保存にはredis_6379コンテナを利用しています。
- **redis_6379**: Redisデータベースを実行し、ポート6379を公開

## その他
- **init_setup_20231223.sh**: 最初にDocker関連のパッケージをインストールするスクリプト。
- **key_gen.sh**: SSL証明書とキーを生成するスクリプト。直接実行する必要はない。init_setup_20231223.shにより実行される。
- **docker/data/redis_6379/dump.rdb**: redisサーバーのスナップショット
- **.env**: API利用頻度の限界や使用モデル及び限界トークン数の設定の他、ドメイン名やAzureEntraIDで取得したTENANT_ID等を設定する。

## セットアップ方法
1. このリポジトリをクローンします
```bash
git clone https://github.com/TomCat2357/chatrobo.git
```

2. リポジトリ内に移動します。
```bash
cd chatrobo
```

3. `init_setup_20231223.sh`を実行して、必要なDocker関連のパッケージをインストールします。また、秘密鍵やlogout時のテナントID、クライアントID等を入力する.envファイルも作成されます。
```bash
sudo bash ./init_setup_20231223.sh
```

4.`.env`を編集して、必要な情報を入力してください。
```bash
sudo vim .env
```

```.envの中身
# これは各種設定、秘密鍵や固有のID等を保存するためのファイルです。
# ".env"にファイル名を変更し、内容も正しいものに書き換えてください。

### 秘密情報
## apache2
#LetsEncryptから連絡するためのあなたのメールアドレス
EMAIL=hogehoge@gmail.com
#あなたのドメイン名
DOMAIN_NAME=www.hogehoge.com
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

### 設定
## streamlit
# GPTへのアクセス回数の上限。PERIOD秒にCOUNT回を超えるアクセスがあれば、ビジーエラーが出る。
LATE_LIMIT={"COUNT":1, "PERIOD":1}
# 使用可能なモデルと限界のトークン数。{"モデル名" : 限界トークン数}となっている。
AVAILABLE_MODELS={"gpt-3.5-turbo":256, "gpt-4":128}
```

5. Dockerコンテナをビルドして実行します。
```bash
sudo docker-compose up --build -d
``` 
