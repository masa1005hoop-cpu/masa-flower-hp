"""
Vercel サーバーレス関数 — /api/chat
Claude API を呼び出してチャットの返答を返す
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import traceback
import anthropic

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


class handler(BaseHTTPRequestHandler):
    """Vercel Python サーバーレス関数ハンドラー"""

    def do_OPTIONS(self):
        """CORS プリフライトリクエスト対応"""
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        """チャットリクエストを処理して Claude API の返答を返す"""
        try:
            # ===== リクエストボディを読み込む =====
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            print(f"[INFO] Received request body ({length} bytes)", flush=True)

            data     = json.loads(body)
            messages = data.get('messages', [])
            print(f"[INFO] Message count: {len(messages)}", flush=True)

            # ===== APIキーの確認 =====
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if not api_key:
                err = 'ANTHROPIC_API_KEY が環境変数に設定されていません。Vercel の Environment Variables を確認してください。'
                print(f"[ERROR] {err}", file=sys.stderr, flush=True)
                self._json(500, {'error': err})
                return

            print(f"[INFO] API key found (length={len(api_key)})", flush=True)

            # ===== Claude API 呼び出し =====
            client   = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            reply = response.content[0].text
            print(f"[INFO] Got reply ({len(reply)} chars)", flush=True)
            self._json(200, {'reply': reply})

        except json.JSONDecodeError as e:
            msg = f'リクエストの JSON が不正です: {e}'
            print(f"[ERROR] JSONDecodeError: {e}", file=sys.stderr, flush=True)
            self._json(400, {'error': msg})

        except anthropic.AuthenticationError as e:
            msg = f'APIキーが無効です。Vercel の Environment Variables を確認してください。詳細: {e}'
            print(f"[ERROR] AuthenticationError: {e}", file=sys.stderr, flush=True)
            self._json(401, {'error': msg})

        except anthropic.RateLimitError as e:
            msg = f'API のレート制限に達しました。しばらくしてから再試行してください。詳細: {e}'
            print(f"[ERROR] RateLimitError: {e}", file=sys.stderr, flush=True)
            self._json(429, {'error': msg})

        except anthropic.APIError as e:
            msg = f'Anthropic API エラー: {e}'
            print(f"[ERROR] APIError: {e}", file=sys.stderr, flush=True)
            self._json(502, {'error': msg})

        except Exception as e:
            tb = traceback.format_exc()
            msg = f'予期しないエラーが発生しました: {e}'
            print(f"[ERROR] Unexpected error:\n{tb}", file=sys.stderr, flush=True)
            self._json(500, {'error': msg})

    # ===== ヘルパー =====
    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        origin = self.headers.get('Origin', '*')
        self.send_header('Access-Control-Allow-Origin',  origin or '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, fmt, *args):
        print(f"[HTTP] {fmt % args}", flush=True)
