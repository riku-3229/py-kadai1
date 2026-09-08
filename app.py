from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import json
import os
import random
import ssl

import certifi


# ==================================================
# アプリ全体の設定
# ==================================================

# app.pyが置かれているフォルダの絶対パス
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 天気予報を取得する地域ID
# 400040は福岡県久留米
WEATHER_CITY_ID = "400040"


# お気に入りで使用できるジャンル
FAVORITE_GENRES = [
    "アニメ",
    "漫画",
    "ゲーム",
    "音楽",
    "映画・ドラマ",
    "書籍",
    "人物",
    "その他"
]

# お気に入り一覧で使用できる並び順
FAVORITE_SORTS = {
    "registration": "登録順",
    "title_asc": "タイトル昇順",
    "title_desc": "タイトル降順",
    "genre": "ジャンル順"
}

# Mac環境でHTTPS証明書エラーが発生したため、
# certifiが持つ証明書一覧を使ってAPIへ接続する
SSL_CONTEXT = ssl.create_default_context(
    cafile=certifi.where()
)


class MyHandler(BaseHTTPRequestHandler):

    # ==================================================
    # HTTPレスポンス・HTMLテンプレート
    # ==================================================

    def render_template(self, filename, **kwargs):
        """HTMLを読み込み、{{ 変数名 }}を置換してブラウザへ返す"""

        filepath = os.path.join(
            BASE_DIR,
            "templates",
            filename
        )

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()

        except FileNotFoundError:
            self.send_404()
            return

        # kwargsで渡された値をHTMLのプレースホルダーへ埋め込む
        for key, value in kwargs.items():
            content = content.replace(
                f"{{{{ {key} }}}}",
                str(value)
            )

        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/html; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def send_css_file(self, filename):
        """staticフォルダ内のCSSファイルをブラウザへ返す"""

        filepath = os.path.join(
            BASE_DIR,
            "static",
            filename
        )

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()

        except FileNotFoundError:
            self.send_404()
            return

        # HTMLではなくCSSとして解釈させるため、
        # Content-Typeをtext/cssに設定する
        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/css; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def send_text_response(self, status_code, message):
        """文字列だけのHTTPレスポンスを返す"""

        self.send_response(status_code)
        self.send_header(
            "Content-type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def send_404(self):
        """存在しないページへ404エラーを返す"""

        self.send_text_response(
            404,
            "ページが見つかりません"
        )

    def redirect(self, location):
        """処理後に指定されたURLへ移動させる"""

        # POST後にGETページへ移動させるため303を使用する
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    # ==================================================
    # ファイルパス・JSONファイル操作
    # ==================================================

    def get_data_path(self, filename):
        """dataフォルダ内にあるファイルの絶対パスを返す"""

        return os.path.join(
            BASE_DIR,
            "data",
            filename
        )

    def load_json_file(self, filename):
        """
        JSONファイルを読み込み、Pythonのデータへ変換する。

        読み込みに失敗した場合はNoneを返す。
        空のリストや辞書と、読み込み失敗を区別するために
        Noneを使用している。
        """

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
            print(
                f"{filename}の読み込みに失敗しました: "
                f"{error}"
            )

        return None

    def load_favorites(self):
        """favorites.jsonからお気に入り一覧を読み込む"""

        favorites = self.load_json_file(
            "favorites.json"
        )

        if favorites is None:
            return []

        if not isinstance(favorites, list):
            print(
                "favorites.jsonの最上位データが"
                "リストではありません"
            )
            return []

        return favorites

    def save_favorites(self, favorites):
        """お気に入り一覧をfavorites.jsonへ保存する"""

        favorites_path = self.get_data_path(
            "favorites.json"
        )

        try:
            with open(
                favorites_path,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    favorites,
                    file,
                    ensure_ascii=False,
                    indent=4
                )

            return True

        except OSError as error:
            print(
                "お気に入りの保存に失敗しました: "
                f"{error}"
            )
            return False

    def load_news(self):
        """news.jsonから更新日時とニュース一覧を読み込む"""

        news_data = self.load_json_file(
            "news.json"
        )

        default_news = {
            "updated_at": "更新日時なし",
            "articles": []
        }

        if news_data is None:
            return default_news

        if not isinstance(news_data, dict):
            print(
                "news.jsonの最上位データが"
                "辞書ではありません"
            )
            return default_news

        articles = news_data.get(
            "articles",
            []
        )

        if not isinstance(articles, list):
            print(
                "news.jsonのarticlesが"
                "リストではありません"
            )
            articles = []

        return {
            "updated_at": news_data.get(
                "updated_at",
                "更新日時なし"
            ),
            "articles": articles
        }

    def load_quotes(self):
        """quotes.jsonから名言一覧を読み込む"""

        quotes_data = self.load_json_file(
            "quotes.json"
        )

        if quotes_data is None:
            return []

        if not isinstance(quotes_data, dict):
            print(
                "quotes.jsonの最上位データが"
                "辞書ではありません"
            )
            return []

        quotes = quotes_data.get(
            "quotes",
            []
        )

        if not isinstance(quotes, list):
            print(
                "quotes.jsonのquotesが"
                "リストではありません"
            )
            return []

        return quotes

    # ==================================================
    # 天気API
    # ==================================================

    def load_weather_from_api(self):
        """つくみ島APIから今日の天気を取得する"""

        api_url = (
            "https://weather.tsukumijima.net/"
            f"api/forecast/city/{WEATHER_CITY_ID}"
        )

        request = Request(
            api_url,
            headers={
                "User-Agent": "OshiDashboard/1.0"
            }
        )

        try:
            with urlopen(
                request,
                timeout=10,
                context=SSL_CONTEXT
            ) as response:
                response_bytes = response.read()

            response_text = response_bytes.decode(
                "utf-8"
            )

            weather_data = json.loads(
                response_text
            )

            forecasts = weather_data.get(
                "forecasts",
                []
            )

            if not forecasts:
                raise ValueError(
                    "forecastsに天気予報がありません"
                )

            # forecastsの先頭が今日の予報
            today = forecasts[0]

            temperature = today.get(
                "temperature"
            ) or {}

            # APIではmaxやminがnullになる場合がある。
            # JSONのnullはPythonではNoneなので、or {}で辞書へ置き換える。
            max_data = temperature.get("max") or {}
            min_data = temperature.get("min") or {}

            image_data = today.get("image") or {}

            # celsiusがNoneの場合は「-」を表示する
            max_temperature = (
                max_data.get("celsius")
                or "-"
            )

            min_temperature = (
                min_data.get("celsius")
                or "-"
            )

            print("天気情報の取得に成功しました")

            return {
                "location": weather_data.get(
                    "title",
                    "地域情報なし"
                ),
                "weather": today.get(
                    "telop",
                    "天気情報なし"
                ),
                "max_temperature": max_temperature,
                "min_temperature": min_temperature,
                "image_url": image_data.get(
                    "url",
                    ""
                )
            }

        except HTTPError as error:
            print(
                "天気APIのHTTPエラー:",
                error.code,
                error.reason
            )

        except URLError as error:
            print(
                "天気APIへの接続エラー:",
                error.reason
            )

        except json.JSONDecodeError as error:
            print(
                "天気JSONの解析エラー:",
                error
            )

        except Exception as error:
            print(
                "天気処理でエラーが発生しました:",
                type(error).__name__,
                error
            )

        # 通信失敗時もトップページ自体は表示できるようにする
        return {
            "location": "地域情報なし",
            "weather": "天気情報を取得できません",
            "max_temperature": "-",
            "min_temperature": "-",
            "image_url": ""
        }

    # ==================================================
    # HTMLへ埋め込む内容の生成
    # ==================================================

    def create_favorites_rows(self, favorites, include_actions=False):
        """お気に入り一覧からtable用のHTMLを作る"""

        favorites_rows = ""

        for favorite in favorites:
            favorite_id = favorite.get(
                "id",
                ""
            )

            title = favorite.get(
                "title",
                "タイトルなし"
            )

            genre = favorite.get(
                "genre",
                "未分類"
            )

            tags = favorite.get(
                "tags",
                []
            )

            # tagsがリストの場合は、読点でつないで表示する
            if isinstance(tags, list):
                tags_text = "、".join(tags)
            else:
                tags_text = str(tags)

            # タグが登録されていない場合
            if tags_text == "":
                tags_text = "タグなし"

            actions_cell = ""

            if include_actions:
                actions_cell = f"""
                <td>
                    <a href="/edit?id={favorite_id}">
                        編集
                    </a>

                    <a href="/delete?id={favorite_id}">
                        削除
                    </a>
                </td>
                """

            favorites_rows += f"""
            <tr>
                <td>{title}</td>
                <td>{genre}</td>
                <td>{tags_text}</td>
                {actions_cell}
            </tr>
            """

        if favorites_rows == "":
            column_count = 4 if include_actions else 3

            favorites_rows = f"""
            <tr>
                <td colspan="{column_count}">
                    お気に入りは登録されていません
                </td>
            </tr>
            """

        return favorites_rows

    def create_genre_options(self, selected_genre, include_all=False):
        """ジャンル選択欄に埋め込むoption要素を作る"""

        genre_options = ""

        if include_all:
            selected = ""

            if selected_genre == "":
                selected = " selected"

            genre_options += (
                f'<option value=""{selected}>'
                'すべて</option>'
            )

        for genre in FAVORITE_GENRES:
            selected = ""

            if genre == selected_genre:
                selected = " selected"

            genre_options += (
                f'<option value="{genre}"{selected}>'
                f'{genre}</option>'
            )

        return genre_options

    def create_news_items(self, articles):
        """ニュース一覧からul用のHTMLを作る"""

        news_items = ""

        for article in articles:
            title = article.get(
                "title",
                "タイトルなし"
            )

            category = article.get(
                "category",
                "未分類"
            )

            summary = article.get(
                "summary",
                "概要なし"
            )

            url = article.get(
                "url",
                ""
            )

            # URLがあるニュースだけタイトルをリンクにする
            if url:
                title_html = (
                    f'<a href="{url}" '
                    f'target="_blank">'
                    f'{title}</a>'
                )
            else:
                title_html = title

            news_items += f"""
            <li>
                <p>
                    <strong>{title_html}</strong>
                </p>

                <p>
                    ジャンル：{category}
                </p>

                <p>
                    {summary}
                </p>
            </li>
            """

        if news_items == "":
            news_items = """
            <li>
                ニュースは登録されていません
            </li>
            """

        return news_items

    def select_random_quote(self, quotes):
        """名言一覧からランダムに1件選ぶ"""

        if not quotes:
            return {
                "text": "名言は登録されていません",
                "author": "不明",
                "category": "未分類"
            }

        quote = random.choice(quotes)

        return {
            "text": quote.get(
                "text",
                "名言の本文がありません"
            ),
            "author": quote.get(
                "author",
                "不明"
            ),
            "category": quote.get(
                "category",
                "未分類"
            )
        }

    # ==================================================
    # 各ページの表示
    # ==================================================

    def show_index(self):
        """トップページを表示する"""

        # トップページでは、天気・ニュース・名言だけを取得する。
        # お気に入り全件は専用の /favorites ページで表示する。
        weather_data = self.load_weather_from_api()

        news_data = self.load_news()
        news_items = self.create_news_items(
            news_data["articles"]
        )

        quotes = self.load_quotes()
        selected_quote = self.select_random_quote(
            quotes
        )

        self.render_template(
            "index.html",
            weather_location=weather_data["location"],
            weather=weather_data["weather"],
            max_temperature=weather_data["max_temperature"],
            min_temperature=weather_data["min_temperature"],
            weather_image=weather_data["image_url"],
            news_updated_at=news_data["updated_at"],
            news_items=news_items,
            quote_text=selected_quote["text"],
            quote_author=selected_quote["author"],
            quote_category=selected_quote["category"]
        )

    def show_favorites(self, query_params):
        """お気に入り一覧を絞り込み・並び替えて表示する"""

        selected_genre = query_params.get(
            "genre",
            [""]
        )[0].strip()

        selected_sort = query_params.get(
            "sort",
            ["registration"]
        )[0].strip()

        # 想定外の値がURLに指定された場合は初期値へ戻す
        if selected_genre not in FAVORITE_GENRES:
            selected_genre = ""

        if selected_sort not in FAVORITE_SORTS:
            selected_sort = "registration"

        favorites = self.load_favorites()

        # ジャンルが指定されている場合だけ絞り込む
        if selected_genre:
            favorites = [
                favorite
                for favorite in favorites
                if favorite.get("genre") == selected_genre
            ]

        # 登録順ではJSONの並び順をそのまま使用する
        if selected_sort == "title_asc":
            favorites.sort(
                key=lambda favorite: str(
                    favorite.get("title", "")
                ).casefold()
            )

        elif selected_sort == "title_desc":
            favorites.sort(
                key=lambda favorite: str(
                    favorite.get("title", "")
                ).casefold(),
                reverse=True
            )

        elif selected_sort == "genre":
            favorites.sort(
                key=lambda favorite: (
                    str(
                        favorite.get("genre", "")
                    ).casefold(),
                    str(
                        favorite.get("title", "")
                    ).casefold()
                )
            )

        favorites_rows = self.create_favorites_rows(
            favorites,
            include_actions=True
        )

        genre_options = self.create_genre_options(
            selected_genre,
            include_all=True
        )

        sort_options = ""

        for sort_value, sort_label in FAVORITE_SORTS.items():
            selected = ""

            if sort_value == selected_sort:
                selected = " selected"

            sort_options += (
                f'<option value="{sort_value}"{selected}>'
                f'{sort_label}</option>'
            )

        self.render_template(
            "favorites.html",
            favorites_rows=favorites_rows,
            genre_options=genre_options,
            sort_options=sort_options,
            result_count=len(favorites)
        )

    def show_edit(self, query_params):
        """指定されたお気に入りの編集画面を表示する"""

        id_text = query_params.get(
            "id",
            [""]
        )[0].strip()

        if id_text == "":
            self.send_text_response(
                400,
                "編集するお気に入りが指定されていません"
            )
            return

        try:
            edit_id = int(id_text)

        except ValueError:
            self.send_text_response(
                400,
                "IDは整数で指定してください"
            )
            return

        favorites = self.load_favorites()
        selected_favorite = None

        for favorite in favorites:
            if favorite.get("id") == edit_id:
                selected_favorite = favorite
                break

        if selected_favorite is None:
            self.send_text_response(
                404,
                "編集するお気に入りが見つかりませんでした"
            )
            return

        tags = selected_favorite.get(
            "tags",
            []
        )

        if isinstance(tags, list):
            tags_text = ", ".join(tags)
        else:
            tags_text = str(tags)

        genre_options = self.create_genre_options(
            selected_favorite.get("genre", "")
        )

        self.render_template(
            "edit.html",
            favorite_id=edit_id,
            favorite_title=selected_favorite.get(
                "title",
                ""
            ),
            genre_options=genre_options,
            favorite_tags=tags_text
        )

    def show_delete(self, query_params):
        """指定されたお気に入りの削除確認画面を表示する"""

        id_text = query_params.get(
            "id",
            [""]
        )[0].strip()

        if id_text == "":
            self.send_text_response(
                400,
                "削除するお気に入りが指定されていません"
            )
            return

        try:
            delete_id = int(id_text)

        except ValueError:
            self.send_text_response(
                400,
                "IDは整数で指定してください"
            )
            return

        favorites = self.load_favorites()
        selected_favorite = None

        for favorite in favorites:
            if favorite.get("id") == delete_id:
                selected_favorite = favorite
                break

        if selected_favorite is None:
            self.send_text_response(
                404,
                "削除するお気に入りが見つかりませんでした"
            )
            return

        tags = selected_favorite.get(
            "tags",
            []
        )

        if isinstance(tags, list):
            tags_text = "、".join(tags)
        else:
            tags_text = str(tags)

        if tags_text == "":
            tags_text = "タグなし"

        self.render_template(
            "delete.html",
            favorite_id=delete_id,
            favorite_title=selected_favorite.get(
                "title",
                "タイトルなし"
            ),
            favorite_genre=selected_favorite.get(
                "genre",
                "未分類"
            ),
            favorite_tags=tags_text
        )

    def show_search(self):
        """詳細検索フォームと初期メッセージを表示する"""

        search_results = """
        <tr>
            <td colspan="4">
                検索条件を入力してください
            </td>
        </tr>
        """

        genre_options = self.create_genre_options(
            "",
            include_all=True
        )

        self.render_template(
            "search.html",
            keyword="",
            tag_keyword="",
            genre_options=genre_options,
            partial_selected=" selected",
            exact_selected="",
            search_message="タイトル・ジャンル・タグを組み合わせて検索できます。",
            result_count="-",
            search_results=search_results
        )

    # ==================================================
    # フォームデータの取得・変換
    # ==================================================

    def read_form_data(self):
        """POSTされたフォームデータを辞書へ変換する"""

        content_length = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        request_body = self.rfile.read(
            content_length
        ).decode("utf-8")

        return parse_qs(request_body)

    def parse_tags(self, tags_text):
        """カンマ区切りの文字列を、重複のないタグ一覧へ変換する"""

        tags = []

        for tag in tags_text.split(","):
            cleaned_tag = tag.strip()

            # 空文字と、すでに追加済みのタグは保存しない
            if cleaned_tag and cleaned_tag not in tags:
                tags.append(cleaned_tag)

        return tags

    # ==================================================
    # お気に入りの追加・編集・検索・削除
    # ==================================================

    def reset_favorite_ids(self, favorites):
        """お気に入りのIDを1から順番に振り直す"""

        # 削除後も1、2、3……の連番にするため、
        # リストの並び順に合わせてIDを再設定する
        for new_id, favorite in enumerate(
            favorites,
            start=1
        ):
            favorite["id"] = new_id

        return favorites

    def add_favorite(self):
        """フォームから受け取ったお気に入りを追加する"""

        form_data = self.read_form_data()

        title = form_data.get(
            "title",
            [""]
        )[0].strip()

        genre = form_data.get(
            "genre",
            [""]
        )[0].strip()

        tags_text = form_data.get(
            "tags",
            [""]
        )[0].strip()

        if title == "" or genre == "":
            self.send_text_response(
                400,
                "タイトルとジャンルを入力してください"
            )
            return

        # 入力されたタグをカンマごとに分けてリストへ変換する
        tags = self.parse_tags(tags_text)

        favorites = self.load_favorites()

        # 既存IDに抜けがあっても、新規追加前に連番へ戻す
        self.reset_favorite_ids(favorites)

        new_favorite = {
            "id": len(favorites) + 1,
            "title": title,
            "genre": genre,
            "tags": tags
        }

        favorites.append(new_favorite)

        if self.save_favorites(favorites):
            self.redirect("/favorites")
            return

        self.send_text_response(
            500,
            "お気に入りの保存に失敗しました"
        )

    def edit_favorite(self):
        """指定されたお気に入りの内容を更新する"""

        form_data = self.read_form_data()

        id_text = form_data.get(
            "id",
            [""]
        )[0].strip()

        title = form_data.get(
            "title",
            [""]
        )[0].strip()

        genre = form_data.get(
            "genre",
            [""]
        )[0].strip()

        tags_text = form_data.get(
            "tags",
            [""]
        )[0].strip()

        if id_text == "":
            self.send_text_response(
                400,
                "編集するお気に入りが指定されていません"
            )
            return

        try:
            edit_id = int(id_text)

        except ValueError:
            self.send_text_response(
                400,
                "IDは整数で指定してください"
            )
            return

        if title == "" or genre == "":
            self.send_text_response(
                400,
                "タイトルとジャンルを入力してください"
            )
            return

        if genre not in FAVORITE_GENRES:
            self.send_text_response(
                400,
                "選択されたジャンルが正しくありません"
            )
            return

        tags = self.parse_tags(tags_text)
        favorites = self.load_favorites()
        edited = False

        for favorite in favorites:
            if favorite.get("id") == edit_id:
                # IDとリスト内の位置は変えず、内容だけ更新する
                favorite["title"] = title
                favorite["genre"] = genre
                favorite["tags"] = tags
                edited = True
                break

        if not edited:
            self.send_text_response(
                404,
                "編集するお気に入りが見つかりませんでした"
            )
            return

        if self.save_favorites(favorites):
            self.redirect("/favorites")
            return

        self.send_text_response(
            500,
            "お気に入りの保存に失敗しました"
        )

    def search_favorites(self):
        """タイトル・ジャンル・タグを組み合わせて検索する"""

        form_data = self.read_form_data()

        keyword = form_data.get(
            "keyword",
            [""]
        )[0].strip()

        match_type = form_data.get(
            "match_type",
            ["partial"]
        )[0].strip()

        selected_genre = form_data.get(
            "genre",
            [""]
        )[0].strip()

        tag_keyword = form_data.get(
            "tag_keyword",
            [""]
        )[0].strip()

        if match_type not in ("partial", "exact"):
            match_type = "partial"

        if selected_genre not in FAVORITE_GENRES:
            selected_genre = ""

        # 何も指定されていない検索は実行しない
        if keyword == "" and selected_genre == "" and tag_keyword == "":
            self.send_text_response(
                400,
                "タイトル、ジャンル、タグのいずれかを指定してください"
            )
            return

        favorites = self.load_favorites()
        search_results = []

        for favorite in favorites:
            title = str(
                favorite.get("title", "")
            )

            genre = str(
                favorite.get("genre", "")
            )

            tags = favorite.get(
                "tags",
                []
            )

            if not isinstance(tags, list):
                tags = [str(tags)]

            # タイトルが入力されている場合だけ一致方法を判定する
            title_matches = True

            if keyword:
                if match_type == "exact":
                    title_matches = (
                        keyword.casefold()
                        == title.casefold()
                    )
                else:
                    title_matches = (
                        keyword.casefold()
                        in title.casefold()
                    )

            # ジャンルが選択されている場合だけ完全一致で判定する
            genre_matches = (
                selected_genre == ""
                or genre == selected_genre
            )

            # タグは、登録済みタグのいずれかと完全一致した場合に一致する
            tag_matches = True

            if tag_keyword:
                tag_matches = any(
                    tag_keyword.casefold()
                    == str(tag).casefold()
                    for tag in tags
                )

            if title_matches and genre_matches and tag_matches:
                search_results.append(favorite)

        if search_results:
            search_results_html = self.create_favorites_rows(
                search_results,
                include_actions=True
            )
        else:
            search_results_html = """
            <tr>
                <td colspan="4">
                    条件に一致するお気に入りは
                    見つかりませんでした
                </td>
            </tr>
            """

        genre_options = self.create_genre_options(
            selected_genre,
            include_all=True
        )

        conditions = []

        if keyword:
            match_label = (
                "完全一致"
                if match_type == "exact"
                else "部分一致"
            )
            conditions.append(
                f"タイトル：{keyword}（{match_label}）"
            )

        if selected_genre:
            conditions.append(
                f"ジャンル：{selected_genre}"
            )

        if tag_keyword:
            conditions.append(
                f"タグ：{tag_keyword}（完全一致）"
            )

        search_message = " / ".join(conditions)

        self.render_template(
            "search.html",
            keyword=keyword,
            tag_keyword=tag_keyword,
            genre_options=genre_options,
            partial_selected=(
                " selected"
                if match_type == "partial"
                else ""
            ),
            exact_selected=(
                " selected"
                if match_type == "exact"
                else ""
            ),
            search_message=search_message,
            result_count=len(search_results),
            search_results=search_results_html
        )

    def delete_favorite(self):
        """指定されたIDのお気に入りを削除する"""

        form_data = self.read_form_data()

        id_text = form_data.get(
            "id",
            [""]
        )[0].strip()

        if id_text == "":
            self.send_text_response(
                400,
                "削除するお気に入りが指定されていません"
            )
            return

        try:
            delete_id = int(id_text)

        except ValueError:
            self.send_text_response(
                400,
                "IDは整数で指定してください"
            )
            return

        favorites = self.load_favorites()

        remaining_favorites = []

        for favorite in favorites:
            if favorite.get("id") != delete_id:
                remaining_favorites.append(favorite)

        # 削除前後で件数が同じなら、指定IDは存在しない
        if len(remaining_favorites) == len(favorites):
            self.send_text_response(
                404,
                "指定されたIDは見つかりませんでした"
            )
            return

        self.reset_favorite_ids(
            remaining_favorites
        )

        if self.save_favorites(remaining_favorites):
            self.redirect("/favorites")
            return

        self.send_text_response(
            500,
            "お気に入りの保存に失敗しました"
        )

    # ==================================================
    # ルーティング
    # ==================================================

    def do_GET(self):
        """GETリクエストをURLごとの処理へ振り分ける"""

        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(
            parsed_url.query
        )

        if path == "/":
            self.show_index()

        elif path == "/favorites":
            self.show_favorites(
                query_params
            )

        elif path == "/add":
            self.render_template("add.html")

        elif path == "/edit":
            self.show_edit(
                query_params
            )

        elif path == "/search":
            self.show_search()

        elif path == "/delete":
            self.show_delete(
                query_params
            )

        elif path == "/style.css":
            self.send_css_file("style.css")

        else:
            self.send_404()

    def do_POST(self):
        """POSTリクエストをURLごとの処理へ振り分ける"""

        if self.path == "/add":
            self.add_favorite()

        elif self.path == "/edit":
            self.edit_favorite()

        elif self.path == "/search":
            self.search_favorites()

        elif self.path == "/delete":
            self.delete_favorite()

        else:
            self.send_404()


# ==================================================
# サーバー起動
# ==================================================

def run():
    """ローカルHTTPサーバーを起動する"""

    server_address = (
        "localhost",
        8000
    )

    server = HTTPServer(
        server_address,
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