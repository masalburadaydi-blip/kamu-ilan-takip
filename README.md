# Kamu İlan Takip

Amaç: Kamu kurumlarının personel ilanlarını düzenli kontrol edip, kullanıcının belirlediği şartlara uyan yeni ilanları Telegram'a göndermek.

Filtreler:
- Kamu kurumları
- KPSS puanı şartı açıkça aranmayacak ilanlar
- Önlisans veya lisans mezuniyeti
- Ankara öncelikli, Türkiye geneli
- Kadrolu ilanlar öncelikli; sözleşmeli ilanlar da dahil
- Tüm uygun kamu kadroları (yalnızca sekreterlik değil)

## Kurulum
1. Bu klasördeki dosyaları GitHub'daki `kamu-ilan-takip` deponuza yükleyin.
2. GitHub > Settings > Secrets and variables > Actions bölümünden:
   - `8637020584:AAGRXDtCZFfFOxYPeHycksSD8ljqqpA0P4I`
   - `7963291137`
   secret'larını ekleyin.
3. Actions sekmesinden `Kamu ilanlarını kontrol et` workflow'unu çalıştırarak test edin.

Not: GitHub zamanlamaları tam dakika garantisi vermez; yoğunluk nedeniyle gecikme olabilir. Site erişimi veya site yapısı değişirse ilgili kaynak geçici olarak ilan veremeyebilir. CAPTCHA/login aşılmaya çalışılmaz.
