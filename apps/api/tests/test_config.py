from niyam.config import Settings


def test_render_postgres_url_uses_psycopg():
    assert Settings(database_url="postgres://u:p@dpg-x:5432/niyam").database_url == "postgresql+psycopg://u:p@dpg-x:5432/niyam"
    assert Settings(database_url="postgresql://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="postgresql+psycopg://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"


def test_console_path_none_when_unset(tmp_path):
    assert Settings(console_dir="").console_path is None
    assert Settings(console_dir=str(tmp_path / "missing")).console_path is None
    assert Settings(console_dir=str(tmp_path)).console_path == tmp_path
