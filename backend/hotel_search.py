#hotel_search.py
import os
import sys
from typing import List
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer, util

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Load .env
load_dotenv()

# Config
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
INDEX_NAME = "hotels-index"

model = SentenceTransformer("all-MiniLM-L6-v2")
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

def get_embedding(text: str) -> List[float]:
    return model.encode([text])[0].tolist()

def fuzzy_match(user_amenities: List[str], hotel_amenities: List[str], threshold: float = 0.7) -> bool:
    if not user_amenities:
        return True
    if not hotel_amenities:
        return False

    user_embeds = model.encode(user_amenities, convert_to_tensor=True)
    hotel_embeds = model.encode(hotel_amenities, convert_to_tensor=True)
    cosine_scores = util.cos_sim(user_embeds, hotel_embeds)

    for i in range(len(user_amenities)):
        if cosine_scores[i].max().item() < threshold:
            return False
    return True

def query_hotels(city: str, rating: float = None, max_price: float = None, amenities: List[str] = None, top_k: int = 100):
    query_str = f"hotels in {city}"
    if rating:
        query_str += f" with rating >= {rating}"
    if max_price:
        query_str += f" with nightly price under {max_price}"
    if amenities:
        query_str += f" with amenities: {', '.join(amenities)}"

    vector = get_embedding(query_str)
    response = index.query(vector=vector, top_k=top_k, include_metadata=True)

    def filter_result(metadata):
        try:
            if metadata["city"].lower() != city.lower():
                return False

            if rating:
                score_str = metadata.get("rating", "0").split("/")[0]
                if float(score_str) < rating:
                    return False

            if max_price:
                price_str = metadata.get("price", {}).get("nightly", "").replace("$", "").replace(",", "")
                if price_str and float(price_str) > max_price:
                    return False

            if amenities:
                hotel_amenities = metadata.get("key_amenities", [])
                # Exact-match filtering
                for a in amenities:
                    if a.lower() in ["pet-friendly", "kid-friendly", "child-friendly", "airport shuttle", "free breakfast"]:
                        if not any(a.lower() == h.lower() for h in hotel_amenities):
                            return False
                    else:
                        if not fuzzy_match([a], hotel_amenities):
                            return False

            return True
        except Exception:
            return False

    return [match["metadata"] for match in response["matches"] if filter_result(match["metadata"])]
