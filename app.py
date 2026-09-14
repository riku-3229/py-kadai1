from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import json
import mimetypes
import os


# ==================================================
# アプリ全体の設定
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))



class MyHandler(BaseHTTPRequestHandler):

    # ==================================================
    # HTTPレスポンス・テンプレート
    # ==================================================

    def render_template(self, filename, **kwargs):
        filepath = os.path.join(BASE_DIR, "templates", filename)

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
        except FileNotFoundError:
            self.send_404()
            return

        for key, value in kwargs.items():
            content = content.replace(
                f"{{{{ {key} }}}}",
                str(value)
            )

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def send_static_file(self, path):
        filepath = os.path.join(BASE_DIR, path.lstrip("/"))

        if not os.path.isfile(filepath):
            self.send_404()
            return

        content_type, _ = mimetypes.guess_type(filepath)

        if content_type is None:
            content_type = "application/octet-stream"

        try:
            with open(filepath, "rb") as file:
                content = file.read()
        except OSError:
            self.send_404()
            return

        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.end_headers()
        self.wfile.write(content)

    def send_text_response(self, status_code, message):
        self.send_response(status_code)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def send_404(self):
        self.send_text_response(404, "ページが見つかりません")

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    # ==================================================
    # JSON操作
    # ==================================================

    def get_data_path(self, filename):
        return os.path.join(BASE_DIR, "data", filename)

    def load_json_file(self, filename):
        filepath = self.get_data_path(filename)

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()

            if content.strip() == "":
                print(f"{filename}が空です")
                return None

            return json.loads(content)

        except FileNotFoundError:
            print(f"{filename}が見つかりません")
        except json.JSONDecodeError:
            print(f"{filename}のJSON形式が正しくありません")
        except OSError as error:
            print(f"{filename}の読み込みに失敗しました: {error}")

        return None

    def load_wiki_data(self):
        wiki_data = self.load_json_file("wiki.json")

        if wiki_data is None:
            return []

        if not isinstance(wiki_data, list):
            print("wiki.jsonの最上位データがリストではありません")
            return []

        return wiki_data

    def save_wiki_data(self, wiki_data):
        filepath = self.get_data_path("wiki.json")

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(
                    wiki_data,
                    file,
                    ensure_ascii=False,
                    indent=4
                )
            return True

        except OSError as error:
            print(f"wiki.jsonの保存に失敗しました: {error}")
            return False

    # ==================================================
    # HTML生成
    # ==================================================


    def create_wiki_rows(self, wiki_data, include_actions=False):
        rows = ""

        for item in wiki_data:
            wiki_id = item.get("id", "")
            title = item.get("title", "武器名なし")
            weapon_type = item.get("weapon_type", "")
            attack_type = item.get("attack_type", "")
            location = item.get("location", "")
            memo = item.get("memo", "")

            actions_html = ""

            if include_actions:
                actions_html = (
                    f'<td><a href="/delete?id={wiki_id}">削除</a></td>'
                )

            rows += f"""
            <tr>
                <td>{title}</td>
                <td>{weapon_type}</td>
                <td>{attack_type}</td>
                <td>{location}</td>
                <td>{memo}</td>
                {actions_html}
            </tr>
            """

        if rows == "":
            column_count = 6 if include_actions else 5

            rows = f"""
            <tr>
                <td colspan="{column_count}">
                    武器情報は登録されていません
                </td>
            </tr>
            """

        return rows

    def create_news_items(self, articles):
        items = ""

        for article in articles:
            title = article.get("title", "タイトルなし")
            summary = article.get("summary", "")

            items += f"""
            <li>
                <strong>{title}</strong>
                <p>{summary}</p>
            </li>
            """

        if items == "":
            items = "<li>ニュースは登録されていません</li>"

        return items

    # ==================================================
    # 各ページ
    # ==================================================

    def show_index(self):

        news_data = self.load_json_file("news.json")

        if not isinstance(news_data, dict):
            news_data = {}

        articles = news_data.get("articles", [])

        if not isinstance(articles, list):
            articles = []

        self.render_template(
            "index.html",
            news_updated_at=news_data.get("updated_at", "更新日時なし"),
            news_items=self.create_news_items(articles),
        )

    def show_wiki(self):
        wiki_data = self.load_wiki_data()

        self.render_template(
            "favorites.html",
            favorites_rows=self.create_wiki_rows(
                wiki_data,
                include_actions=True
            ),
            result_count=len(wiki_data)
        )

    def show_add(self):
        self.render_template("add.html")

    def show_search(self):
        self.render_template(
            "search.html",
            keyword="",
            search_message="タイトルを入力して検索してください。",
            result_count="-",
            search_results="""
            <tr>
                <td colspan="6">
                    検索条件を入力してください
                </td>
            </tr>
            """
        )

    def show_delete(self, query_params):
        id_text = query_params.get("id", [""])[0].strip()

        try:
            delete_id = int(id_text)
        except ValueError:
            self.send_text_response(400, "IDは整数で指定してください")
            return

        wiki_data = self.load_wiki_data()

        target = None

        for item in wiki_data:
            if item.get("id") == delete_id:
                target = item
                break

        if target is None:
            self.send_text_response(404, "削除する攻略情報が見つかりません")
            return

        self.render_template(
            "delete.html",
            wiki_id=delete_id,
            wiki_title=target.get("title", "タイトルなし"),
            wiki_game=target.get("game", "ゲーム名なし"),
            wiki_genre=target.get("genre", "未分類")
        )

    # ==================================================
    # フォーム処理
    # ==================================================

    def read_form_data(self):
        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        request_body = self.rfile.read(
            content_length
        ).decode("utf-8")

        return parse_qs(request_body)

    def reset_wiki_ids(self, wiki_data):
        for new_id, item in enumerate(wiki_data, start=1):
            item["id"] = new_id

    def add_wiki(self):
        form_data = self.read_form_data()

        title = form_data.get("title", [""])[0].strip()
        weapon_type = form_data.get("weapon_type", [""])[0].strip()
        attack_type = form_data.get("attack_type", [""])[0].strip()
        location = form_data.get("location", [""])[0].strip()
        memo = form_data.get("memo", [""])[0].strip()

        if (
            title == ""
            or weapon_type == ""
            or attack_type == ""
            or location == ""
        ):
            self.send_text_response(
                400,
                "武器名・武器種・攻撃属性・入手場所を入力してください"
            )
            return

        wiki_data = self.load_wiki_data()
        self.reset_wiki_ids(wiki_data)

        wiki_data.append({
            "id": len(wiki_data) + 1,
            "title": title,
            "weapon_type": weapon_type,
            "attack_type": attack_type,
            "location": location,
            "memo": memo
        })

        if self.save_wiki_data(wiki_data):
            self.redirect("/favorites")
            return

        self.send_text_response(
            500,
            "武器情報の保存に失敗しました"
        )

    def search_wiki(self):
        form_data = self.read_form_data()
        keyword = form_data.get("keyword", [""])[0].strip()

        if keyword == "":
            self.send_text_response(
                400,
                "検索するタイトルを入力してください"
            )
            return

        wiki_data = self.load_wiki_data()

        results = [
            item
            for item in wiki_data
            if keyword.casefold()
            in str(item.get("title", "")).casefold()
        ]

        self.render_template(
            "search.html",
            keyword=keyword,
            search_message=f"タイトル「{keyword}」の検索結果",
            result_count=len(results),
            search_results=self.create_wiki_rows(
                results,
                include_actions=True
            )
        )

    def delete_wiki(self):
        form_data = self.read_form_data()
        id_text = form_data.get("id", [""])[0].strip()

        try:
            delete_id = int(id_text)
        except ValueError:
            self.send_text_response(
                400,
                "IDは整数で指定してください"
            )
            return

        wiki_data = self.load_wiki_data()

        remaining = [
            item
            for item in wiki_data
            if item.get("id") != delete_id
        ]

        if len(remaining) == len(wiki_data):
            self.send_text_response(
                404,
                "指定された攻略情報が見つかりません"
            )
            return

        self.reset_wiki_ids(remaining)

        if self.save_wiki_data(remaining):
            self.redirect("/favorites")
            return

        self.send_text_response(
            500,
            "攻略情報の削除に失敗しました"
        )

    # ==================================================
    # ルーティング
    # ==================================================

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if path == "/":
            self.show_index()

        elif path == "/favorites":
            self.show_wiki()

        elif path == "/add":
            self.show_add()

        elif path == "/search":
            self.show_search()

        elif path == "/delete":
            self.show_delete(query_params)

        elif path.startswith("/static/"):
            self.send_static_file(path)

        elif path == "/style.css":
            self.send_static_file("/static/style.css")

        else:
            self.send_404()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/add":
            self.add_wiki()

        elif path == "/search":
            self.search_wiki()

        elif path == "/delete":
            self.delete_wiki()

        else:
            self.send_404()


# ==================================================
# サーバー起動
# ==================================================

def run():
    server = HTTPServer(
        ("localhost", 8000),
        MyHandler
    )

    print("サーバーを起動しました")
    print("http://localhost:8000/")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nサーバーを停止します")

    finally:
        server.server_close()


if __name__ == "__main__":
    run()
