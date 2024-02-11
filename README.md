# Dockerコンテナ構成に関するReadMe

このリポジトリは、Dockerコンテナを使用して複数のサービスを展開するための設定を提供します。

## Dockerコンテナ構成
- **streamlit**: Streamlitアプリケーションをホストするコンテナ
- **apache**: Apacheサーバーをホストするコンテナ
- **redis_6379**: Redisデータベースをホストするコンテナ

## Dockerファイル
- **docker/streamlit_docker/Dockerfile**: Streamlitコンテナの構成ファイル
- **docker/apache_docker/Dockerfile**: Apacheコンテナの構成ファイル
- **docker/redis_conf/6379/redis.conf**: Redis設定ファイル

## サービス構成
- **streamlit**: Streamlitアプリケーションを実行し、ポート8501を公開
- **apache**: Apacheサーバーを実行し、ポート443と80を公開
- **redis_6379**: Redisデータベースを実行し、ポート6379を公開

## その他
- **key_gen.sh**: SSL証明書とキーを生成するスクリプト。基本的に使わない
- **init_setup_20231223.sh**: 最初にDocker関連のパッケージをインストールするスクリプト。まずはこれを実行

詳細な手順や設定については各ファイルのコメントやスクリプト内の説明を参照してください。
