# Rangoli Boutique — Technical Specification

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INTERNET                                     │
│                                                                      │
│   Telegram Bot API ──────┐         Buyers (Browser)                  │
│                          │              │                            │
│                          ▼              ▼                            │
│              ┌───────────────────────────────┐                       │
│              │      Flask Web App (gunicorn) │                       │
│              │                               │                       │
│              │  /telegram/webhook  (admin)   │                       │
│              │  /                  (catalog)  │                       │
│              │  /d/<dress_id>     (product)   │                       │
│              └──────┬────────────┬───────────┘                       │
│                     │            │                                    │
│              enqueue jobs   read/write                                │
│                     │            │                                    │
│                     ▼            ▼                                    │
│              ┌──────────┐  ┌───────────┐                             │
│              │  Redis    │  │ PostgreSQL│                             │
│              │  (RQ)     │  │           │                             │
│              └─────┬─────┘  └───────────┘                            │
│                    │                                                  │
│              dequeue                                                  │
│                    │                                                  │
│              ┌─────▼──────────────────┐     ┌─────────────────────┐  │
│              │  RQ Worker Process     │────▶│  Gemini API         │  │
│              │  (AI image generation) │     │  (image generation) │  │
│              └─────────────┬──────────┘     └─────────────────────┘  │
│                            │                                         │
│                     upload images                                     │
│                            │                                         │
│                    ┌───────▼──────────┐                              │
│                    │  S3-Compatible   │                              │
│                    │  Object Storage  │──── CDN (optional)           │
│                    │  (R2/S3/MinIO)   │                              │
│                    └──────────────────┘                              │
│                                                                      │
│   Buyer WhatsApp ◀── wa.me deep link (no backend needed)            │
└─────────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
- **Server-rendered Jinja2 templates** over SPA. Justification: simple catalog pages with no client-side state, better SEO for product pages, one deployment target, can add HTMX for progressive enhancement later. No JS build step needed.
- **RQ (Redis Queue)** over Celery. Justification: ~10 items/day means low throughput; RQ is simpler to configure/debug, fewer dependencies, adequate for this scale.
- **Cloudflare R2** recommended for S3-compatible storage (free egress). AWS S3 or MinIO also work.
- **Single Flask app** serves both public pages and Telegram webhook. No need for separate API service at this scale.

---

## 2. Flask App Structure

```
rangoli-boutique/
├── app/
│   ├── __init__.py              # create_app() factory
│   ├── config.py                # Config classes (Dev/Prod/Test)
│   ├── extensions.py            # db, redis, rq instances
│   ├── models/
│   │   ├── __init__.py          # re-exports all models
│   │   ├── product.py           # Product model
│   │   ├── image.py             # Image model
│   │   ├── variant.py           # VariantOption model
│   │   ├── settings.py          # Settings KV model
│   │   └── audit_log.py         # AuditLog model
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── public/
│   │   │   ├── __init__.py
│   │   │   └── views.py         # Catalog + product pages
│   │   ├── telegram/
│   │   │   ├── __init__.py
│   │   │   ├── webhook.py       # Webhook endpoint
│   │   │   ├── handlers.py      # Message + callback handlers
│   │   │   └── keyboards.py     # Inline keyboard builders
│   │   └── api/
│   │       ├── __init__.py
│   │       └── callbacks.py     # Internal callbacks (worker → bot)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── product_service.py   # CRUD + status transitions
│   │   ├── image_service.py     # Image record management
│   │   ├── ai_service.py        # Gemini API integration
│   │   ├── storage_service.py   # S3 upload/download/signed URLs
│   │   └── telegram_service.py  # Telegram Bot API client
│   ├── workers/
│   │   ├── __init__.py
│   │   └── ai_generation.py     # RQ job: generate AI image
│   ├── templates/
│   │   ├── base.html
│   │   ├── catalog.html
│   │   ├── product.html
│   │   └── partials/
│   │       ├── product_card.html
│   │       ├── filters.html
│   │       └── whatsapp_button.html
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   └── catalog.js       # Minimal: filter toggles, lazy load
│   │   └── img/
│   │       └── logo.svg
│   └── cli.py                   # Flask CLI commands
├── migrations/
│   ├── env.py
│   ├── alembic.ini
│   └── versions/                # Auto-generated migration files
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_telegram.py
│   ├── test_public.py
│   └── test_worker.py
├── scripts/
│   └── set_webhook.py           # One-time: register Telegram webhook
├── Procfile                     # web + worker
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

**Config pattern:**
- `Config` base class reads all values from env vars with sensible defaults
- `DevelopmentConfig` enables debug, uses local Postgres/Redis
- `ProductionConfig` enforces `SECRET_KEY`, sets secure cookies
- `TestingConfig` uses SQLite in-memory, mocks external services
- `FLASK_ENV` / `APP_CONFIG` env var selects which config to load

---

## 3. API Endpoints + Web Routes

### Public Web Routes (blueprint: `public`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Catalog page with filters (category, price, color, size, new arrivals) |
| GET | `/d/<dress_id>` | Product detail page |
| GET | `/health` | Health check (returns 200 + DB/Redis status) |

### Telegram Webhook (blueprint: `telegram`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/telegram/webhook/<token>` | Telegram update webhook (token in URL for obscurity) |

### Internal API (blueprint: `api`) — called by worker

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/internal/ai-complete` | Worker notifies web app that AI gen is done |

**Note:** The internal endpoint is secured with a shared `INTERNAL_API_KEY` header. Alternative: worker writes directly to DB and sends Telegram message via service.

**Chosen approach:** Worker writes to DB directly (shared DB access) and calls `telegram_service.send_preview()` directly. No internal API endpoint needed — simpler.

### Telegram Bot Commands / Interactions

| Trigger | Action |
|---------|--------|
| Photo + caption | Create draft, enqueue AI gen |
| `/setrate <value>` | Update USD FX rate |
| `/setwhatsapp <number>` | Update WhatsApp number |
| `/soldout <dress_id>` | Mark product SOLD_OUT |
| `/hide <dress_id>` | Set status HIDDEN |
| `/unhide <dress_id>` | Set status PUBLISHED |
| `/edit <dress_id>` | Enter edit mode for product |
| `/help` | Show available commands |
| `/stats` | Show product count by status |
| Callback: `approve:<id>` | Publish product with AI image |
| Callback: `regen:<id>` | Regenerate AI image (new version) |
| Callback: `pub_orig:<id>` | Publish with original image only |
| Callback: `discard:<id>` | Delete draft |
| Callback: `edit_meta:<id>` | Prompt for metadata edits |

---

## 4. DB Schema + Migration Plan

### Products

```sql
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    dress_id        VARCHAR(10) UNIQUE NOT NULL,  -- e.g. "D-1042"
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    categories      JSONB DEFAULT '[]',           -- ["saree", "silk"]
    tags            JSONB DEFAULT '[]',           -- ["wedding", "red", "banarasi"]
    price_inr       INTEGER NOT NULL,             -- in paise (1250000 = ₹12,500)
    status          VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
                    -- CHECK (status IN ('DRAFT','PUBLISHED','HIDDEN','SOLD_OUT'))
    telegram_chat_id    BIGINT,                   -- chat where draft was created
    telegram_message_id INTEGER,                  -- preview message ID (for editing)
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_dress_id ON products(dress_id);
CREATE INDEX idx_products_categories ON products USING GIN(categories);
CREATE INDEX idx_products_tags ON products USING GIN(tags);
CREATE INDEX idx_products_created ON products(created_at DESC);
```

**Decision: price in paise (integer)**
Avoids floating point issues. ₹12,500 stored as 1250000. Display logic divides by 100.

### Variant Options

```sql
CREATE TABLE variant_options (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,   -- "Size", "Color", "Fabric"
    value       VARCHAR(100) NOT NULL,  -- "Free Size", "Red with Gold Border"
    sort_order  INTEGER DEFAULT 0,
    UNIQUE(product_id, type, value)
);

CREATE INDEX idx_variants_product ON variant_options(product_id);
```

### Images

```sql
CREATE TABLE images (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    type        VARCHAR(20) NOT NULL,   -- 'ORIGINAL' or 'AI_GENERATED'
    version     INTEGER NOT NULL DEFAULT 1,
    storage_key VARCHAR(512) NOT NULL,  -- S3 key
    url         VARCHAR(1024),          -- public/signed URL
    status      VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                -- 'PENDING', 'READY', 'FAILED'
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_id, type, version)
);

CREATE INDEX idx_images_product ON images(product_id);
```

### Settings

```sql
CREATE TABLE settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed:
INSERT INTO settings (key, value) VALUES
    ('usd_fx_rate', '83.00'),
    ('whatsapp_number', '919876543210');
```

### Audit Log

```sql
CREATE TABLE audit_log (
    id          SERIAL PRIMARY KEY,
    admin_id    BIGINT NOT NULL,        -- Telegram user ID
    action      VARCHAR(50) NOT NULL,   -- 'CREATE_DRAFT', 'PUBLISH', 'SOLD_OUT', etc.
    product_id  INTEGER REFERENCES products(id) ON DELETE SET NULL,
    payload     JSONB,                  -- action-specific data
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_admin ON audit_log(admin_id);
CREATE INDEX idx_audit_product ON audit_log(product_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
```

### Dress ID Sequence

```sql
CREATE SEQUENCE dress_id_seq START WITH 1001;
-- New dress_id = 'D-' || nextval('dress_id_seq')
```

### Migration Plan

1. Use **Flask-Migrate** (Alembic wrapper)
2. Initial migration creates all tables + indexes + sequence
3. Seed migration inserts default settings
4. On deploy: `flask db upgrade` runs before web/worker start
5. Alembic auto-generates diffs; manual review before applying

---

## 5. Queue + Worker

### Technology: RQ (Redis Queue)

**Job payload format:**
```json
{
    "product_id": 42,
    "image_id": 17,
    "original_image_url": "https://storage.example.com/originals/D-1042.jpg",
    "version": 1,
    "attempt": 1
}
```

### Retry / Backoff

- Max 3 attempts
- Backoff: 30s → 120s → 300s (exponential)
- On final failure: mark Image status=FAILED, notify admin via Telegram with "Publish Original Only" option
- RQ's built-in retry mechanism with custom intervals

### Idempotency

- Before generating, check if Image record for (product_id, type=AI_GENERATED, version=N) already has status=READY
- If READY, skip generation (job is a no-op)
- If PENDING, proceed with generation
- Use the Image record ID as the idempotency key
- Worker acquires a Redis lock `ai_gen:{image_id}` (TTL=10min) before starting

### Worker Process

```
Procfile:
  worker: rq worker ai-generation --with-scheduler --url $REDIS_URL
```

Single queue named `ai-generation`. At ~10 items/day, one worker is sufficient.

---

## 6. AI Prompting (Gemini Image Generation)

### Prompt Template

```
Generate a photorealistic studio photograph of an Indian woman wearing
the exact garment shown in the reference image.

CRITICAL REQUIREMENTS — garment fidelity:
- Preserve the EXACT pattern, color, texture, weave, and embroidery
- Preserve the EXACT drape style, pleating, and silhouette
- Do NOT simplify, stylize, or alter the garment design in any way
- The garment must look identical to the reference — as if photographed on a person

Model and setting:
- Indian woman, age 25-35, medium skin tone, pleasant neutral expression
- Standing pose, slightly angled, hands naturally at sides
- Plain off-white/cream studio backdrop
- Soft diffused lighting, no harsh shadows
- Full body shot showing the complete garment

NEGATIVE CONSTRAINTS — strictly avoid:
- No nudity or revealing poses
- No invented logos, text, watermarks, or brand names
- No warped/extra/missing fingers or hands
- No unrealistic body proportions
- No background objects, furniture, or outdoor scenes
- No sunglasses, hats, or accessories not in the original garment
- No color shifts or artistic filters
```

### API Integration (Gemini 2.0 Flash)

```python
# Using google-generativeai SDK
model = genai.GenerativeModel("gemini-2.0-flash-exp")

response = model.generate_content([
    prompt_text,
    original_image_pil,   # PIL Image of the uploaded garment
])
# Extract generated image from response
```

**Tradeoff:** Gemini 2.0 Flash is fast and cost-effective but may need prompt iteration for garment fidelity. Imagen 3 (via Vertex AI) produces higher-quality fashion images but is more expensive. Start with Gemini Flash, upgrade if quality is insufficient.

---

## 7. WhatsApp Deep-Link Encoding

### Format

```
https://wa.me/{PHONE}?text={URL_ENCODED_MESSAGE}
```

### Message Template

```
Hi Poonam Jain, I want Dress {DRESS_ID} from Rangoli Boutique.
Variant: {VARIANT_TEXT}
Ship to: {CITY, COUNTRY}
Link: {PAGE_URL}
```

### Encoding Rules

- Phone number: digits only, with country code, no `+` (e.g., `919876543210`)
- Message body: URL-encoded using `urllib.parse.quote()`
- `{VARIANT_TEXT}` — pre-filled from selected variant on product page; default "Not selected" if none chosen
- `{CITY, COUNTRY}` — left as placeholder text for buyer to fill in
- `{PAGE_URL}` — full canonical URL of the product page

### Example

```
https://wa.me/919876543210?text=Hi%20Poonam%20Jain%2C%20I%20want%20Dress%20D-1042%20from%20Rangoli%20Boutique.%0AVariant%3A%20Red%20with%20Gold%20Border%0AShip%20to%3A%20%5Byour%20city%2C%20country%5D%0ALink%3A%20https%3A%2F%2Frangoliboutique.com%2Fd%2FD-1042
```

### Implementation

```python
from urllib.parse import quote

def build_whatsapp_link(phone, dress_id, variant_text, page_url):
    message = (
        f"Hi Poonam Jain, I want Dress {dress_id} from Rangoli Boutique.\n"
        f"Variant: {variant_text}\n"
        f"Ship to: [your city, country]\n"
        f"Link: {page_url}"
    )
    return f"https://wa.me/{phone}?text={quote(message)}"
```

---

## 8. Security

### Telegram Admin Allowlist

- `TELEGRAM_ADMIN_IDS` env var: comma-separated Telegram user IDs
- Every incoming update is checked: `update.effective_user.id in allowed_ids`
- Reject all others silently (return 200 to Telegram but take no action)

### Telegram Webhook Signature Verification

- Webhook URL includes the bot token as a path segment: `/telegram/webhook/<bot_token>`
- Verify that the token in the URL matches `TELEGRAM_BOT_TOKEN`
- Additionally, set a webhook secret via `setWebhook(secret_token=...)` and verify the `X-Telegram-Bot-Api-Secret-Token` header on every request

### Rate Limiting

- Use `flask-limiter` with Redis backend
- Public routes: 60 req/min per IP
- Telegram webhook: 120 req/min (Telegram may burst)
- Stricter limits on expensive operations (AI regen: 5/hour per admin)

### Safe File Handling

- Validate `content_type` of uploaded photos (must be `image/jpeg` or `image/png`)
- Limit file size (max 10MB, Telegram's own limit is 20MB)
- Sanitize filenames: generate UUID-based keys, never use user-supplied filenames
- Process images with Pillow to strip EXIF data and validate they're actual images (re-encode)
- Store in S3 with `Content-Disposition: inline` and correct `Content-Type`

### Storage Access Control

- **Draft images:** stored with private ACL; accessed via short-lived signed URLs (15min TTL)
- **Published images:** stored with public-read ACL; served via CDN
- On publish: copy image from private to public prefix (or update ACL)
- On discard: delete all associated S3 objects

### Backups

- Postgres: daily automated backups via PaaS (Railway/Render include this)
- S3: versioning enabled on bucket
- Audit log provides point-in-time action history

---

## 9. Deploy Plan

### Procfile

```
web: gunicorn app:create_app() --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile -
worker: rq worker ai-generation --with-scheduler --url $REDIS_URL
release: flask db upgrade
```

The `release` command runs migrations before new code starts serving.

### Environment Variables

```bash
# App
FLASK_ENV=production
SECRET_KEY=                    # random 64-char string
APP_URL=                       # e.g. https://rangoliboutique.com

# Database
DATABASE_URL=                  # postgres://user:pass@host:5432/dbname

# Redis
REDIS_URL=                     # redis://user:pass@host:6379/0

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=       # random string for X-Telegram-Bot-Api-Secret-Token
TELEGRAM_ADMIN_IDS=            # comma-separated: 123456789,987654321

# S3-Compatible Storage
S3_ENDPOINT_URL=               # e.g. https://abc.r2.cloudflarestorage.com
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET_NAME=
S3_PUBLIC_URL=                 # CDN/public base URL for images

# AI
GEMINI_API_KEY=

# Internal
INTERNAL_API_KEY=              # for worker→web communication (optional)
```

### Production Settings

- **Gunicorn:** 2 workers (PaaS-appropriate), 120s timeout (AI webhook callbacks may take time)
- **Database pool:** SQLAlchemy `pool_size=5`, `max_overflow=10`
- **Redis connection pool:** max 10 connections
- **Logging:** structured JSON logs to stdout (PaaS captures these)
- **HTTPS:** enforced by PaaS reverse proxy; set `PREFERRED_URL_SCHEME=https`

### Deploy Steps

1. Push to main branch → PaaS auto-deploys
2. `release` command runs `flask db upgrade`
3. Web process starts with gunicorn
4. Worker process starts with rq
5. One-time: run `python scripts/set_webhook.py` to register Telegram webhook

---

## 10. MVP Timeline (1–2 weeks)

### Week 1: Core

| Day | Task |
|-----|------|
| 1 | Project setup, DB models, migrations, config |
| 2 | Telegram webhook + draft creation flow (photo → product) |
| 3 | S3 integration, image upload/download |
| 4 | RQ worker + AI image generation (Gemini) |
| 5 | Telegram preview card + approve/reject/regen callbacks |
| 5 | Admin commands: /soldout, /hide, /unhide, /setrate |

### Week 2: Frontend + Polish

| Day | Task |
|-----|------|
| 6 | Catalog page with filters |
| 7 | Product detail page + WhatsApp deep link |
| 8 | CSS/responsive design, image optimization |
| 9 | Security hardening (rate limiting, input validation, signed URLs) |
| 10 | Deploy to PaaS, end-to-end testing |

### Testing Checklist

- [ ] Admin sends photo+caption → draft created with correct metadata
- [ ] Dress ID auto-increments correctly (D-1001, D-1002, ...)
- [ ] AI image generated and stored in S3
- [ ] Preview card shows in Telegram with all 5 buttons
- [ ] Approve → product visible on catalog
- [ ] Regenerate → new AI version, new preview card
- [ ] Publish Original Only → product visible with original photo only
- [ ] Discard → product deleted, S3 objects cleaned up
- [ ] /soldout → product shows as sold out on website
- [ ] /hide → product hidden from catalog
- [ ] /unhide → product visible again
- [ ] /setrate → USD prices update across site
- [ ] /setwhatsapp → WhatsApp links update
- [ ] Catalog filters work (category, price, color, size, new arrivals)
- [ ] Product page shows correct prices (INR + approx USD)
- [ ] WhatsApp deep link opens with pre-filled message
- [ ] Variant selection updates WhatsApp message
- [ ] Mobile-responsive catalog and product pages
- [ ] Non-admin Telegram users are rejected silently
- [ ] Webhook signature verification works
- [ ] Rate limiting blocks excessive requests
- [ ] Draft images not accessible without signed URL
- [ ] AI generation retries on failure (up to 3x)
- [ ] AI failure → admin notified with fallback option
- [ ] Concurrent dress ID generation doesn't collide
- [ ] Audit log records all admin actions
- [ ] Health endpoint returns DB/Redis status

---

## 11. Future Enhancements

1. **Instagram auto-post**: On publish, auto-post to Instagram via Graph API with product image + caption
2. **WhatsApp/SMS broadcasts**: Opt-in list; notify subscribers of new arrivals (WhatsApp Business API or Twilio)
3. **Analytics dashboard**: Track page views, WhatsApp click-throughs, conversion by category
4. **Search**: Full-text search with Postgres `tsvector` or Meilisearch
5. **Multi-image upload**: Support multiple original photos per product
6. **Customer wishlist**: Cookie-based or simple email-based wishlist
7. **Inventory alerts**: Telegram notification when items have been published for >N days
8. **Bulk upload**: CSV/spreadsheet import for batch product creation
9. **AI style variations**: Generate multiple outfit styles (casual, formal) from same garment
10. **SEO**: Dynamic sitemap.xml, Open Graph tags, structured data (JSON-LD Product schema)

---

## Pseudocode: Key Flows

### A) Telegram Add → Draft

```python
def handle_photo_message(update):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return  # silent reject

    photo = update.message.photo[-1]  # highest resolution
    caption = update.message.caption or ""

    # Parse caption metadata
    metadata = parse_caption(caption)
    # Expected format:
    #   Title: Red Banarasi Silk Saree
    #   Price: 12500
    #   Category: saree
    #   Tags: silk, banarasi, red, wedding
    #   Variants: Size: Free Size; Color: Red with Gold Border

    # Download photo from Telegram
    file = telegram_api.get_file(photo.file_id)
    image_bytes = telegram_api.download_file(file.file_path)

    # Validate image
    validate_image(image_bytes)  # checks content-type, size, re-encodes

    # Generate dress ID
    dress_id = generate_dress_id()  # "D-1042"

    # Upload original to S3 (private)
    storage_key = f"originals/{dress_id}/v1.jpg"
    storage_service.upload(storage_key, image_bytes, private=True)

    # Create product record
    product = Product(
        dress_id=dress_id,
        title=metadata['title'],
        description=metadata.get('description', ''),
        categories=metadata.get('categories', []),
        tags=metadata.get('tags', []),
        price_inr=metadata['price'] * 100,  # convert to paise
        status='DRAFT',
        telegram_chat_id=update.message.chat_id,
    )
    db.session.add(product)
    db.session.flush()  # get product.id

    # Create variant options
    for variant in metadata.get('variants', []):
        db.session.add(VariantOption(
            product_id=product.id,
            type=variant['type'],
            value=variant['value'],
        ))

    # Create original image record
    original_image = Image(
        product_id=product.id,
        type='ORIGINAL',
        version=1,
        storage_key=storage_key,
        url=storage_service.get_signed_url(storage_key),
        status='READY',
    )
    db.session.add(original_image)
    db.session.flush()

    # Create pending AI image record
    ai_image = Image(
        product_id=product.id,
        type='AI_GENERATED',
        version=1,
        storage_key=f"ai/{dress_id}/v1.jpg",
        status='PENDING',
    )
    db.session.add(ai_image)

    # Audit log
    db.session.add(AuditLog(
        admin_id=user_id,
        action='CREATE_DRAFT',
        product_id=product.id,
        payload={'dress_id': dress_id, 'title': metadata['title']},
    ))

    db.session.commit()

    # Enqueue AI generation job
    queue.enqueue(
        generate_ai_image,
        product_id=product.id,
        image_id=ai_image.id,
        original_url=storage_service.get_signed_url(storage_key),
        version=1,
        job_id=f"ai_gen_{ai_image.id}",
        retry=Retry(max=3, interval=[30, 120, 300]),
    )

    # Reply to admin
    telegram_service.send_message(
        chat_id=update.message.chat_id,
        text=f"✅ Draft created: {dress_id}\n"
             f"Title: {metadata['title']}\n"
             f"Price: ₹{metadata['price']:,}\n"
             f"AI image is being generated..."
    )
```

### B) Worker Job → AI Gen → Store Images

```python
def generate_ai_image(product_id, image_id, original_url, version):
    # Idempotency check
    image = Image.query.get(image_id)
    if image.status == 'READY':
        return  # already done

    # Acquire distributed lock
    lock_key = f"ai_gen:{image_id}"
    lock = redis.lock(lock_key, timeout=600)  # 10 min
    if not lock.acquire(blocking=False):
        return  # another worker is processing

    try:
        # Download original image
        original_bytes = storage_service.download(original_url)
        original_pil = PIL.Image.open(io.BytesIO(original_bytes))

        # Generate AI image via Gemini
        prompt = build_ai_prompt()  # see Section 6
        ai_image_bytes = gemini_service.generate_image(
            prompt=prompt,
            reference_image=original_pil,
        )

        # Validate generated image (ensure it's a valid image)
        ai_pil = PIL.Image.open(io.BytesIO(ai_image_bytes))
        ai_pil.verify()

        # Re-encode as JPEG for consistency
        buffer = io.BytesIO()
        ai_pil = PIL.Image.open(io.BytesIO(ai_image_bytes))
        ai_pil.save(buffer, format='JPEG', quality=90)
        ai_bytes_final = buffer.getvalue()

        # Upload to S3 (private — not published yet)
        storage_key = image.storage_key
        storage_service.upload(storage_key, ai_bytes_final, private=True)

        # Update image record
        image.url = storage_service.get_signed_url(storage_key)
        image.status = 'READY'
        db.session.commit()

        # Send preview to admin via Telegram
        product = Product.query.get(product_id)
        send_preview_card(product)

    except Exception as e:
        image.status = 'FAILED'
        db.session.commit()

        # On final retry failure, notify admin
        if is_final_attempt():
            product = Product.query.get(product_id)
            telegram_service.send_message(
                chat_id=product.telegram_chat_id,
                text=f"⚠️ AI generation failed for {product.dress_id} after 3 attempts.\n"
                     f"Error: {str(e)[:200]}\n"
                     f"You can publish with original image only.",
                reply_markup=fallback_keyboard(product.id),
            )
        raise  # let RQ handle retry
    finally:
        lock.release()


def send_preview_card(product):
    """Send original + AI images with approval keyboard to admin."""
    original = product.images.filter_by(type='ORIGINAL').first()
    ai_img = product.images.filter_by(
        type='AI_GENERATED', status='READY'
    ).order_by(Image.version.desc()).first()

    settings = get_settings()
    usd_rate = float(settings['usd_fx_rate'])
    price_inr = product.price_inr / 100
    price_usd = round(price_inr / usd_rate)

    caption = (
        f"📦 {product.dress_id}: {product.title}\n"
        f"💰 ₹{price_inr:,.0f} (~${price_usd})\n"
        f"📂 {', '.join(product.categories)}\n"
        f"🏷 {', '.join(product.tags)}\n"
        f"🎨 AI v{ai_img.version}\n"
        f"\nOriginal ↑ | AI Generated ↓"
    )

    # Send original photo
    telegram_service.send_photo(
        chat_id=product.telegram_chat_id,
        photo_url=original.url,
        caption=f"📷 Original — {product.dress_id}",
    )

    # Send AI photo with keyboard
    keyboard = build_approval_keyboard(product.id)
    msg = telegram_service.send_photo(
        chat_id=product.telegram_chat_id,
        photo_url=ai_img.url,
        caption=caption,
        reply_markup=keyboard,
    )

    # Store message ID for later editing
    product.telegram_message_id = msg.message_id
    db.session.commit()
```

### C) Approval Transaction

```python
def handle_approve(callback_query, product_id):
    product = Product.query.get(product_id)
    if not product or product.status != 'DRAFT':
        answer_callback(callback_query, "Product not in DRAFT state.")
        return

    ai_img = product.images.filter_by(
        type='AI_GENERATED', status='READY'
    ).order_by(Image.version.desc()).first()

    original = product.images.filter_by(type='ORIGINAL').first()

    # Make images public
    storage_service.make_public(original.storage_key)
    original.url = storage_service.get_public_url(original.storage_key)

    if ai_img:
        storage_service.make_public(ai_img.storage_key)
        ai_img.url = storage_service.get_public_url(ai_img.storage_key)

    # Transition status
    product.status = 'PUBLISHED'
    product.updated_at = datetime.utcnow()

    # Audit log
    db.session.add(AuditLog(
        admin_id=callback_query.from_user.id,
        action='PUBLISH',
        product_id=product.id,
        payload={'ai_version': ai_img.version if ai_img else None},
    ))

    db.session.commit()

    # Update Telegram message
    telegram_service.edit_message_caption(
        chat_id=product.telegram_chat_id,
        message_id=product.telegram_message_id,
        caption=f"✅ PUBLISHED: {product.dress_id}\n{product.title}",
        reply_markup=None,  # remove buttons
    )

    answer_callback(callback_query, f"{product.dress_id} published!")
```

### D) Publish Original Only

```python
def handle_publish_original(callback_query, product_id):
    product = Product.query.get(product_id)
    if not product or product.status != 'DRAFT':
        answer_callback(callback_query, "Product not in DRAFT state.")
        return

    original = product.images.filter_by(type='ORIGINAL').first()
    storage_service.make_public(original.storage_key)
    original.url = storage_service.get_public_url(original.storage_key)

    product.status = 'PUBLISHED'
    product.updated_at = datetime.utcnow()

    db.session.add(AuditLog(
        admin_id=callback_query.from_user.id,
        action='PUBLISH_ORIGINAL_ONLY',
        product_id=product.id,
    ))
    db.session.commit()

    telegram_service.edit_message_caption(
        chat_id=product.telegram_chat_id,
        message_id=product.telegram_message_id,
        caption=f"✅ PUBLISHED (original only): {product.dress_id}",
        reply_markup=None,
    )

    answer_callback(callback_query, f"{product.dress_id} published with original image!")
```

### E) Regenerate Flow

```python
def handle_regenerate(callback_query, product_id):
    product = Product.query.get(product_id)
    if not product or product.status != 'DRAFT':
        answer_callback(callback_query, "Product not in DRAFT state.")
        return

    # Determine next version
    latest_ai = product.images.filter_by(type='AI_GENERATED').order_by(
        Image.version.desc()
    ).first()
    next_version = (latest_ai.version + 1) if latest_ai else 1

    # Create new pending image record
    ai_image = Image(
        product_id=product.id,
        type='AI_GENERATED',
        version=next_version,
        storage_key=f"ai/{product.dress_id}/v{next_version}.jpg",
        status='PENDING',
    )
    db.session.add(ai_image)

    db.session.add(AuditLog(
        admin_id=callback_query.from_user.id,
        action='REGENERATE_AI',
        product_id=product.id,
        payload={'new_version': next_version},
    ))
    db.session.commit()

    # Get original image URL
    original = product.images.filter_by(type='ORIGINAL').first()

    # Enqueue new job
    queue.enqueue(
        generate_ai_image,
        product_id=product.id,
        image_id=ai_image.id,
        original_url=storage_service.get_signed_url(original.storage_key),
        version=next_version,
        job_id=f"ai_gen_{ai_image.id}",
        retry=Retry(max=3, interval=[30, 120, 300]),
    )

    # Update Telegram message
    telegram_service.edit_message_caption(
        chat_id=product.telegram_chat_id,
        message_id=product.telegram_message_id,
        caption=f"🔄 Regenerating AI image v{next_version} for {product.dress_id}...",
        reply_markup=None,
    )

    answer_callback(callback_query, f"Regenerating v{next_version}...")
```
