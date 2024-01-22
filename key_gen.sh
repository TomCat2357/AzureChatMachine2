#!/bin/bash

# 証明書とキーを保存するディレクトリを作成
mkdir -p ./docker/apache_docker/keys

# 秘密鍵を生成
openssl genrsa -out ./docker/apache_docker/keys/my_key.key 2048

# CSR（証明書署名要求）を生成
openssl req -out ./docker/apache_docker/keys/my_cert.csr -key ./docker/apache_docker/keys/my_key.key -new -subj "/C=JP/ST=Tokyo/L=Minato-ku/O=YourOrganization/OU=YourDepartment/CN=localhost"

# 自己署名証明書を生成
# オプショナル：SAN（Subject Alternative Name）を含める場合、san.txtファイルのパスを指定
openssl x509 -req -days 365 -signkey ./docker/apache_docker/keys/my_key.key -in ./docker/apache_docker/keys/my_cert.csr -out ./docker/apache_docker/keys/my_cert.crt -extfile ./docker/apache_docker/apache_san.txt

# CSRファイルを削除
rm ./docker/apache_docker/keys/my_cert.csr

echo "証明書とキーの生成が完了しました。"
