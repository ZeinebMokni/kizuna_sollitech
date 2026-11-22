"""Add normalized weather and soil observation storage."""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0003"
down_revision = "20261122_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.db import Base
    from app.modules.data_sources import models as data_source_models  # noqa: F401
    from app.modules.data_sources import models_observations as observation_models  # noqa: F401

    Base.metadata.create_all(
        op.get_bind(),
        tables=[
            observation_models.WeatherObservation.__table__,
            observation_models.SoilProfileObservation.__table__,
        ],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO data_sources
              (id, code, name, provider, kind, license, terms_url,
               spatial_resolution, temporal_resolution, methodology_url, description,
               created_at, updated_at)
            VALUES
              (gen_random_uuid(), 'nasa_power', 'NASA POWER',
               'NASA', 'api', 'Public use with attribution',
               'https://power.larc.nasa.gov/data-access-viewer/',
               '0.5 x 0.625 degrees', 'daily',
               'https://power.larc.nasa.gov/',
               'Gridded meteorology and solar radiation estimates', now(), now()),
              (gen_random_uuid(), 'open_meteo_archive', 'Open-Meteo Archive',
               'Open-Meteo', 'api', 'Free tier is non-commercial',
               'https://open-meteo.com/en/terms',
               'grid point', 'hourly aggregated to daily',
               'https://open-meteo.com/en/docs',
               'Reanalysis-derived historical weather', now(), now()),
              (gen_random_uuid(), 'open_meteo_forecast', 'Open-Meteo Forecast',
               'Open-Meteo', 'api', 'Free tier is non-commercial',
               'https://open-meteo.com/en/terms',
               'grid point', 'hourly forecast',
               'https://open-meteo.com/en/docs',
               'Projected weather forecast', now(), now()),
              (gen_random_uuid(), 'soilgrids', 'ISRIC SoilGrids',
               'ISRIC', 'api', 'CC BY 4.0',
               'https://creativecommons.org/licenses/by/4.0/',
               '250 m', 'static',
               'https://www.isric.org/explore/soilgrids',
               'Machine-learning soil property predictions', now(), now()),
              (gen_random_uuid(), 'dgacta', 'DGACTA Agro-weather Stations',
               'DGACTA / CRDA', 'api',
               'Licence Nationale de Données Publiques Ouvertes',
               'https://catalog.agridata.tn/',
               'station point', 'hourly',
               NULL,
               'Tunisian station observations requiring quality control', now(), now())
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS soil_profile_observations"))
    op.execute(sa.text("DROP TABLE IF EXISTS weather_observations"))
