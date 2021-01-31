"""Main file to stream tweets in real time.  Might turn this into a flask app at some point."""

from requests_oauthlib import OAuth1Session
import requests
import os
import json
import sys
import logging
import http.client as http_client
import traceback
from bs4 import BeautifulSoup

from urls import Urls
from ratelimiter import RateLimiter

# To set your environment variables in your terminal run the following line:
# export 'BEARER_TOKEN'='<your_bearer_token>'
# same with consumer key and secret
# Or store them in an untracked git file

from secret import *

BAD_WORDS = ["i won", "i entered", "i entered to win a", "i'm entered to win a", "check out and follow", "you can enter here too", "i just entered", "i am in the running", "i'm in the running"]
RETWEET_WORDS = ["retweet", " rt", "rt", "re-tweeted", "re-tweet", "#retweet", "#rt", "#re-tweeted", "#re-tweet"]
LIKE_WORDS = ["favorite", "like", "fav", "fave", "#favorite", "#like", "#fav", "#fave"]
FOLLOW_WORDS = ["followed", "follow", "#followed", "#follow", "flw", "#flw"]

# TODO we can only follow 400 users in a 24 hour period
follow_rate_limiter = RateLimiter(400, 24 * 60 * 60)
# TODO we can only retweet or tweet 300 times per three hours.
# 403 status will be returned if the limit is hit.
retweet_rate_limiter = RateLimiter(300, 3 * 60 * 60)
# TODO we can only like 1000 tweets per 24 hours
like_rate_limiter = RateLimiter(1000, 24 * 60 * 60)
stream_rate_limiter = RateLimiter(50, 15 * 60)
# Note this limiter is for both setting and deleting rules
rule_post_limiter = RateLimiter(450, 15 * 60)
rule_get_limiter = RateLimiter(450, 15 * 60)


# Now that I have the access token and secret I no longer need this function to generate them for me
def o1_auth():
    # oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET)
    # try:
    #     fetch_response = oauth.fetch_request_token("https://api.twitter.com/oauth/request_token")
    # except ValueError:
    #     print("There may an issue with the consumer key or secret.")
    
    # resource_owner_key = fetch_response.get("oauth_token")
    # resource_owner_secret = fetch_response.get("oauth_token_secret")
    # authorization_url = oauth.authorization_url("https://api.twitter.com/oauth/authorize")
    # print(f"Please go here and authorize: {authorization_url}")
    # verifier = input("Paste the PIN here: ")

    # # Get the access token
    # access_token_url = "https://api.twitter.com/oauth/access_token"
    # oauth = OAuth1Session(
    #     CONSUMER_KEY,
    #     client_secret=CONSUMER_SECRET,
    #     resource_owner_key=resource_owner_key,
    #     resource_owner_secret=resource_owner_secret,
    #     verifier=verifier,
    # )
    # oauth_tokens = oauth.fetch_access_token(access_token_url)

    # access_token = oauth_tokens["oauth_token"]
    # access_token_secret = oauth_tokens["oauth_token_secret"]

    # Make the request
    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=ACCESS_TOKEN,
        resource_owner_secret=ACCESS_SECRET,
    )

    return oauth


def o2_auth():
    return os.environ.get("BEARER_TOKEN")


def create_url(endpoint, *args):
    if endpoint == Urls.RULES:
        return "https://api.twitter.com/2/tweets/search/stream/rules"
    elif endpoint == Urls.FOLLOW:
        return "https://api.twitter.com/1.1/friendships/create.json"
    elif endpoint == Urls.LIKE:
        return "https://api.twitter.com/1.1/favorites/create.json"
    elif endpoint == Urls.RETWEET:
        return f"https://api.twitter.com/1.1/statuses/retweet/{args}.json"
    elif endpoint == Urls.STREAM:
        return "https://api.twitter.com/2/tweets/search/stream"


def create_headers(bearer_token):
    return {"Authorization": f"Bearer {bearer_token}"}


def get_rules(url, headers):
    """Get the current stream rules, prints them, and returns them."""
    rule_get_limiter.message_sent()
    return handle_request(requests.get, url, 200, "Cannot get rules", headers=headers)


def delete_all_rules(url, headers, rules):
    """Delete the current stream rules, and prints them.  Returns early if no rules."""
    if rules is None or "data" not in rules:
        return None
    
    ids = list(map(lambda rule: rule["id"], rules["data"]))
    handle_request(requests.post, url, 200, "Cannot delete rules", headers, {"delete": {"ids": ids}})
    rule_post_limiter.message_sent()


def set_rules(url, headers):
    """Set the stream rules."""
    rules = [
        {"value": "giveaway -is:reply -is:retweet lang:en -has:links", "tag": "giveaway"},
    ]
    handle_request(requests.post, url, 201, "Cannot add rules", headers, {"add": rules})
    rule_post_limiter.message_sent()


def get_stream(url, headers, oauth):
    """Get a filtered stream based on the set stream rules."""
    # debug() decomment if something breaks
    try:
        handle_stream_request(oauth, requests.get, url, 200, "Cannot get stream", headers, params={"expansions": ["author_id"],"user.fields": ["name"], "tweet.fields": ["entities,conversation_id,referenced_tweets"]})
        stream_rate_limiter.message_sent()
    except Exception as e:
        print(e)


def debug():
    # You must initialize logging, otherwise you'll not see debug output.
    http_client.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def handle_stream_request(oauth, request_func, url, correct_status_code, err_msg, headers=None, payload=None, params=None):
    """Make stream request to url endpoint, check for errors, and print request headers"""
    response = request_func(url, headers=headers, params=params, json=payload, stream=True)
    # passing headers is required since streams do not have access to the response text
    # cannot use the handle response function because we do not have accces to the response json
    wrong_status_code(correct_status_code, response.status_code, err_msg, response.headers)
    for response_line in response.iter_lines():
        if response_line:
            json_response = json.loads(response_line)
            handle_tweet(json_response, oauth)
            print(json.dumps(json_response, indent=4, sort_keys=True))


def handle_tweet(json_response, oauth):
    """Parse the tweet and perform the appropriate actions to enter giveaway."""
    tweet_text = json_response["data"]["text"].lower()

    # We do not want to parse this tweet
    if any(word in tweet_text for word in BAD_WORDS):
        return

    # TODO we can only follow 400 users in a 24 hour period
    if any(word in tweet_text for word in FOLLOW_WORDS):
        follow_users(oauth, json_response)
    
    tweet_id = json_response["data"]["id"]
    # TODO we can only retweet or tweet 300 times per three hours.
    # 403 status will be returned if the limit is hit.
    if any(word in tweet_text for word in RETWEET_WORDS):
        handle_request(oauth.post, create_url(Urls.RETWEET, tweet_id), 200, "Cannot retweet tweet")
        retweet_rate_limiter.message_sent()

    # TODO we can only like 1000 tweets per 24 hours
    if any(word in tweet_text for word in LIKE_WORDS):
        handle_request(oauth.post, create_url(Urls.LIKE), 200, "Cannot like tweet", params={"id": tweet_id})
        like_rate_limiter.message_sent()


def follow_users(oauth, json_response):
    """Follows the specified user, and the users mentioned in a tweet."""
    user_id = json_response["includes"]["users"][0]["id"]
    # follow the user
    handle_request(oauth.post, create_url(Urls.FOLLOW), 200, "Cannot follow user", params={"user_id": user_id})
    follow_rate_limiter.message_sent()
    # Follow all of the mentioned users
    try:
        for user in json_response["data"]["entities"]["mentions"]:
            handle_request(oauth.post, create_url(Urls.FOLLOW), 200, "Cannot follow user", params={"screen_name": user["username"]})
            follow_rate_limiter.message_sent()
    except KeyError:
        pass


def handle_request(request_func, url, correct_status_code, err_msg, headers=None, payload=None, params=None):
    """Make request to url endpoint, check for errors, print json, then return json data."""
    response = request_func(url, headers=headers, json=payload, params=params)
    return handle_response(correct_status_code, response, err_msg, response.text)


def handle_response(correct_status_code, response, err_msg, text):
    """Handle the responses from the two handle request functions."""
    try:
        wrong_status_code(correct_status_code, response.status_code, err_msg, text)
        print("\n", json.dumps(response.json()), "\n")
        return response.json()
    except Exception as e:
        print(traceback.format_exc())


def wrong_status_code(correct_status_code, status_code, err_msg, text):
    """Raise an error if the response code does not match what we expect."""
    if status_code != correct_status_code:
        raise Exception(f"{err_msg} (HTTP {status_code}): {text}")


# def main():
#     oauth = o1_auth()
#     handle_request(oauth.post, "https://api.twitter.com/1.1/favorites/create.json", 200, "Cannot like tweet", params={"id": '1351309149234225158'}) 


def main():
    """Stream tweets in real time."""
    # Construct headers
    bearer_token = BEARER_TOKEN
    headers = create_headers(bearer_token)

    rules_url = create_url(Urls.RULES)
    # Get previous rules, delete them, and set new rules
    # In the future we can probably just set rules
    rules = get_rules(rules_url, headers)
    delete_all_rules(rules_url, headers, rules)
    set_rules(rules_url, headers)

    # Construct oauth1 session variable
    # Used for performing write actions to our twitter account
    oauth = o1_auth()

    # Get the filtered stream of giveaway tweets
    stream_url = create_url(Urls.STREAM)
    # Rate limiter will pause execution if rate limit is hit
    while True:
        get_stream(stream_url, headers, oauth)


if __name__ == '__main__':
    main()
