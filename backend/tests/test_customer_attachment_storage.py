from app.services.customer_attachment_storage import parse_qbo_attachable_id


def test_parse_qbo_attachable_id_attachable_response_shape():
    data = {"AttachableResponse": [{"Attachable": {"Id": "99", "SyncToken": "0"}}]}
    assert parse_qbo_attachable_id(data) == "99"


def test_parse_qbo_attachable_id_top_level_attachable():
    data = {"Attachable": {"Id": "fake-attach"}}
    assert parse_qbo_attachable_id(data) == "fake-attach"


def test_parse_qbo_attachable_id_missing():
    assert parse_qbo_attachable_id({}) is None
