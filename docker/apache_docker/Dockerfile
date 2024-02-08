# 基本イメージとしてUbuntuを使用
FROM ubuntu:latest

# 必要なパッケージのインストール
RUN apt-get update && \
    apt-get install -y apache2 wget vim libapache2-mod-auth-openidc

# 必要なモジュールの有効化
RUN a2enmod proxy proxy_http proxy_wstunnel rewrite ssl auth_openidc

# ディレクトリの作成と権限変更
# RUN mkdir /etc/ssl/certs/
# 秘密鍵と証明書のコピーと権限設定
COPY ./keys/my_cert.crt /etc/ssl/certs/my_cert.crt
COPY ./keys/my_key.key /etc/ssl/private/my_key.key
RUN chmod 600 /etc/ssl/private/my_key.key && \
    chmod 666 /etc/ssl/certs/my_cert.crt

# Apacheの設定ファイルを作成
RUN rm -f /etc/apache2/sites-available/default-sss.conf
RUN { \
      echo '<VirtualHost *:80>'; \
      echo '    Redirect permanent / https://\${LOCALHOST}'; \
      echo '</VirtualHost>'; \
      echo '<IfModule mod_ssl.c>'; \
      echo '<VirtualHost *:443>'; \
      echo '    SSLEngine on'; \
      echo '    Alias /auth /var/www/html/auth'; \
      echo '    SSLCertificateFile /etc/ssl/certs/my_cert.crt'; \
      echo '    SSLCertificateKeyFile /etc/ssl/private/my_key.key'; \
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

# ServerName localhostの追記
RUN { \
    echo "PassEnv TENANT_ID CLIENT_ID CLIENT_SECRET LOCALHOST PASSPHRASE"; \
    echo "ServerName \${LOCALHOST}"; \
    echo "OIDCProviderMetadataURL https://login.microsoftonline.com/\${TENANT_ID}/v2.0/.well-known/openid-configuration"; \
    echo "OIDCClientID \${CLIENT_ID}"; \
    echo "OIDCClientSecret \${CLIENT_SECRET}"; \
    echo "OIDCRedirectURI https://\${LOCALHOST}/auth"; \
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


# 80番ポートと443番ポートを公開
EXPOSE 80 443

# コンテナ起動時にApache2を実行
CMD ["apache2ctl", "-D", "FOREGROUND"]
