"""
Twitter Bot (main) view.

URLs include:
/
"""

import flask

import twitter_bot

@twitter_bot.app.route('/')
def index():
    """Display / route."""

    return flask.render_template("index.html")