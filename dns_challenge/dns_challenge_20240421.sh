#!/bin/bash

# DOMAIN_NAMEが正しくセットされているか確認
if [ -z "$DOMAIN_NAME" ] && [ -z "$EMAIL" ]; then
    echo "環境変数DOMAIN_NAME及びEMAILが設定されていません。"
    exit 1
fi



# .pemファイルのパス
PRIVKEY_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem"
FULLCHAIN_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"



# .pemファイルが存在しない場合、Certbotコマンドを実行
if [ ! -f "$PRIVKEY_PATH" ] && [ ! -f "$FULLCHAIN_PATH" ]; then
    echo "DNS01チャレンジを開始します: $DOMAIN_NAME"
    #dnsチャレンジ
    sudo certbot certonly --manual --preferred-challenges dns -d $DOMAIN_NAME --email $EMAIL --agree-tos --no-eff-email
    
else
    echo ".pemファイルは既に存在します。"
fi

