from dotenv import load_dotenv
load_dotenv()
from utils.image_sources.google_images import search_player_images
print(search_player_images("Luciano Darderi", tournament_name="Rome"))
