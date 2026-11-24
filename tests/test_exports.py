"""Image, 3D and contact encoding, checked by reading the output back."""
import os
import re

import cv2
import PIL.Image
import pytest
import qrcode

from conftest import app


def make_qr(data, **kwargs):
    qr = qrcode.QRCode(box_size=10, border=4, **kwargs)
    qr.add_data(data)
    qr.make(fit=True)
    return qr, qr.make_image(fill_color="black", back_color="white").convert("RGBA")


def read_back(pil_img, tmp_path, name="qr.png"):
    path = str(tmp_path / name)
    pil_img.convert("RGB").save(path)
    return app.try_decode_with_preprocessing(cv2.imread(path))


def test_qr_with_a_logo_still_scans(tmp_path):
    logo = tmp_path / "logo.png"
    PIL.Image.new("RGBA", (64, 64), (220, 30, 30, 255)).save(logo)
    qr, img = make_qr("https://example.com/with-logo", error_correction=qrcode.constants.ERROR_CORRECT_H)

    with_logo = app.add_logo_aligned_to_grid(img, str(logo), qr, max_module_ratio=0.22)

    assert with_logo.size == img.size
    assert read_back(with_logo, tmp_path) == "https://example.com/with-logo"


def test_inverted_colors_are_read(tmp_path):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data("light on dark")
    img = qr.make_image(fill_color="white", back_color="black")

    assert read_back(img, tmp_path) == "light on dark"


def test_contact_survives_a_round_trip_through_a_qr(tmp_path):
    card = app.build_vcard(
        "Ana", "Pérez; Ruiz", "Cafe, Bar & Co", "Owner", "+34 600 000 000",
        "ana@example.com", "https://example.com", "Main St 1", "Bilbao", "48001", "Spain",
    )
    _, img = make_qr(card)

    decoded = read_back(img, tmp_path)

    assert app.is_vcard(decoded)
    contact = app.parse_vcard(decoded)
    assert contact["name"] == "Ana Pérez; Ruiz"
    assert contact["org"] == "Cafe, Bar & Co"
    assert contact["phones"] == ["+34 600 000 000"]
    assert contact["emails"] == ["ana@example.com"]
    assert "Bilbao" in contact["address"]


def test_stl_export_builds_a_closed_model_of_the_qr(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "QR_DIR", str(tmp_path))
    monkeypatch.setattr(app, "PINNED_DIR", str(tmp_path / "pinned"))
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data("3D")
    qr.make(fit=True)
    qr.make_image().save(tmp_path / "model.png")
    dark_modules = sum(row.count(True) for row in qr.get_matrix())

    out = app.StlBuilder("model", base_height=2, pillar_height=1, pixel_size=0.5).generate_stl(
        str(tmp_path / "model.stl")
    )

    text = open(out).read()
    assert text.startswith("solid qr_code\n") and text.endswith("endsolid qr_code\n")
    # Base: top, bottom and 4 sides (2 triangles each); each dark module: top + 4 sides.
    assert text.count("facet normal") == 2 * (6 + 5 * dark_modules)
    heights = {float(z) for z in re.findall(r"vertex \S+ \S+ (\S+)", text)}
    assert heights == {0.0, 2.0, 3.0}


def test_stl_export_inverted_raises_the_light_modules(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "QR_DIR", str(tmp_path))
    monkeypatch.setattr(app, "PINNED_DIR", str(tmp_path / "pinned"))
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data("3D")
    qr.make(fit=True)
    qr.make_image().save(tmp_path / "model.png")
    light_modules = sum(row.count(False) for row in qr.get_matrix())

    out = app.StlBuilder("model", invert=True).generate_stl(str(tmp_path / "inv.stl"))

    assert open(out).read().count("facet normal") == 2 * (6 + 5 * light_modules)


def test_missing_qr_cannot_be_exported(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "QR_DIR", str(tmp_path))
    monkeypatch.setattr(app, "PINNED_DIR", str(tmp_path))

    with pytest.raises(FileNotFoundError):
        app.StlBuilder("nope").generate_stl(str(tmp_path / "x.stl"))
    assert not os.path.exists(tmp_path / "x.stl")
