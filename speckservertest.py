import requests

URL = "http://127.0.0.1:5000/"
param = {"addr1":"ucla", "addr2":"lax", "scale":"distance from sun to earth"}
r = requests.get(URL, params=param)
print(r.text)
