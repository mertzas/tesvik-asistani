"""Alembic ortam yapilandirmasi.

DIKKAT - iki tuzak var, ikisi de burada cozuldu:

1) app/models_cilek.py, app/models.py'daki AYNI Base'i kullaniyor ama ayri
   bir dosyada. Sadece app.models import edilirse cilek tablolari (parsel,
   sensor_okuma vb.) metadata'ya kaydolmaz ve `alembic revision
   --autogenerate` bu tablolari "fazlalik" sanip DROP TABLE uretir.
   Bu yuzden asagida iki modul de import ediliyor.

2) Veritabani adresi os.getenv("DATABASE_URL") ile okunursa .env dosyasi
   devreye girmez (onu pydantic-settings okuyor) ve alembic yanlis/bos
   adrese baglanir. Tek dogru kaynak app.models.settings.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models import Base, settings
import app.models_cilek  # noqa: F401  - cilek tablolarini metadata'ya kaydeder

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _tip_karsilastir(context, denetlenen_sutun, metadata_sutun,
                    denetlenen_tip, metadata_tip) -> bool | None:
    """Tip degisikligi gercekten var mi?

    SQLite'in "type affinity" tasarimi yuzunden veritabanindan okunan tip
    modeldeki tipe hic benzemiyor: UUID sutunlari NUMERIC, String sutunlari
    TEXT, Float sutunlari REAL olarak geri geliyor. Bu yuzden hicbir sey
    degismemisken bile `alembic check` 20 sahte "modify_type" farki
    bildiriyordu (dogrulandi 2026-09-26). Bu gurultu iki somut zarar veriyor:
    check komutu kalici olarak kirmizi kaldigi icin islevsizlesiyor ve
    `revision --autogenerate` her calistirmada anlamsiz tip goclerini
    dosyaya yaziyor - SQLite'ta bunlar batch modunda tabloyu bastan
    olusturdugu icin bedelsiz de degil.

    Cozum: SQLite'ta tip karsilastirmasini kapatiyoruz (None dondurmek
    "farksiz kabul et" demek). PostgreSQL'de - gercek uretim hedefi -
    tipler gerçek oldugu icin karsilastirma acik kaliyor (True/None yerine
    alembic'in kendi varsayilan davranisina birakiyoruz).
    """
    if context.dialect.name == "sqlite":
        return False
    return None  # alembic'in varsayilan karsilastirmasi devreye girsin


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite ALTER TABLE'i kisitli destekler; batch modu olmadan
            # sutun silme/degistirme goclerinde hata verir.
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=_tip_karsilastir,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
