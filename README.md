# Iyzico Django Template

Django tabanlı, **Iyzico Checkout Form** ödeme akışı eklenmiş bir template. Auth, RBAC ve audit altyapısı mevcut; odak ödeme entegrasyonunda. **Docker** ile çalışacak şekilde yapılandırılmıştır.

---

## Docker ile Çalıştırma

### Gereksinimler

- Docker ve Docker Compose
- Iyzico sandbox hesabı ([sandbox-merchant.iyzipay.com](https://sandbox-merchant.iyzipay.com))

### Hızlı başlangıç

1. **Ortam dosyasını oluşturun:**

   ```bash
   cp .env.example .env
   ```

2. **`.env` içinde Iyzico sandbox anahtarlarınızı girin:**

   - `IYZICO_API_KEY`
   - `IYZICO_SECRET_KEY`
   - `IYZICO_BASE_URL=sandbox-api.iyzipay.com` (zaten örnekte var)

3. **Uygulamayı ayağa kaldırın:**

   ```bash
   docker compose up --build
   ```

4. **Tarayıcıdan erişin:** [http://localhost:8000](http://localhost:8000)

   Nginx 8000 portunu dışarı açar; istekler `web` konteynerine iletilir. Veritabanı (PostgreSQL 16) otomatik başlar; entrypoint migration ve (tanımlıysa) superuser oluşturur.

### Callback URL (Iyzico ödeme sonrası yönlendirme)

Ödeme/abonelik tamamlandığında Iyzico kullanıcıyı sizin bir URL’e yönlendirir. Bu adresin **dışarıdan erişilebilir** olması gerekir:

- **Yerel test:** [ngrok](https://ngrok.com) ile tünel açın: `ngrok http 8000` → çıkan adresi `.env` içinde `NGROK_PUBLIC_URL=https://xxxx.ngrok.io` (veya `PAYMENT_CALLBACK_HOST`) olarak verin.
- **Sunucu:** `PAYMENT_CALLBACK_HOST=https://your-domain.com` şeklinde ayarlayın.

### Abonelik planlarını Iyzico ile eşleştirme

İlk kez abonelik kullanacaksanız, Iyzico tarafında product/pricing plan oluşturmak için:

```bash
docker compose exec web python manage.py setup_subscription_plans
```

Abonelik özelliği Iyzico hesabında varsayılan kapalıdır; açtırmak için Iyzico destek (entegrasyon@iyzico.com) ile iletişime geçin.

### Production

- `.env` içinde `DEBUG=False`, güçlü `SECRET_KEY`, gerçek Iyzico anahtarları ve `IYZICO_BASE_URL=api.iyzipay.com` kullanın.
- `docker-compose.yml` içinde `web` servisi varsayılan olarak `runserver` ile çalışır (geliştirme). Production’da image’ı `CMD` override etmeden build ederseniz `Dockerfile` içindeki **Gunicorn** komutu kullanılır.

---

## Önemli URL’ler

| URL | Açıklama |
|-----|----------|
| `/` | Ana sayfa |
| `/accounts/login/` | Giriş |
| `/payments/start/` | Ödeme başlat (giriş gerekli) |
| `/payments/callback/` | Iyzico’nun ödeme sonrası yönlendirdiği adres |
| `/payments/result/` | Ödeme sonucu (başarılı/başarısız) |
| `/api/payments/checkout/initialize/` | JWT ile ödeme başlatma (API) |
| `/api/payments/{id}/` | Ödeme durumu (JWT) |
| `/subscriptions/` | Abonelik planları (Basic, Pro, Enterprise) |
| `/subscriptions/checkout/<plan_id>/` | Abonelik başlat (Iyzico Subscription Checkout Form) |
| `/subscriptions/callback/` | Iyzico abonelik callback |
| `/subscriptions/result/` | Abonelik sonucu |
| `/subscriptions/my/` | Aboneliklerim |
| `/subscriptions/webhook/` | Iyzico yenileme webhook’u (panelden tanımlanır) |

---

## Abonelik (Subscription)

Aylık yenilenen 3 paket (Basic 99 TRY, Pro 199 TRY, Enterprise 399 TRY) tanımlıdır. Iyzico’da product/pricing plan oluşturmak için:

```bash
docker compose exec web python manage.py setup_subscription_plans
```

Yenileme bildirimleri için Iyzico panelde webhook URL’i şu şekilde tanımlanır: `https://your-domain.com/subscriptions/webhook/`.

**Yenileme nasıl çalışır?** Tahsilatı Iyzico yapar; uygulama periyodik cron çalıştırmaz. Plan periyodu (aylık) dolunca Iyzico kartı otomatik çeker ve sonucu webhook ile bildirir (`subscription.order.success` / `subscription.order.failure`). Backend bu webhook’u dinleyip abonelik durumunu (ACTIVE / PAST_DUE) günceller.

---

## Ödeme akışı (Iyzico Checkout Form)

1. **Initialize** — Kullanıcı ödeme başlattığında backend Iyzico’ya istek atar; `token` ve `paymentPageUrl` döner. Kart bilgisi sunucunuza gelmez (PCI yükü sizde olmaz).
2. Kullanıcı Iyzico sayfasında öder; Iyzico tarayıcıyı sizin **callback URL**’e yönlendirir (`token` query’de).
3. **Callback** — Backend yalnızca bu `token` ile Iyzico’ya **Retrieve** çağrısı yapar. Başarı/başarısızlık kararı **sadece** Retrieve cevabına göre verilir; URL parametrelerine güvenilmez.
4. Retrieve sonucuna göre `Payment` güncellenir, audit log yazılır, kullanıcı `/payments/result/` sayfasına yönlendirilir.

Detaylı akış, `conversation_id` / idempotency ve test kartları: **`apps/payments/README.md`**

---

## Docker olmadan yerel geliştirme

Gerekirse projeyi doğrudan Python ile de çalıştırabilirsiniz:

1. `cp .env.example .env` ve Iyzico anahtarlarını doldurun.
2. Yerel PostgreSQL kullanıyorsanız `DATABASE_URL`’i buna göre güncelleyin (örn. `postgres://user:pass@localhost:5432/dbname`).
3. `pip install -r requirements.txt` → `python manage.py migrate` → `python manage.py runserver`.
4. Abonelik planları için: `python manage.py setup_subscription_plans`.

Testler: `pip install -r requirements.txt` sonrası `pytest tests/ -v`.
