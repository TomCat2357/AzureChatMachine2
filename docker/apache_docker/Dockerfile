# 基本イメージとしてUbuntuを使用
FROM ubuntu:latest

# 必要なパッケージのインストール
RUN apt update && \
    apt install -y \
    apache2 wget vim libapache2-mod-auth-openidc cron
RUN DEBIAN_FRONTEND=noninteractive apt install -y \
    certbot python3-certbot-apache  \
    && rm -rf /var/lib/apt/lists/*


# 必要なモジュールの有効化
RUN a2enmod proxy proxy_http proxy_wstunnel rewrite ssl auth_openidc

# DOMAIN_NAMEの値を環境変数に設定
ARG DOMAIN_NAME
ENV DOMAIN_NAME=${DOMAIN_NAME}

# Apacheの設定ファイルを作成
RUN rm -f /etc/apache2/sites-available/default-sss.conf
RUN { \
      echo '<VirtualHost *:80>'; \
      echo "    ServerName ${DOMAIN_NAME}"; \
      echo "    Redirect permanent / https://${DOMAIN_NAME}"; \
      echo '</VirtualHost>'; \
      echo '<IfModule mod_ssl.c>'; \
      echo '<VirtualHost *:443>'; \
      echo "    ServerName ${DOMAIN_NAME}"; \
      echo '    SSLEngine on'; \
      echo '    Alias /auth /var/www/html/auth'; \
      echo "    SSLCertificateFile /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"; \
      echo "    SSLCertificateKeyFile /etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem"; \
      echo '    ProxyPreserveHost On'; \
      echo '    RewriteEngine On'; \
      echo '    RewriteCond %{HTTP:Upgrade} websocket [NC]'; \
      echo '    RewriteCond %{HTTP:Connection} upgrade [NC]'; \
      echo '    RewriteRule /(.*) ws://streamlit:8501/$1 [P,L]'; \
      echo '    ProxyPass / http://streamlit:8501/'; \
      echo '    ProxyPassReverse / http://streamlit:8501/'; \
      echo '</VirtualHost>'; \
      echo '</IfModule>'; \
    } > /etc/apache2/sites-available/000-default.conf


# ServerName DOMAIN_NAMEの追記
RUN { \
    echo "PassEnv TENANT_ID CLIENT_ID CLIENT_SECRET DOMAIN_NAME PASSPHRASE"; \
    echo "ServerName \${DOMAIN_NAME}"; \
    echo "OIDCProviderMetadataURL https://login.microsoftonline.com/\${TENANT_ID}/v2.0/.well-known/openid-configuration"; \
    echo "OIDCClientID \${CLIENT_ID}"; \
    echo "OIDCClientSecret \${CLIENT_SECRET}"; \
    echo "OIDCRedirectURI https://\${DOMAIN_NAME}/auth"; \
    echo "OIDCCryptoPassphrase \${PASSPHRASE}"; \
    echo "<Location />"; \
    echo "    AuthType openid-connect"; \
    echo "    Require valid-user"; \
    echo "</Location>"; \
} >> /etc/apache2/apache2.conf

# ログアウト用の設定を追加
RUN { \
    echo "<Location /logout>"; \
    echo "    AuthType openid-connect"; \
    echo "    OIDCUnAuthAction 401"; \
    echo "    RedirectMatch 302 ^/logout$ https://login.microsoftonline.com/\${TENANT_ID}/oauth2/v2.0/logout?post_logout_redirect_uri=https://www.google.com/"; \
    echo "</Location>"; \
} >> /etc/apache2/apache2.conf


# /auth用のディレクトリとHTMLファイルの作成
RUN mkdir -p /var/www/html/auth && \
    echo "<html><body>認証されました</body></html>" > /var/www/html/auth/index.html

# Certbotの自動更新設定
RUN echo "0 12 * * * root certbot renew --quiet --no-self-upgrade --post-hook 'apache2ctl graceful' --dry-run" >> /etc/crontab

# 初期設定用のスクリプトを作成し、実行権限を付与
RUN echo '#!/bin/bash'"\n"\
'# Certbotの設定'"\n"\
'certbot --apache --non-interactive --agree-tos --email ${EMAIL} -d ${DOMAIN_NAME} --redirect --staging'"\n"\
'# cronデーモンの起動'"\n"\
'cron'"\n"\
'# Apacheが既に実行中かどうかを確認'"\n"\
'if ! pidof apache2 > /dev/null; then'"\n"\
'    echo "Starting Apache..."'"\n"\
'    apache2ctl -D FOREGROUND'"\n"\
'else'"\n"\
'    echo "Apache is already running. Keeping it running."'"\n"\
'    tail -f /dev/null'"\n"\
'fi' > /init-setup.sh && chmod +x /init-setup.sh



# コンテナ起動時にinit.shスクリプトを実行
CMD ["/bin/bash", "-c", "/init-setup.sh"]