from flask import Flask, render_template, request

from .get_parser import get_csv_parser

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    title, parser = get_csv_parser(file)

    if parser:
        df = parser(file)
        last_row = df.iloc[-1]
        df = df.iloc[:-1]

        return render_template("display.html", df=df, last_row=last_row, title=title)
    else:
        error = "Invalid CSV format"
        return render_template("index.html", error=error)
