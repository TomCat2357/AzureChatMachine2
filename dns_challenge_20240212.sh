#!/bin/bash

# システムのパッケージリストを更新
sudo apt update
# dnsチャレンジをするためのcerbotをinstall
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
    certbot python3-certbot-apache


# .envファイルのパス
ENV_FILE="./.env"


# .envファイルからDOMAIN_NAMEを読み込む
if [ -f "$ENV_FILE" ]; then
    export $(grep -E '^DOMAIN_NAME=' "$ENV_FILE" | xargs)
fi

# DOMAIN_NAMEが正しくセットされているか確認
if [ -z "$DOMAIN_NAME" ]; then
    echo "DOMAIN_NAMEが.envファイルから読み込めませんでした。"
    exit 1
fi

# .pemファイルのパス
PRIVKEY_PATH="./data/apache_letsencrypt/live/${DOMAIN_NAME}/privkey.pem"
FULLCHAIN_PATH="./data/apache_letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"



# .pemファイルが存在しない場合、Certbotコマンドを実行
if [ ! -f "$PRIVKEY_PATH" ] && [ ! -f "$FULLCHAIN_PATH" ]; then
    echo "DNSチャレンジを開始します: $DOMAIN_NAME"
    sudo certbot certonly --manual --preferred-challenges dns -d $DOMAIN_NAME
else
    echo ".pemファイルは既に存在します。"
fi

