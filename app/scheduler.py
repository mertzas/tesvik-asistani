"""
Zamanlanmış veri güncelleme işleri (jobs). APScheduler kullanarak background'da
cron zamanlarına göre scraper'ları çalıştırır. Sunucu başlangıcında etkinleşir,
kesintiye uğrama riski olmadıkça (örn. tek process modunda) arka planda çalışır.

Zamanlamalar:
- HKS hal fiyatları (150+ ürün): Günlük 23:00 (canlı hal verisi sabah-akşam güncellenir)
- HKS ihracat fiyatları: Günlük 23:30 (hal verisiyle senkronize)
- Çilek hal fiyatları (özel panel): Günlük 22:00 (panel verisi için)
- TMO fiyatları: Haftada pazartesi 03:00 (mevsimsel, sık değişmez)
- TÜİK makro göstergeler: Ayda 1. gün 01:00 (resmi istatistikler aylık yayınlanır)

Tüm joblar kendi logger'ı ile hata/başarısını log'luyor; sıkıntı varsa (net sorunu,
site yapısı değişiklikleri vb.) uygulamayı çökmez, sadece loglara "bu job başarısız"
yazar.
"""
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def _run_job(job_name: str, job_func, *args, **kwargs) -> None:
    """Bir scraper jobını çalıştır, hata durumunda log'la ama uygulamayı çöktürme."""
    try:
        logger.info(f"[{job_name}] başlıyor...")
        result = job_func(*args, **kwargs)
        logger.info(f"[{job_name}] başarılı: {result}")
    except Exception as e:
        logger.error(f"[{job_name}] hata: {e}", exc_info=True)


def _job_hal_urun_fiyat() -> str:
    """HKS Fiyat Detayları bülteninden 150+ ürün güncel hal fiyatları."""
    from app.scrapers import hal_urun_fiyat
    result = hal_urun_fiyat.run()
    return f"{result} kayıt"


def _job_hal_ihracat_fiyat() -> str:
    """HKS İhracat Fiyat Bülteni'nden ~40 ürün ihracat fiyatları."""
    from app.scrapers import hal_ihracat_fiyat
    result = hal_ihracat_fiyat.run()
    return f"{result} kayıt"


def _job_hal_cilek_fiyat() -> str:
    """HKS'den çilek (kalite bazlı) hal fiyatları — çilek paneli için."""
    from app.scrapers import hal_cilek_fiyat
    result = hal_cilek_fiyat.run()
    return f"{result} kayıt"


def _job_tmo_fiyatlar() -> str:
    """TMO buğday/arpa fiyatları — statik curated veri, scraper yok; dummy."""
    # TMO fiyatları tmo_fiyatlar.py içinde hardcoded; refresh yok ama
    # ileride TMO'nun açık veri API'sine bağlanırsa burada olacak.
    logger.info("TMO fiyatları: şu an statik curated veri, API refresh henüz yapılmadı")
    return "statik veri"


def _job_tuik_makro() -> str:
    """TÜİK EVDS API'sinden makro göstergeler (TUFE, tarım girdi enflasyonu, dış ticaret)."""
    from app.scrapers import tuik_macro
    result = tuik_macro.run()
    return f"{result} gösterge"


def _job_tarim_bakanligi() -> str:
    """Tarım Bakanlığı destek programları — şu an curated veri, statik."""
    from app.scrapers import tarim_bakanligi
    result = tarim_bakanligi.run()
    return f"{result} kayıt"


def setup_scheduler() -> BackgroundScheduler:
    """Tüm jobları tanımla ve scheduler'ı döndür. main.py'de startup event'inde başlatılır."""
    scheduler = BackgroundScheduler()

    # HKS hal fiyatları — her gün 23:00
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=23, minute=0, second=0),
        id="hal_urun_fiyat",
        args=("hal_urun_fiyat", _job_hal_urun_fiyat),
        replace_existing=True,
    )

    # HKS ihracat fiyatları — her gün 23:30
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=23, minute=30, second=0),
        id="hal_ihracat_fiyat",
        args=("hal_ihracat_fiyat", _job_hal_ihracat_fiyat),
        replace_existing=True,
    )

    # Çilek hal fiyatları — her gün 22:00
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=22, minute=0, second=0),
        id="hal_cilek_fiyat",
        args=("hal_cilek_fiyat", _job_hal_cilek_fiyat),
        replace_existing=True,
    )

    # TMO fiyatları — haftada pazartesi 03:00
    scheduler.add_job(
        _run_job,
        CronTrigger(day_of_week=0, hour=3, minute=0, second=0),  # 0 = Monday
        id="tmo_fiyatlar",
        args=("tmo_fiyatlar", _job_tmo_fiyatlar),
        replace_existing=True,
    )

    # TÜİK makro göstergeler — ayda 1. gün 01:00
    scheduler.add_job(
        _run_job,
        CronTrigger(day=1, hour=1, minute=0, second=0),
        id="tuik_makro",
        args=("tuik_makro", _job_tuik_makro),
        replace_existing=True,
    )

    # Tarım Bakanlığı destekleri — ayda 5. gün 02:00 (curated veri, düşük sıklık)
    scheduler.add_job(
        _run_job,
        CronTrigger(day=5, hour=2, minute=0, second=0),
        id="tarim_bakanligi",
        args=("tarim_bakanligi", _job_tarim_bakanligi),
        replace_existing=True,
    )

    logger.info("✅ Scheduler kuruldu: 6 job tanımlandı")
    return scheduler
