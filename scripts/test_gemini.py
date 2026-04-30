import urllib.request
import json
import os

key = os.environ['GEMINI_API_KEY']

url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}'
body = json.dumps({'contents': [{'parts': [{'text': 'テストです。「OK」とだけ返してください。'}]}]}).encode()
req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
try:
    res = json.loads(urllib.request.urlopen(req).read())
    print(res['candidates'][0]['content']['parts'][0]['text'])
except urllib.error.HTTPError as e:
    print(f'エラーコード: {e.code}')
    print(f'エラー内容: {e.read().decode()}')

