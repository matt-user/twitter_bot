"""Main file to stream tweets in real time.  Might turn this into a flask app at some point."""

import requests
import os
import json

# To set your environment variables in your terminal run the following line:
# export 'BEARER_TOKEN'='<your_bearer_token>'
# currently works with no angle brackets, but I read somewhere that you actually need the brackets.

def auth():
    return os.environ.get("BEARER_TOKEN")


def create_url():
    return "https://api.twitter.com/2/tweets/search/stream/rules"


def create_headers(bearer_token):
    headers = {"Authorization": f"Bearer {bearer_token}"}
    return headers


def get_rules(url, headers, bearer_token):
    """Get the current stream rules, prints them, and returns them."""
    response = requests.get(url, headers=headers)
    wrong_status_code(200, response.status_code, "Cannot get rules", response.text)
    print("\nGet rules: \n", json.dumps(response.json()))
    return response.json()


def delete_all_rules(url, headers, bearer_token, rules):
    """Delete the current stream rules, and prints them.  Returns early if no rules."""
    if rules is None or "data" not in rules:
        return None
    
    ids = list(map(lambda rule: rule["id"], rules["data"]))
    payload = {"delete": {"ids": ids}}
    response = requests.post(url, headers=headers, json=payload)
    wrong_status_code(200, response.status_code, "Cannot delete rules", response.text)
    print("\ndelete rules: \n", json.dumps(response.json()))


def set_rules(url, headers, delete, bearer_token):
    """Set the stream rules."""
    rules = [
        {"value": "giveaway", "tag": "giveaway"},
    ]
    payload = {"add": rules}
    response = requests.post(url, headers=headers, json=payload)
    wrong_status_code(201, response.status_code, "Cannot add rules", response.text)
    print("\nset rules: \n", json.dumps(response.json()))


def get_stream(url, headers, set_r, bearer_token):
    """Get a filtered stream based on the set stream rules."""
    response = requests.get(url, headers=headers, stream=True)
    print("\nget stream: \n", response.status_code)
    for response_line in response.iter_lines():
        if response_line:
            json_response = json.loads(response_line)
            print(json.dumps(json_response, indent=4, sort_keys=True))
    # I would like to raise an exception before I iterate over the responses
    # But apparently I can't call a function, something to do with the nature of streams?
    wrong_status_code(200, response.status_code, "Cannot get stream", response.text)


def wrong_status_code(correct_status_code, status_code, err_msg, text):
    """Raise an error if the response code does not match what we expect."""
    if status_code != correct_status_code:
        raise Exception(f"{err_msg} (HTTP {status_code}): {text}")


def main():
    """Stream tweets in real time."""
    bearer_token = auth()
    url = create_url()
    headers = create_headers(bearer_token)
    rules = get_rules(url, headers, bearer_token)
    delete = delete_all_rules(url, headers, bearer_token, rules)
    set_r = set_rules(url, headers, delete, bearer_token)
    get_stream("https://api.twitter.com/2/tweets/search/stream", headers, set_r, bearer_token)
    # timeout = 0
    # while True:
    #     get_stream("https://api.twitter.com/2/tweets/search/stream", headers, set_r, bearer_token)
    #     timeout += 1


if __name__ == '__main__':
    main()