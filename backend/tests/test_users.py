import pytest

from app import users


@pytest.fixture
def conn(tmp_path):
    return users.connect(tmp_path / "t.db")


def test_phone_normalization():
    assert users.normalize_phone("98765 43210") == "+919876543210"
    assert users.normalize_phone("+91-98765-43210") == "+919876543210"
    assert users.normalize_phone("09876543210") == "+919876543210"
    for bad in ["12345", "5876543210", "", None]:
        with pytest.raises(users.InvalidInput):
            users.normalize_phone(bad)


def test_signup_and_token_login(conn):
    user, token = users.create_user(conn, "Asha", "9876543210", "mr", [{"name": "Aai", "phone": "9123456780"}])
    assert user["contacts"] == [{"name": "Aai", "phone": "+919123456780"}]
    assert users.user_for_token(conn, token)["id"] == user["id"]
    assert users.user_for_token(conn, "wrong") is None


def test_contacts_rules(conn):
    with pytest.raises(users.InvalidInput):
        users.create_user(conn, "Asha", "9876543210", "en", [])
    with pytest.raises(users.InvalidInput):
        users.create_user(conn, "Asha", "9876543210", "en", [{"name": "Me", "phone": "9876543210"}])
    user, _ = users.create_user(conn, "Asha", "9876543210", "en", [{"name": "A", "phone": "9123456780"}])
    out = users.replace_contacts(conn, user["id"], [{"name": "B", "phone": "9000000001"},
                                                     {"name": "B again", "phone": "9000000001"}])
    assert len(out) == 1
