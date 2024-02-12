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
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-compose

# Dockerサービスを開始
sudo service docker start

# .env_exampleファイルを.envにコピーする
find . -name ".env_example" | while read filename; do
  target="${filename%_example}" # .envファイルの名前を設定
  # 同一ディレクトリに.envファイルが存在するか確認
  if [[ ! -f "$target" ]]; then
    # .envファイルが存在しない場合、.env_exampleを.envにコピー
    cp "$filename" "$target"
    echo "$filename を $target にコピーしました。"
  else
    # .envファイルが既に存在する場合
    echo "$target は既に存在するため、コピーは行いませんでした。"
  fi
done



# .envファイルが見つかった場合の説明
if find . -name ".env" -exec false {} +; then
    echo ""
else
    echo ".envファイルは、設定の他、秘密鍵やAPIキーなどの環境依存の秘密情報を含むテンプレートです。"
    echo "実際の環境に適した設定と秘密情報を入力してください。"
fi

