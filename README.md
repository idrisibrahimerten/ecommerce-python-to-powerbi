# 🛒 E-Ticaret Rekabet Analizi Dashboard / E-Commerce Competitive Analysis Dashboard

Bu proje / This project pulls **product data**, **reviews**, **aspects**, and **sponsored links** from a local API `http://test/api/product/` and normalizes it to CSV format.  
---

## 🚀 Özellikler / Features

- Normalize product info (name, brand, category, price, etc.)
- Extracts reviews (text, stars, top pos/neg)
- Extracts **aspects** from customer reviews (e.g., quality, durability)
- Parses **sponsored products** and their links
- Exports outputs to `data/` directory as CSV

---

## 🔧 Kurulum / Setup

```bash
git clone https://github.com/kullanici-adi/product-data-extractor.git
cd product-data-extractor
pip install -r requirements.txt
```

> **Gereksinimler / Requirements**:
> - Python 3.7+
> - `pandas`, `requests`

Manuel yükleme / Manual install:

```bash
pip install pandas requests
```

---

## ⚙️ Kullanım / Usage

```bash
python main.py [PRODUCT_ID_1] [PRODUCT_ID_2] ...
```

---

## 📂 Çıktılar / Output Files

| File | Description |
|------|-------------|
| `products.csv` | Ürün bilgileri / Product info |
| `reviews.csv` | Pozitif/negatif yorumlar / Reviews |
| `aspects.csv` | Aspect'ler & duygu skoru / Review aspects & polarity |
| `sponsored_links.csv` | Sponsorlu ürünler / Sponsored products |

---

## 📊 Power BI Project: Strategic Market Positioning for E‑commerce (TR + EN)

Bu depo, uçtan uca **Power BI + Python** çözümüdür.  
This repo provides an end‑to‑end solution in **Power BI + Python**.

- **Price–Performance** positioning via scatter (bubble) chart  
- **Sentiment & Aspect analysis** with Word Cloud  
- **Top Reviews** (positive/negative split)  
- **Brand Co‑visibility** via sponsored products (network graph)  
- **Metrics modeled in DAX**

---

## 🎯 DAX Measures

```DAX
Avg Rating := AVERAGE ( Products[avg_rating] )
Review Count := SUM ( Products[review_count] )
Price := MIN ( Products[price] )

Price (Category Index) :=
DIVIDE(
  [Price],
  CALCULATE( MEDIAN( Products[price] ), ALLEXCEPT( Products, Products[category] ) )
)

Pos Mentions := CALCULATE( SUM( Aspects[weight] ), Aspects[polarity] = "positive" )
Neg Mentions := CALCULATE( SUM( Aspects[weight] ), Aspects[polarity] = "negative" )
Total Mentions := [Pos Mentions] + [Neg Mentions]

FP Score :=
VAR r = [Avg Rating]
VAR n = [Review Count]
VAR p = [Price (Category Index)]
VAR rr = ( r ^ 1.2 ) * LOG( 1 + n )
RETURN DIVIDE( rr, p )
```

---

## 🖼 Power BI Visuals

- 📍 **Bubble Chart**: Price vs Rating, size=Review count
- 🌩 **Word Cloud**: aspect names (weighted)
- 📝 **Top Reviews**: filtered by pos/neg
- 🕸 **Force‑Directed Graph**: sponsored brand network

---

## ⚠️ Hata Yönetimi / Error Handling

- JSON dışı cevaplarda hata yakalanır / Handles non-JSON responses
- HTTP veya bağlantı hatalarında uyarı verir / Logs request failures
- `_error` içeren response'lar loglanır / Logs failed responses with `_error`

---

## 🗺 Yol Haritası / Roadmap

- Time series for price/rating
- Category breakdown & clustering
- Action suggestions from FP Score + Sentiment
- Gateway + scheduled refresh (Power BI Service)

---

## 📄 Lisans / License

MIT License  
Demo verileri eğitim amaçlıdır / Demo data is for showcase purposes.
