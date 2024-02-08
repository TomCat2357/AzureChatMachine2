#!/bin/bash

# システムのパッケージリストを更新
sudo apt update

# 必要なパッケージをインストール
sudo apt -y install \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# DockerのGPGキーを追加
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# DockerのAPTリポジトリを追加
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# リポジトリの更新
sudo apt update

# Docker関連のパッケージをインストール
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Dockerグループを作成し、現在のユーザーを追加(sudoをつけないため)
# セキュリティをアップするために、dockerコマンドにsudoを必須とする
#sudo groupadd docker
#sudo gpasswd -a $USER docker

# Dockerソケットのグループ所有権を変更
#sudo chgrp docker /var/run/docker.sock

# Dockerサービスを開始
sudo service docker start

