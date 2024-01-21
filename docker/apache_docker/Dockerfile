# 基本イメージとしてUbuntuを使用
FROM ubuntu:latest

# 必要なパッケージのインストール
RUN apt-get update && \
    apt-get install -y apache2 wget vim

# 必要なモジュールの有効化
RUN a2enmod proxy proxy_http proxy_wstunnel rewrite ssl

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
      echo '    Redirect permanent / https://localhost/'; \
      echo '</VirtualHost>'; \
      echo '<IfModule mod_ssl.c>'; \
      echo '<VirtualHost *:443>'; \
      echo '    SSLEngine on'; \
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
RUN echo 'ServerName localhost' >> /etc/apache2/apache2.conf

# 80番ポートと443番ポートを公開
EXPOSE 80 443

# コンテナ起動時にApache2を実行
CMD ["apache2ctl", "-D", "FOREGROUND"]
