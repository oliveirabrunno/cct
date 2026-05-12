import os
import requests
from dotenv import load_dotenv

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

query = "Luciano Darderi tennis Rome action"
params = {
    "q":       query,
    "tbm":     "isch",
    "api_key": SERPAPI_KEY,
    "num":     5,
}
resp = requests.get("https://serpapi.com/search", params=params)
data = resp.json()
print("Total images:", len(data.get("images_results", [])))
