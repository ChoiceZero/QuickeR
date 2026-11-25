"""QR contents written by other generators are recognised and shown field by field."""
import flet as ft
import pytest
import qrcode

from conftest import app


def parse(text):
    return app.parse_qr_content(text)


@pytest.mark.parametrize("text, ssid, security, password", [
    ("WIFI:S:Home;T:WPA;P:secret;;", "Home", "WPA", "secret"),  # QuickeR's own order
    ("WIFI:T:WPA;S:Home;P:secret;;", "Home", "WPA", "secret"),  # Android / ZXing order
    ("wifi:P:secret;S:Home;T:WPA2;H:false;;", "Home", "WPA2", "secret"),
    (r'WIFI:S:"My\;Net";T:WEP;P:p\:a\\ss;;', "My;Net", "WEP", r"p:a\ss"),
    ("WIFI:T:nopass;S:Open Cafe;;", "Open Cafe", "", ""),
    ("WIFI:S:NoType;P:pw;;", "NoType", "", "pw"),
])
def test_wifi_in_any_field_order(text, ssid, security, password):
    kind, wifi = parse(text)
    assert kind == "wifi"
    assert (wifi["ssid"], wifi["security"], wifi["password"]) == (ssid, security, password)


def test_hidden_wifi_is_flagged():
    assert parse("WIFI:T:WPA;S:Lab;P:x;H:true;;")[1]["hidden"]


@pytest.mark.parametrize("text, to, subject, body", [
    ("mailto:ana@example.com", "ana@example.com", "", ""),
    ("MAILTO:ana@example.com?body=Hi%20there&subject=Lunch", "ana@example.com", "Lunch", "Hi there"),
    ("mailto:?to=ana@example.com&subject=C%2B%2B+talk", "ana@example.com", "C++ talk", ""),
    ("MATMSG:TO:ana@example.com;SUB:Lunch;BODY:See you\\; at noon;;", "ana@example.com", "Lunch", "See you; at noon"),
    ("SMTP:ana@example.com:Lunch:See you", "ana@example.com", "Lunch", "See you"),
])
def test_email_formats(text, to, subject, body):
    assert parse(text) == ("email", {"to": to, "subject": subject, "body": body})


@pytest.mark.parametrize("text, number, message", [
    ("SMSTO:34600111222:Hello", "+34600111222", "Hello"),  # QuickeR stores no "+"
    ("SMSTO:+34600111222:Hi: there", "+34600111222", "Hi: there"),
    ("smsto:600111222:Hello", "600111222", "Hello"),
    ("SMS:+1555123:Ping", "+1555123", "Ping"),
    ("sms:+1555123?body=Call%20me", "+1555123", "Call me"),
    ("sms:+1555123;?body=Call%20me", "+1555123", "Call me"),
    ("MMSTO:+1555123:Pic", "+1555123", "Pic"),
])
def test_sms_formats(text, number, message):
    assert parse(text) == ("sms", {"number": number, "message": message})


@pytest.mark.parametrize("text, number", [
    ("tel:+34600111222", "+34600111222"),
    ("TEL:+1-555-0100", "+1-555-0100"),
])
def test_phone_any_case(text, number):
    assert parse(text) == ("phone", {"number": number})


@pytest.mark.parametrize("text, lat, lng, place", [
    ("geo:43.26,-2.93", "43.26", "-2.93", ""),
    ("GEO:43.26,-2.93,120", "43.26", "-2.93", ""),
    ("geo:43.26,-2.93?q=Guggenheim+Bilbao", "43.26", "-2.93", "Guggenheim Bilbao"),
    ("geo:0,0?q=43.26,-2.93(Museum)", "0", "0", "Museum"),
    ("geo:43.26,-2.93;u=35", "43.26", "-2.93", ""),
])
def test_geo_with_altitude_and_labels(text, lat, lng, place):
    assert parse(text) == ("geo", {"lat": lat, "lng": lng, "place": place})


def test_event_with_parameters_and_folded_lines():
    ics = (
        "BEGIN:VEVENT\r\nUID:42\r\nSUMMARY:Team\r\n  sync\r\n"
        "DTSTART;TZID=Europe/Madrid:20261201T093000\r\nDTEND;VALUE=DATE:20261202\r\n"
        "LOCATION:Room 4\\, floor 2\r\nEND:VEVENT"
    )
    kind, event = parse(ics)
    assert kind == "event"
    assert event["summary"] == "Team sync"
    assert event["location"] == "Room 4, floor 2"
    assert app.format_ics_datetime(event["start"]) == "Day: 2026-12-01 Time: 09:30"
    assert app.format_ics_datetime(event["end"]) == "2026-12-02"


def test_quickers_own_event_without_times():
    kind, event = parse("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nSUMMARY:Party\r\nLOCATION:Home\r\nEND:VEVENT\r\nEND:VCALENDAR")
    assert (kind, event["summary"], event["location"], event["start"]) == ("event", "Party", "Home", "")


def test_mecard_contact():
    kind, contact = parse("MECARD:N:Doe,John;TEL:+1555;TEL:+1666;EMAIL:j@x.com;URL:http\\://x.com;ADR:1 Main St;;")
    assert kind == "contact"
    assert contact["name"] == "John Doe"
    assert contact["phones"] == ["+1555", "+1666"]
    assert contact["emails"] == ["j@x.com"]
    assert contact["urls"] == ["http://x.com"]
    assert contact["address"] == "1 Main St"


def test_bizcard_contact():
    kind, contact = parse("BIZCARD:N:Ana;X:Ruiz;T:CTO;C:Acme;B:+3460;E:ana@acme.io;;")
    assert kind == "contact"
    assert (contact["name"], contact["title"], contact["org"]) == ("Ana Ruiz", "CTO", "Acme")
    assert (contact["phones"], contact["emails"]) == (["+3460"], ["ana@acme.io"])


def test_two_factor_setup_code():
    kind, otp = parse("otpauth://totp/GitHub:alice%40example.com?secret=JBSWY3DP&issuer=GitHub&digits=6")
    assert kind == "otp"
    assert (otp["issuer"], otp["account"], otp["secret"], otp["type"]) == ("GitHub", "alice@example.com", "JBSWY3DP", "TOTP")


def test_crypto_payment():
    kind, pay = parse("bitcoin:bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh?amount=0.01&label=Shop&message=Order%2042")
    assert kind == "crypto"
    assert pay == {"currency": "Bitcoin", "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                   "amount": "0.01", "label": "Shop", "message": "Order 42"}


def test_sepa_payment():
    epc = "BCD\n002\n1\nSCT\nBPOTBEB1\nRed Cross\nBE72000000001616\nEUR12.50\n\n\nDonation\n"
    kind, pay = parse(epc)
    assert kind == "payment"
    assert (pay["name"], pay["iban"], pay["amount"], pay["reference"]) == ("Red Cross", "BE72000000001616", "12.50 EUR", "Donation")


@pytest.mark.parametrize("text, kind", [
    ("https://example.com", "link"),
    ("HTTP://EXAMPLE.COM/A", "link"),
    ("market://details?id=io.github.choicezero", "link"),
    ("www.example.com", "link"),
    ("Visit http://x.com today", "text"),  # mentions a link but is text
    ("Dash: see you at 5", "text"),  # starts like a crypto scheme but is text
    ("just some text", "text"),
    ("", "text"),
])
def test_links_and_text(text, kind):
    assert parse(text)[0] == kind


@pytest.mark.parametrize("text", [
    "WIFI:", "MECARD:", "mailto:", "SMSTO:", "tel:", "geo:", "BEGIN:VEVENT", "otpauth://", "bitcoin:", "BCD\n\n\nSCT\n\n\n\n",
])
def test_empty_payloads_still_give_rows(text):
    kind, fields = parse(text)
    rows = app.qr_detail_rows(kind, fields)
    assert all(value for _, value, _ in rows)


def save_qr_png(directory, name, data):
    qrcode.make(data).save(directory / f"{name}.png")


def library_tile(driver, title):
    return driver.find(
        lambda c: isinstance(c, ft.ListTile) and isinstance(c.title, ft.Text) and c.title.value == title
    )


@pytest.mark.parametrize("content, shown, list_name", [
    ("WIFI:T:WPA;S:Guest Net;P:hunter22;;", ["Guest Net", "Network name", "WPA", "hunter22"], "Guest Net"),
    ("MATMSG:TO:ana@example.com;SUB:Hello;BODY:Hi;;", ["ana@example.com", "Hello", "Subject"], "ana@example.com"),
    ("MECARD:N:Doe,John;TEL:+1555;;", ["John Doe", "+1555", "Phone number"], "John Doe"),
    ("sms:+1555123?body=Call%20me", ["+1555123", "Call me", "Preset message"], "+1555123"),
    ("otpauth://totp/GitHub:alice?secret=JBSWY3DP", ["GitHub", "alice", "JBSWY3DP", "Secret key"], "GitHub · alice"),
])
async def test_external_qr_details_show_each_field(start_app, data_dir, content, shown, list_name):
    save_qr_png(data_dir / "qr_codes", "External", content)
    driver = await start_app()

    tile = library_tile(driver, "External")
    assert driver.text_of(tile.subtitle) == list_name
    await driver.click(tile)

    text = " ".join(driver.text_of(root) for root in driver.roots())
    for value in shown:
        assert value in text
    assert "Failed to unpack" not in text
