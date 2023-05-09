from datetime import datetime
import os
import openai
from dotenv import load_dotenv
from flask import Flask, request, Response, render_template, url_for, abort
import feedparser
import xml.etree.ElementTree as ET
from flask_frozen import Freezer

from src.logger import setup_logger

logger = setup_logger()

load_dotenv()
openai.api_key = os.environ.get("OPENAI_API_KEY")

app = Flask(__name__)
# app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET")
app.config['FREEZER_DEFAULT_URL_GENERATOR'] = 'flask_frozen.url_generators.default_url_generator_with_html'
freezer = Freezer(app)


@freezer.register_generator
def url_generator():
    build_path = os.path.join(app.root_path, "build")
    yield from generate_url_list(build_path)


def save_static_html(endpoint, year_month, type_by, build_path):
    with app.app_context():
        folder = f'static/{year_month}'
        posts, min_date, max_date = parse_xml_files(folder)

        if type_by == "thread":
            posts = sorted(posts, key=lambda p: p['author'])
        elif type_by == "subject":
            posts = sorted(posts, key=lambda p: p['title'])
        elif type_by == "date":
            posts = sorted(posts, key=lambda p: p['date'])
        elif type_by == "author":
            posts = sorted(posts, key=lambda p: p['author'])
        else:
            raise ValueError(f"Invalid type_by: {type_by}")

        html = render_template('thread.html', posts=posts, year_month=year_month, min_date=min_date, max_date=max_date,
                               type_by=type_by)

        html_folder_path = os.path.join(build_path, endpoint)
        os.makedirs(html_folder_path, exist_ok=True)
        html_file_path = os.path.join(html_folder_path, f"{year_month}.html")

        with open(html_file_path, "w") as f:
            f.write(html)


def generate_url_list(build_path=None):
    url_list = []
    data = get_year_month_data()

    for row in data:
        year_month = row["month"].replace(" ", "_")
        folder = f'static/{year_month}'

        # Check if the folder exists
        if os.path.isdir(os.path.join(app.root_path, folder)):
            # for type_by in ["thread", "subject", "author", "date"]:
            # save_static_html(type_by, year_month, type_by, build_path)

            url_list.append(url_for("thread", year_month=year_month))
            url_list.append(url_for("subject", year_month=year_month))
            url_list.append(url_for("author", year_month=year_month))
            url_list.append(url_for("date", year_month=year_month))

            posts, _, _ = parse_xml_files(folder)
            for post in posts:
                url_list.append(url_for("display_feed", year_month=year_month, filename=post["filename"]))

    return url_list


def parse_xml_files(folder):
    files = os.listdir(os.path.join(app.root_path, folder))
    posts = []
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}

    for file in files:
        if file.endswith('.xml'):
            tree = ET.parse(os.path.join(folder, file))
            root = tree.getroot()

            title = root.find('atom:title', namespace).text
            author = root.find('atom:author/atom:name', namespace).text
            date = root.find('atom:entry/atom:published', namespace).text
            # summary = root.find('atom:entry/atom:summary', namespace).text
            posts.append({'title': title, 'author': author, 'date': date, 'filename': file})

    min_date = min(posts, key=lambda x: x['date'])['date']
    max_date = max(posts, key=lambda x: x['date'])['date']
    min_date_dt = datetime.fromisoformat(min_date)
    max_date_dt = datetime.fromisoformat(max_date)

    return posts, min_date_dt, max_date_dt


def get_year_month_data():
    folders = os.listdir(os.path.join(app.root_path, 'static'))
    data = []
    for f in folders:
        month = f.split("_")[0]
        year = f.split("_")[-1]
        data.append({"month": f"{month} {year}"})
    return data


@app.route("/")
def archive():
    data = get_year_month_data()
    return render_template('index.html', data=data)


def sort_grouping(posts):
    # return sorted(posts,key= lambda x:x['filename'].split("_")[1:])
    combined = {}
    threads = []
    for post in posts:
        if "combined_" in post['filename']:
            ckey = '_'.join(post['filename'].split("_")[1:])
            combined[ckey] = post
        else:
            threads.append(post)

    sorted_threads = sorted(threads, key=lambda x: x['title'].split("_")[1:])
    for i, thread in enumerate(sorted_threads):
        ckey = '_'.join(thread['filename'].split("_")[1:])
        if ckey in combined:
            sorted_threads.insert(i, combined[ckey])
            combined.pop(ckey)

    return sorted_threads


@app.route('/thread/<year_month>.html')
def thread(year_month):
    try:
        folder = f'static/{year_month}'
        posts, min_date, max_date = parse_xml_files(folder)
        posts = sort_grouping(posts)
        return render_template('thread.html', posts=posts, year_month=year_month, min_date=min_date,
                               max_date=max_date, type_by="thread")
    except Exception as e:
        logger.exception(e)
        abort(500)


@app.route('/author/<year_month>.html')
def author(year_month):
    folder = f'static/{year_month}'
    posts, min_date, max_date = parse_xml_files(folder)
    posts = sorted(posts, key=lambda p: p['author'])
    return render_template('thread.html', posts=posts, year_month=year_month, min_date=min_date,
                           max_date=max_date, type_by="author")


@app.route('/subject/<year_month>.html')
def subject(year_month):
    folder = f'static/{year_month}'
    posts, min_date, max_date = parse_xml_files(folder)
    posts = sorted(posts, key=lambda p: p['title'])
    return render_template('thread.html', posts=posts, year_month=year_month, min_date=min_date,
                           max_date=max_date, type_by="subject")


@app.route('/date/<year_month>.html')
def date(year_month):
    folder = f'static/{year_month}'
    posts, min_date, max_date = parse_xml_files(folder)
    posts = sorted(posts, key=lambda p: p['date'])
    return render_template('thread.html', posts=posts, year_month=year_month, min_date=min_date,
                           max_date=max_date, type_by="date")


@app.route('/<year_month>/<filename>.html')
def display_feed(year_month, filename):
    file_url = f"./static/{year_month}/{filename}"
    xml_feed = feedparser.parse(file_url)
    return render_template('feed.html', feed=xml_feed)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        freezer.freeze()
    else:
        os.popen('python scheduler.py > scheduler_logs.txt 2>&1 &')
        try:
            app.run(debug=True)
        except Exception as e:
            logger.exception(e)
