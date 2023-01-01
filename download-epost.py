import re
import sys
from os import path, makedirs

import requests
from requests.adapters import HTTPAdapter, Retry

if len(sys.argv) < 2 or len(sys.argv) > 3:
    print(f"Usage: {sys.argv[0]} COOKIE_VALUE [DEST]")
    exit()

cookies = sys.argv[1]

headers = {
    "Cookie": cookies,
}

first_time = True
page_size = 50
offset = 0
num_processed = 0
num_total = 0
downloaded = 0

s = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
s.mount("https://", HTTPAdapter(max_retries=retries))

response = requests.get("https://www.canadapost-postescanada.ca/inbox/en", headers=headers)

sso_tokens = re.findall('"sso-token" content="([a-z0-9\-]*)"', response.text)
potential_sso_tokens = [token for token in sso_tokens if token]
if not potential_sso_tokens:
    print("Failed getting a SSO token. Are you sure you provided your up to date cookies? 🤔")
    exit()

headers["csrf"] = potential_sso_tokens[0]

dir = sys.argv[2] if len(sys.argv) > 2 else "mails"
if not path.exists(dir):
    makedirs(dir, exist_ok=True)

while True:
    url = f"https://www.canadapost-postescanada.ca/inbox/rs/mailitem?folderId=0&sortField=1&order=D&offset={offset}&limit={page_size}"
    response = s.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Request to {url} failed with HTTP {response.status_code} 🔥")
        break

    if "content-length" in response.headers and response.headers["content-length"] == "0":
        print("Failed getting a response. Are you sure you provided your up to date cookies? 🤔")
        exit()

    data = response.json()

    if first_time:
        num_total = data["numTotal"]
        first_time = False

    if len(data["mailitemInfos"]) == 0:
        break

    for mail_item in data["mailitemInfos"]:
        response = s.get(
            f'https://www.epost.ca/service/displayMailStream.a?importSummaryId={mail_item["mailItemID"]}',
            headers=headers,
        )

        name = mail_item["shortDescription"].replace("/", "-").replace(":", " ")
        ext = response.headers["content-type"].split("/")[1]
        file_name = f'{mail_item["mailItemID"]}@{mail_item["billDate"]} {name}.{ext}'
        file_location = path.join(dir, file_name)

        if response.status_code != 200:
            print(f"Downloading {name} failed with HTTP {response.status_code} 🔥")
            continue
        print(f"Downloaded {file_location} 👍")

        with open(file_location, mode="bw") as f:
            f.write(response.content)

        downloaded += 1
        num_processed += 1

    offset += page_size

print(f"Processed {num_processed} of {num_total}! Downloaded {downloaded} new documents. 🎉")
