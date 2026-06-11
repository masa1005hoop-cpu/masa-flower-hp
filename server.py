"""
そらflower チャットボット バックエンドサーバー
静的ファイルの配信 + Claude API によるチャット機能
"""

import json
import os
import http.server
import socketserver
from urllib.parse import urlparse
import anthropic

# .env ファイルが存在すれば読み込む
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

# ===== 設定 =====
PORT = 3334
DIR  = os.path.dirname(os.path.abspath(__file__))

# そらflower のシステムプロンプト
SYSTEM_PROMPT = """あなたは「そらflower」のAIアシスタントスタッフです。
以下の自社情報をもとに、お客様のご質問に丁寧にお答えください。

【サービス名】
生花の卸売・小売

【サービス内容】
- 切り花
- 花束
- アレンジメント
- お祝いスタンド
- 鉢物の配達

【料金】
お客様のご希望に合わせて作成いたします。まずはお気軽にご相談ください。

【営業時間・連絡先】
- 営業時間：9:00〜18:00
- 電話：03-0000-0000
- メールアドレス：info@example.jp

【よくある質問と回答】
Q: 注文後、どのくらいで届きますか？
A: 仕入れと運送の状況、配達エリアにもよりますので、ご注文の際にご希望のお日にちをご記入いただければ、確認後ご返答いたします。

Q: 沖縄に配達はできますか？
A: 問題ありません。沖縄への配達も承っております。

【対応方針】
- 丁寧で親しみやすい口調で回答する
- 料金・納期の詳細はお客様のご要望に応じて個別対応するため、電話またはメールへの問い合わせを案内する
- 上記の情報にない質問には正直に伝え、電話（03-0000-0000）またはメール（info@example.jp）への問い合わせを案内する
- 回答は簡潔にまとめる（長すぎない）
- 日本語で回答する"""


class ChatHandler(http.server.SimpleHTTPRequestHandler):
    """静的ファイル配信 + /api/chat エンドポイントを持つハンドラー"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

    def do_OPTIONS(self):
        """CORS プリフライトリクエスト対応"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path == '/api/chat':
            self._handle_chat()
        else:
            self.send_error(404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self.path = '/index.html'
        super().do_GET()

    def _handle_chat(self):
        """Claude API へリクエストを転送してレスポンスを返す"""
        try:
            # リクエストボディを読み込む
            length  = int(self.headers.get('Content-Length', 0))
            body    = json.loads(self.rfile.read(length))
            history = body.get('messages', [])

            # APIキーの確認
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if not api_key:
                self._send_json(500, {'error': 'ANTHROPIC_API_KEY が設定されていません。'})
                return

            # Claude API を呼び出す
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=history,
            )

            reply = response.content[0].text
            self._send_json(200, {'reply': reply})

        except anthropic.AuthenticationError:
            self._send_json(401, {'error': 'APIキーが無効です。ANTHROPIC_API_KEY を確認してください。'})
        except Exception as e:
            self._send_json(500, {'error': f'エラーが発生しました: {str(e)}'})

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self):
        # file:// から開いた場合 Origin が null になるため null も許可する
        origin = self.headers.get('Origin', '*')
        self.send_header('Access-Control-Allow-Origin',  origin if origin else '*')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT), ChatHandler) as server:
        print(f'Server running on http://localhost:{PORT}', flush=True)
        server.serve_forever()
