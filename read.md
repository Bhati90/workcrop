text
# Product Relationship Instance API Documentation

## Get Product Relationships

Retrieve product relationships including crops, varieties, activities, and day ranges.

### Endpoint

`GET /api/product-relationships/{product_id}/`

#### Example

`GET /api/product-relationships/12/`

### Success Response

- **HTTP Status:** `200 OK`
- **Content-Type:** `application/json`
- **Allowed Methods:** `GET, HEAD, OPTIONS`

**Response Example:**
{
"product": {
"id": 12,
"name": "Amil",
"name_marathi": "अमिल",
"product_type": "Bio Stimulant",
"manufacturer": null,
"manufacturer_marathi": null,
"mrp": null,
"price": null,
"size": null,
"size_unit": null
},
"total_uses": 13,
"grouped_by_crop": [
{
"crop": {
"id": 1,
"name": "Grapes",
"name_marathi": "द्राक्ष"
},
"varieties": [
{
"variety": {
"id": 1,
"name": "ARD 36",
"name_marathi": "एआरडी ३६"
},
"activities": [
{
"activity": {
"id": 3,
"name": "Foliar Spray",
"name_marathi": "फवारणी"
},
"day_ranges": [
{
"day_range_product_id": 12,
"day_range": {
"id": 4,
"start_day": 6,
"end_day": 6,
"info": "Use 1600-2000 liters of water per acre.",
"info_marathi": "एकरी १६०० - २००० ली. पाणी वापरणे."
},
"dosage": 10.0,
"dosage_unit": "ml/liter",
"dosage_unit_display": "Milliliter per Liter"
}
]
},
...
]
}
]
}
],
"all_relationships": [
{
"day_range_product_id": 12,
"dosage": 10.0,
"dosage_unit": "ml/liter",
"dosage_unit_display": "Milliliter per Liter",
"day_range": {
"id": 4,
"start_day": 6,
"end_day": 6,
"info": "Use 1600-2000 liters of water per acre.",
"info_marathi": "एकरी १६०० - २००० ली. पाणी वापरणे."
},
"activity": {
"id": 3,
"name": "Foliar Spray",
"name_marathi": "फवारणी"
},
"variety": {
"id": 1,
"name": "ARD 36",
"name_marathi": "एआरडी ३६"
},
"crop": {
"id": 1,
"name": "Grapes",
"name_marathi": "द्राक्ष"
}
},
...
]
}

text

---

## Product Read Only List

### Endpoint

`GET /api/products-readonly/`

#### Example

`GET /api/products-readonly/`

### Success Response

- **HTTP Status:** `200 OK`
- **Allowed Methods:** `GET, HEAD, OPTIONS`
- **Cache-Control:** `public, max-age=300`
- **Content-Type:** `application/json`

**Response Example:**
{
"count": 359,
"next": null,
"previous": null,
"results": [
{
"manufacturer": null,
"id": 391,
"name": "अँट्राकोल",
"name_marathi": "अँट्राकोल",
...
"display_size": "34.00 Gram",
"image": "media/c1f4d795a8dc481e9f1c22488dd04e34_1113907.jpg",
...
},
{
"manufacturer": null,
"id": 390,
"name": "बंबार्डीअर",
"name_marathi": "बंबार्डीअर",
...
},
...
]
}

text

---

## Get Dayrange By Variety And Day

Fetch day range information for a specific crop variety and day.

### Endpoint

`GET /api/get-dayrange-by-day/?variety_id={id}&day={day}`

#### Example

`GET /api/get-dayrange-by-day/?variety_id=1&day=56`

### Success Response

- **HTTP Status:** `200 OK`
- **Allowed Methods:** `GET, OPTIONS`
- **Content-Type:** `application/json`

**Response Example:**
{
"match_type": "exact",
"searched_day": 56,
"variety": {
"id": 1,
"name": "ARD 36",
"name_marathi": "एआरडी ३६",
"crop": {
"id": 1,
"name": "Grapes",
"name_marathi": "द्राक्ष"
}
},
"day_range": {
"id": 41,
"start_day": 56,
"end_day": 56,
"info": "Spray 400 liters of water per acre. Do thinning after GA spray.",
"info_marathi": "एकरी ४०० ली. पाणी फवारणे. / जीए फवारून थिनिंग करणे.",
"activity": {
"id": 20,
"name": "6-8 MM Berry",
"name_marathi": "६ -८ एम एम"
}
},
"products": [
{
"day_range_product_id": 103,
"product_id": 62,
"product_name": "Eclon Max",
"product_name_marathi": "ईक्लोन मॅक्स",
"product_type": "Plant Growth Regulator",
"dosage": 1.0,
"dosage_unit": "liter/acre",
"dosage_unit_display": "Liter per Acre",
"manufacturer": null,
...
},
...
],
"total_products": 4
}

text

---

## Crop List

### Endpoint

`GET /api/crops/`

#### Example

`GET /api/crops/`

### Success Response

- **HTTP Status:** `200 OK`
- **Allowed Methods:** `GET, POST, HEAD, OPTIONS`
- **Content-Type:** `application/json`

**Response Example:**
{
"count": 7,
"next": null,
"previous": null,
"results": [
{
"id": 5,
"name": "Banana",
"name_marathi": "केळी",
"varieties": [
{
"id": 10,
"name": "Banana",
"name_marathi": "केळी",
"crop_name": "Banana",
...
}
],
...
},
...
]
}

text

---

**All endpoints return HTTP 200 OK with structured JSON. Read-only endpoints support GET, HEAD, OPTIONS. All field names are self-explanatory and include both English and Marathi language keys for multilingual support.**