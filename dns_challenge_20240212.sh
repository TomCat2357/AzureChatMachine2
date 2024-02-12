#!/bin/bash



# .envファイルのパス
ENV_FILE="./.env"


# .envファイルからDOMAIN_NAMEを読み込む
if [ -f "$ENV_FILE" ]; then
    export $(grep -E '^DOMAIN_NAME=' "$ENV_FILE" | xargs)
fi
# .envファイルからEMAILを読み込む
if [ -f "$ENV_FILE" ]; then
    export $(grep -E '^EMAIL=' "$ENV_FILE" | xargs)
fi


# DOMAIN_NAMEが正しくセットされているか確認
if [ -z "$DOMAIN_NAME" ] && [ -z "$EMAIL" ]; then
    echo "DOMAIN_NAME又はEMAILが.envファイルから読み込めませんでした。"
    exit 1
fi



# .pemファイルのパス
PRIVKEY_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem"
FULLCHAIN_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"



# .pemファイルが存在しない場合、Certbotコマンドを実行
if [ ! -f "$PRIVKEY_PATH" ] && [ ! -f "$FULLCHAIN_PATH" ]; then
    echo "DNS01チャレンジを開始します: $DOMAIN_NAME"
    # システムのパッケージリストを更新
    sudo apt update --quiet
    # dnsチャレンジをするためのcerbotをinstall
    sudo DEBIAN_FRONTEND=noninteractive apt install -y --quiet \
        certbot python3-certbot-apache
    # apache2が止まっている場合に備えstart
    sudo service apache2 start
    # 再起動時にapache2を止めること
    sudo systemctl disable apache2
    # apache2を止めることの呼びかけ
    echo "Please stop apache2.service(sudo service apache2 stop)"
    #dnsチャレンジ
    sudo certbot certonly --manual --preferred-challenges dns -d $DOMAIN_NAME --email $EMAIL --agree-tos --no-eff-email
    #apache2を止める
    sudo service apache2 stop

else
    echo ".pemファイルは既に存在します。"
fi

