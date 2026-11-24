"""End-to-end flows through the real UI, driven by events like a user would."""
import json
import os

import cv2
import flet as ft
import qrcode

from conftest import app


def is_fab(icon):
    return lambda c: isinstance(c, ft.FloatingActionButton) and c.icon == icon


def is_button(label):
    return lambda c: isinstance(c, ft.Button) and getattr(c.content, "value", None) == label


def is_field(label):
    return lambda c: isinstance(c, ft.TextField) and (c.label == label or c.hint_text == label)


def library_titles(driver):
    """Names of the QR entries shown in the "All" library list."""
    tiles = driver.find_all(lambda c: isinstance(c, ft.ListTile) and isinstance(c.title, ft.Text))
    return [t.title.value for t in tiles]


def save_qr_png(directory, name, data):
    path = os.path.join(directory, f"{name}.png")
    qrcode.make(data).save(path)
    return path


def decode(path):
    return app.try_decode_with_preprocessing(cv2.imread(path))


async def open_creator(driver):
    await driver.click(driver.find(is_fab(ft.Icons.ADD_ROUNDED)))
    sheet = driver.find(lambda c: isinstance(c, ft.BottomSheet) and c.fullscreen)
    assert sheet.open
    return sheet


async def test_first_launch_shows_the_tutorial(start_app, data_dir):
    settings = data_dir / "settings.json"
    settings.write_text(json.dumps({**json.loads(settings.read_text()), "First_run": "True"}))

    driver = await start_app()

    shown = " ".join(driver.text_of(c) for c in driver.page.controls)
    assert "Your QRs, made quicker." in shown
    assert not library_titles(driver)


async def test_empty_library_shows_the_tip(start_app):
    driver = await start_app()

    assert library_titles(driver) == []
    tip = driver.find(lambda c: isinstance(c, ft.Container) and "No QR codes yet" in driver.text_of(c))
    assert tip.visible


async def test_library_lists_saved_qrs(start_app, data_dir):
    save_qr_png(data_dir / "qr_codes", "Shop", "https://example.com/shop")
    save_qr_png(data_dir / "pinned_qr_codes", "Wifi at home", "WIFI:S:Home;T:WPA;P:secret;;")

    driver = await start_app()

    titles = library_titles(driver)
    assert "Shop" in titles
    assert "Wifi at home" in titles


async def test_create_a_text_qr_and_find_it_in_the_library(start_app, data_dir):
    driver = await start_app()
    await open_creator(driver)

    await driver.type_text(driver.find(is_field("Enter URL or text")), "https://quicker.example/hello")
    await driver.type_text(driver.find(is_field("Name your QR code")), "Hello link")
    await driver.click(driver.find(is_button("Save QR")))

    saved = data_dir / "qr_codes" / "Hello link.png"
    assert saved.exists()
    assert decode(str(saved)) == "https://quicker.example/hello"
    assert "Hello link" in library_titles(driver)
    assert not driver.find(lambda c: isinstance(c, ft.BottomSheet) and c.fullscreen).open


async def test_create_a_wifi_qr(start_app, data_dir):
    driver = await start_app()
    await open_creator(driver)

    type_dropdown = driver.find(lambda c: isinstance(c, ft.Dropdown) and c.value == "Text/URL")
    driver.session.apply_patch(type_dropdown._i, {"value": "WIFI"})
    await driver.event(type_dropdown, "select", "WIFI")
    await driver.type_text(driver.find(is_field("Enter network name")), "Cafe")
    await driver.type_text(driver.find(is_field("Enter network password")), "latte123")
    await driver.type_text(driver.find(is_field("Name your QR code")), "Cafe wifi")
    await driver.click(driver.find(is_button("Save QR")))

    saved = data_dir / "qr_codes" / "Cafe wifi.png"
    assert decode(str(saved)) == "WIFI:S:Cafe;T:WPA2;P:latte123;;"


async def test_saving_without_content_asks_for_it(start_app, data_dir):
    driver = await start_app()
    await open_creator(driver)

    await driver.type_text(driver.find(is_field("Enter URL or text")), "")
    await driver.click(driver.find(is_button("Save QR")))

    dialog = driver.find(lambda c: isinstance(c, ft.AlertDialog) and c.open)
    assert driver.text_of(dialog.title) == "Missing required fields"
    assert os.listdir(data_dir / "qr_codes") == []


async def test_names_with_path_characters_are_rejected(start_app, data_dir):
    driver = await start_app()
    await open_creator(driver)

    await driver.type_text(driver.find(is_field("Enter URL or text")), "hello")
    await driver.type_text(driver.find(is_field("Name your QR code")), "../escape")
    await driver.click(driver.find(is_button("Save QR")))

    dialog = driver.find(lambda c: isinstance(c, ft.AlertDialog) and c.open)
    assert "invalid characters" in driver.text_of(dialog.content)
    assert os.listdir(data_dir / "qr_codes") == []
    assert not (data_dir / "escape.png").exists()


async def test_duplicate_names_get_a_suffix(start_app, data_dir):
    save_qr_png(data_dir / "qr_codes", "Menu", "https://example.com/menu")
    driver = await start_app()
    await open_creator(driver)

    await driver.type_text(driver.find(is_field("Enter URL or text")), "https://example.com/menu-v2")
    await driver.type_text(driver.find(is_field("Name your QR code")), "Menu")
    await driver.click(driver.find(is_button("Save QR")))

    assert decode(str(data_dir / "qr_codes" / "Menu.png")) == "https://example.com/menu"
    assert decode(str(data_dir / "qr_codes" / "Menu_1.png")) == "https://example.com/menu-v2"


def library_tile(driver, title):
    return driver.find(
        lambda c: isinstance(c, ft.ListTile) and isinstance(c.title, ft.Text) and c.title.value == title
    )


async def test_opening_a_qr_shows_its_content(start_app, data_dir):
    save_qr_png(data_dir / "qr_codes", "Docs", "https://example.com/docs")
    driver = await start_app()

    await driver.click(library_tile(driver, "Docs"))

    # Wide windows show details beside the library, narrow ones in a sheet.
    shown = " ".join(driver.text_of(root) for root in driver.roots())
    assert "https://example.com/docs" in shown


async def test_opening_a_qr_on_a_phone_uses_a_sheet(start_app, data_dir):
    save_qr_png(data_dir / "qr_codes", "Docs", "https://example.com/docs")
    driver = await start_app(width=400, height=850, platform="android")

    await driver.click(library_tile(driver, "Docs"))

    sheet = driver.find(lambda c: isinstance(c, ft.BottomSheet) and c.open and c.draggable)
    assert "https://example.com/docs" in driver.text_of(sheet)


async def test_pinning_a_qr_moves_it_to_pinned(start_app, data_dir):
    save_qr_png(data_dir / "qr_codes", "Ticket", "https://example.com/ticket")
    driver = await start_app()
    await driver.click(library_tile(driver, "Ticket"))

    pin = driver.find(lambda c: isinstance(c, ft.IconButton) and c.icon == ft.Icons.PUSH_PIN_OUTLINED)
    await driver.click(pin)

    assert (data_dir / "pinned_qr_codes" / "Ticket.png").exists()
    assert not (data_dir / "qr_codes" / "Ticket.png").exists()
    assert pin.icon == ft.Icons.PUSH_PIN_ROUNDED


def library_entries(driver):
    """Each library entry: its list row and its grid card."""
    return {
        c.controls[0].title.value: c
        for c in driver.find_all(lambda c: isinstance(c, ft.Column) and isinstance(c.controls, list) and c.controls and isinstance(c.controls[0], ft.ListTile))
    }


def shown_as_grid(entry):
    tile, divider, card = entry.controls
    return card.visible and not tile.visible and not divider.visible and entry.col == app.GRID_COLUMNS


async def test_grid_button_shows_the_library_as_cards(start_app, data_dir):
    save_qr_png(data_dir / "qr_codes", "Shop", "https://example.com/shop")
    save_qr_png(data_dir / "pinned_qr_codes", "Wifi at home", "WIFI:S:Home;T:WPA;P:secret;;")
    driver = await start_app()
    assert not any(shown_as_grid(e) for e in library_entries(driver).values())

    await driver.click(driver.find(is_button("Grid")))
    assert all(shown_as_grid(e) for e in library_entries(driver).values())

    # A card opens the details like a row does; pinning re-adds the entry, still as a card.
    shop_card = library_entries(driver)["Shop"].controls[2]
    await driver.click(shop_card)
    await driver.click(driver.find(lambda c: isinstance(c, ft.IconButton) and c.icon == ft.Icons.PUSH_PIN_OUTLINED))
    assert (data_dir / "pinned_qr_codes" / "Shop.png").exists()
    assert shown_as_grid(library_entries(driver)["Shop"])

    pinned_filter = driver.find(is_button("Pinned"))
    await driver.click(pinned_filter)
    assert pinned_filter.bgcolor == ft.Colors.SECONDARY_CONTAINER

    await driver.click(driver.find(is_button("List")))
    assert not any(shown_as_grid(e) for e in library_entries(driver).values())


async def test_the_ui_follows_the_saved_language(start_app, data_dir):
    settings = data_dir / "settings.json"
    settings.write_text(json.dumps({**json.loads(settings.read_text()), "Language": "es"}))

    driver = await start_app()

    assert driver.find_all(is_button("Guardar QR"))
    assert not driver.find_all(is_button("Save QR"))
