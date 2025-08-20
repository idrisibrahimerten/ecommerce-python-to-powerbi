from typing import Any, Dict, List, Optional
import json, sys
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def dig(d: Dict, path: List[str], default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict): return default
        cur = cur.get(k)
    return cur if cur is not None else default

def coerce_payload(data: Any) -> Dict:
    """GraphQL data.data varsa onu, yoksa doğrudan data'yı payload kabul eder."""
    if isinstance(data, dict):
        return data.get("data") if isinstance(data.get("data"), dict) else data
    if isinstance(data, list):
        for it in data:
            if isinstance(it, dict):
                return it.get("data") if isinstance(it.get("data"), dict) else it
    return {}

def extract_product(payload: Dict) -> Optional[Dict]:
    product = payload.get("product") if isinstance(payload.get("product"), dict) else None
    if product is None:
        item_ctx = dig(payload, ["pageMetadata","pageContext","itemContext"], {})
        if isinstance(item_ctx, dict): 
            product = item_ctx
            price_container = payload.get("product") if isinstance(payload.get("product"), dict) else {}
            product.setdefault("priceInfo", price_container.get("priceInfo", {}))

    if not isinstance(product, dict):
        return None

    pid = product.get("usItemId") or product.get("itemId")
    price_info = product.get("priceInfo") or {}
    current_price = dig(price_info, ["currentPrice","price"])
    unit_price_str = dig(price_info, ["unitPrice","priceString"])

    reviews = payload.get("reviews") if isinstance(payload.get("reviews"), dict) else {}

    return {
        "product": {
            "product_id": pid,
            "name": product.get("name"),
            "brand": product.get("brand"),
            "category": product.get("categoryPath") or dig(product, ["category","categoryPathId"]),
            "price": current_price,
            "unit_price": unit_price_str,
            "avg_rating": reviews.get("averageOverallRating") or reviews.get("averageRating"),
            "review_count": reviews.get("totalReviewCount") or reviews.get("numberOfReviews"),
            "availability_status": product.get("availabilityStatus"),
        },
        "reviews_raw": reviews
    }

def extract_reviews_and_aspects(pid: str, reviews_raw: Dict):
    reviews_rows, aspects_rows = [], []

    top_pos = reviews_raw.get("topPositiveReview") or {}
    top_neg = reviews_raw.get("topNegativeReview") or {}

    def add_top(row, is_pos: bool):
        if not isinstance(row, dict): return
        txt = row.get("text") or row.get("reviewText") or row.get("content")
        rating = row.get("rating")
        rid = row.get("id") or row.get("reviewId")
        if txt:
            reviews_rows.append({
                "review_id": rid,
                "product_id": pid,
                "rating": rating,
                "review_text": txt,
                "sentiment": "positive" if is_pos else "negative",
                "is_top_pos": 1 if is_pos else 0,
                "is_top_neg": 0 if is_pos else 1
            })

    add_top(top_pos, True)
    add_top(top_neg, False)

    aspects = reviews_raw.get("aspects")
    if isinstance(aspects, list):
        for a in aspects:
            if not isinstance(a, dict): continue
            aspects_rows.append({
                "product_id": pid,
                "aspect": a.get("name") or a.get("aspect"),
                "polarity": a.get("polarity") or a.get("sentiment"),
                "weight": a.get("count") or a.get("score") or 1,
                "source": "reviews.aspects"
            })

    return reviews_rows, aspects_rows

def normalize_records(raw_batch: List[Dict[str, Any]]):
    products, reviews, aspects, sponsored = [], [], [], []
    for item in raw_batch:
        pid = item.get("_pid")
        payload = coerce_payload(item.get("_raw"))
        block = extract_product(payload)
        if not block or not block["product"]["product_id"]:
            continue
        p = block["product"]; products.append(p)
        pid = p["product_id"]

        r_rows, a_rows = extract_reviews_and_aspects(pid, block["reviews_raw"] or {})
        reviews.extend(r_rows); aspects.extend(a_rows)

        # Sponsored products
        modules = dig(payload, ["contentLayout","modules"], [])
        if isinstance(modules, list):
            for m in modules:
                ad = dig(m, ["configs","ad","adContent"], {})
                if isinstance(ad, dict) and ad.get("type") == "SPONSORED_PRODUCTS":
                    prods = dig(ad, ["data","products"], [])
                    if isinstance(prods, list):
                        for sp in prods:
                            if isinstance(sp, dict):
                                sponsored.append({
                                    "main_product_id": pid,
                                    "sponsored_product_id": sp.get("usItemId") or sp.get("itemId"),
                                    "sponsored_name": sp.get("name"),
                                    "sponsored_brand": sp.get("brand"),
                                })
    return (
        pd.DataFrame(products).drop_duplicates(subset=["product_id"]),
        pd.DataFrame(reviews),
        pd.DataFrame(aspects),
        pd.DataFrame(sponsored)
    )

BASE_URL = "http://127.0.0.1:3000/api/product/"

def get_product(product_id: str) -> dict:
    """http://127.0.0.1:3000/api/product/{id} uç noktasından tek bir ürünü çeker."""
    if not product_id.isdigit():
        raise ValueError(f"Ürün ID'si sadece rakamlardan oluşmalı: {product_id}")
    url = f"{BASE_URL}{product_id}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {"_error": "non_json", "raw_text": resp.text[:1000]}
    except requests.RequestException as e:
        return {"_error": "request_failed", "message": str(e)}

def get_products_concurrently(product_ids: List[str], max_workers: int = 10) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_id = {ex.submit(get_product, pid): pid for pid in product_ids}
        for fut in as_completed(future_to_id):
            pid = future_to_id[fut]
            try:
                data = fut.result()
                results.append({"_pid": pid, "_raw": data})
                if "_error" in data:
                    print(f"[WARN] {pid} için hata bilgisi döndü: {data.get('_error')}")
                else:
                    print(f"[OK]   {pid} verisi çekildi.")
            except Exception as e:
                print(f"[ERR]  {pid} çekilemedi: {e}")
    return results

def save_outputs(products_df: pd.DataFrame, reviews_df: pd.DataFrame,
                 aspects_df: pd.DataFrame, sponsored_df: pd.DataFrame,
                 out_dir: str = "data"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not products_df.empty:
        products_df.to_csv(out / "products.csv", index=False, encoding="utf-8-sig")
        print(f"[SAVE] products.csv → {len(products_df)} satır")
    else:
        print("[SKIP] products boş")

    if not reviews_df.empty:
        reviews_df.to_csv(out / "reviews.csv", index=False, encoding="utf-8-sig")
        print(f"[SAVE] reviews.csv → {len(reviews_df)} satır")
    else:
        print("[SKIP] reviews boş")

    if not aspects_df.empty:
        aspects_df.to_csv(out / "aspects.csv", index=False, encoding="utf-8-sig")
        print(f"[SAVE] aspects.csv → {len(aspects_df)} satır")
    else:
        print("[SKIP] aspects boş")

    if not sponsored_df.empty:
        sponsored_df.to_csv(out / "sponsored_links.csv", index=False, encoding="utf-8-sig")
        print(f"[SAVE] sponsored_links.csv → {len(sponsored_df)} satır")
    else:
        print("[SKIP] sponsored_links boş")

# ======================
# Main
# ======================

if __name__ == "__main__":
    product_ids = [pid for pid in sys.argv[1:] if pid.strip()] or [
        "6557751127", "1496314895", "5321127916", "6570902110", "16513673629",
        "2438119712", "631193073", "2995864229", "11381374703", "1415071964"
    ]

    print(f"Toplam {len(product_ids)} ID işlenecek: {product_ids}")
    raw_batch = get_products_concurrently(product_ids, max_workers=10)

    if not raw_batch:
        sys.exit(1)

    products_df, reviews_df, aspects_df, sponsored_df = normalize_records(raw_batch)
    save_outputs(products_df, reviews_df, aspects_df, sponsored_df, out_dir="data")
