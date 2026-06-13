"""RDS Secrets Manager payload merge (dbname from config) and URL shape."""

import unittest

from app.core.secrets.models import RDSPostgresSecrets, rds_database_field_absent
from app.core.secrets.slot_loading import _merge_into_sm_payload


class TestRdsSecretMerge(unittest.TestCase):
    def test_rds_database_field_absent_when_no_db_keys(self) -> None:
        d = {"username": "u", "password": "p", "host": "h"}
        self.assertTrue(rds_database_field_absent(d))

    def test_rds_database_field_absent_false_when_dbname_present(self) -> None:
        d = {"username": "u", "password": "p", "host": "h", "dbname": "x"}
        self.assertFalse(rds_database_field_absent(d))

    def test_merge_adds_dbname_for_rds_slot(self) -> None:
        payload = {"username": "u", "password": "p", "host": "h", "port": 5432}
        merged = _merge_into_sm_payload("rds_postgres", payload, {"dbname": "midas_dev"})
        r = RDSPostgresSecrets.from_mapping(merged)
        self.assertEqual(r.database, "midas_dev")

    def test_merge_does_not_overwrite_existing_dbname(self) -> None:
        payload = {"username": "u", "password": "p", "host": "h", "dbname": "keep_me"}
        merged = _merge_into_sm_payload("rds_postgres", payload, {"dbname": "other"})
        r = RDSPostgresSecrets.from_mapping(merged)
        self.assertEqual(r.database, "keep_me")

    def test_sqlalchemy_url_includes_sslmode_when_set(self) -> None:
        r = RDSPostgresSecrets(
            username="u",
            password="p",
            host="h.example.com",
            port=5432,
            database="db",
        )
        url = r.sqlalchemy_url(sslmode="require")
        self.assertIn("sslmode=require", url)
        self.assertTrue(url.startswith("postgresql+psycopg2://"))
