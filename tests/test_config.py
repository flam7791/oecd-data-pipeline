import pytest

from oecd_pipeline.config import ConfigError, load_config


def test_loads_three_indicators(cfg):
    assert [i.id for i in cfg.indicators] == ["unemployment_rate", "cpi_inflation", "gdp_growth"]
    assert cfg.settings.countries == ("USA", "FRA", "ITA")


def test_key_must_take_country_list(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(
        '[settings]\nbase_url="x"\ncountries=["USA"]\nstart_period="2024"\n'
        '[[indicator]]\nid="a"\nname="a"\ndataflow="d"\nkey="USA.M"\nfrequency="M"\nunit="u"\n'
    )
    with pytest.raises(ConfigError, match="countries"):
        load_config(p)


def test_rejects_unknown_frequency(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(
        '[settings]\nbase_url="x"\ncountries=["USA"]\nstart_period="2024"\n'
        '[[indicator]]\nid="a"\nname="a"\ndataflow="d"\nkey="{countries}.W"\nfrequency="W"\nunit="u"\n'
    )
    with pytest.raises(ConfigError, match="frequency"):
        load_config(p)
