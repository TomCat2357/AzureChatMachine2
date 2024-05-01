from flask import Flask, render_template, request, redirect, jsonify,make_response
from cryptography.fernet import Fernet
import redis,os, jwt



# redisCliUserSetting : user_idで設定を管理する。構造{user_id : {"user_name" : user_name(str), "model" : model_name(str), "custom_instruction" : custom_instruction(str), "use_custom_instruction_flag" : use_custom_instruction_flag(bool)}
redisCliUserSetting = redis.Redis(host="redis", port=6379, db=1)

# JWTでの鍵
JWT_SECRET_KEY = os.environ['JWT_SECRET_KEY']
# メッセージを暗号化する鍵と暗号化インスタンス
ENCRYPT_KEY = os.environ["ENCRYPT_KEY"].encode()
cipher_suite = Fernet(ENCRYPT_KEY)


DOMAIN_NAME = os.environ['DOMAIN_NAME']
app = Flask(__name__)

@app.route('/f_settings')
def settings():
    token = request.args.get('token')
    if token:
        try:
            # JWTの検証
            decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_token["user_id"]
                  
            user_name_encrypted = redisCliUserSetting.hget(user_id, 'user_name')
            user_name = cipher_suite.decrypt(user_name_encrypted).decode('utf-8')
            custom_instruction_encrypted = redisCliUserSetting.hget(user_id, 'custom_instruction')
            custom_instruction = cipher_suite.decrypt(custom_instruction_encrypted).decode('utf-8')
            
            use_custom_instruction_flag = redisCliUserSetting.hget(user_id, 'use_custom_instruction_flag').decode()
            return render_template('settings.html', custom_instruction=custom_instruction, user_name=user_name, user_id=user_id, use_custom_instruction_flag=use_custom_instruction_flag)
        except jwt.ExpiredSignatureError:
            # JWTの有効期限が切れている場合
            return jsonify({"message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            # JWTが無効な場合
            return jsonify({"message": "Invalid token"}), 401
    else:
        # JWTが存在しない場合
        return jsonify({"message": "Token not found"}), 401       

@app.route('/f_save', methods=['POST'])
def save_instruction():
    user_id = request.form['user_id']
    user_name = request.form['user_name']
    custom_instruction = request.form['custom_instruction']
    use_custom_instruction_flag = 'use_custom_instruction' in request.form
    if use_custom_instruction_flag:
        use_custom_instruction_flag = "True"
    else:
        use_custom_instruction_flag = ""
    user_name_encrypted = cipher_suite.encrypt(user_name.encode())
    custom_instruction_encrypted = cipher_suite.encrypt(custom_instruction.encode())
    redisCliUserSetting.hset(user_id, 'user_name', user_name_encrypted)
    redisCliUserSetting.hset(user_id, 'custom_instruction', custom_instruction_encrypted)
    redisCliUserSetting.hset(user_id, 'use_custom_instruction_flag', use_custom_instruction_flag)
    return redirect(f'https://{DOMAIN_NAME}')

@app.route('/f_back', methods=['POST'])
def back():
    return redirect(f'https://{DOMAIN_NAME}')

@app.route('/f_logout_success')
def logout_success():
    # クッキー名 'mod_auth_openidc_session' のクッキーを削除
    response = make_response("""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="3;url=https://{DOMAIN_NAME}">
        <title>Logout</title>
    </head>
    <body>
        <p>Logoutされました。3秒後にリダイレクトします。</p>
        <script>
            setTimeout(function() {
                window.location.href = 'https://{DOMAIN_NAME}';
            }, 3000);
        </script>
    </body>
    </html>
    """)
    response.set_cookie('mod_auth_openidc_session', '', expires=0)
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)