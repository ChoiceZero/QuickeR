import os
import qrcode
import cv2 
import time 
import flet as ft
from flet_color_pickers import MaterialPicker, BlockPicker
from pathlib import Path
import platform
import shutil
import json
import base64
from io import BytesIO  
import asyncio
import subprocess
import PIL 
import urllib.parse
import datetime
import numpy as np
import logging

#ft.Colors.INVERSE_SURFACE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
QR_DIR = os.path.join(BASE_DIR, "qr_codes")
PINNED_DIR = os.path.join(BASE_DIR, "pinned_qr_codes")

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(PINNED_DIR, exist_ok=True)

APP_VERSION = "__VERSION__"

ERROR_CORRECTION_MAP = {
    "L (7%)": qrcode.constants.ERROR_CORRECT_L,
    "M (15%)": qrcode.constants.ERROR_CORRECT_M,
    "Q (25%)": qrcode.constants.ERROR_CORRECT_Q,
    "H (30%)": qrcode.constants.ERROR_CORRECT_H,
}

os.path.join(ASSET_DIR,"github-white-icon.webp")

def hex_to_rgba(color_str):
    if color_str.startswith("#"):
        c = color_str.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (r, g, b, 255)
    else:   
        return PIL.ImageColor.getcolor(color_str, "RGBA")

def normalize_hex(color_str):
    if color_str.startswith("#"):
        c = color_str.lstrip("#")
        if len(c) == 8:  # AARRGGBB
            c = c[2:]
        return "#" + c
    else:
        r, g, b = PIL.ImageColor.getcolor(color_str, "RGB")
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

def normalize_picker_date(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone().date()

def try_decode_with_preprocessing(image):
    detector = cv2.QRCodeDetector()

    data, _, _ = detector.detectAndDecode(image)
    if data:
        return data

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    data, _, _ = detector.detectAndDecode(thresh_bgr)
    if data:
        return data

    _, thresh_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    thresh_inv_bgr = cv2.cvtColor(thresh_inv, cv2.COLOR_GRAY2BGR)
    data, _, _ = detector.detectAndDecode(thresh_inv_bgr)
    if data:
        return data

    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    adaptive_bgr = cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR)
    data, _, _ = detector.detectAndDecode(adaptive_bgr)
    return data

def add_logo_aligned_to_grid(pil_img, logo_data, qr_obj, max_module_ratio=0.25, bg_color=(255, 255, 255, 255)):
    box_size = qr_obj.box_size
    border = qr_obj.border
    modules_count = len(qr_obj.get_matrix())

    max_logo_modules = int(modules_count * max_module_ratio)
    if max_logo_modules % 2 == 0:
        max_logo_modules -= 1
    max_logo_modules = max(max_logo_modules, 1)

    logo_size_px = max_logo_modules * box_size

    logo = PIL.Image.open(BytesIO(logo_data)).convert("RGBA")
    logo = logo.resize((logo_size_px, logo_size_px))

    qr_w, qr_h = pil_img.size
    pos_x = (qr_w - logo_size_px) // 2
    pos_y = (qr_h - logo_size_px) // 2

    pil_img = pil_img.convert("RGBA")
    backdrop = PIL.Image.new("RGBA", (logo_size_px, logo_size_px), bg_color)
    pil_img.paste(backdrop, (pos_x, pos_y))
    pil_img.paste(logo, (pos_x, pos_y), logo)
    return pil_img


def relative_luminance(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = [int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(hex1, hex2):
    l1, l2 = relative_luminance(hex1), relative_luminance(hex2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def get_pictures_folder() -> str:
        system = platform.system()

        if system == "Linux":
            try:
                result = subprocess.run(
                    ["xdg-user-dir", "PICTURES"],
                    capture_output=True, text=True
                )
                path = result.stdout.strip()
                if path:
                    return path
            except FileNotFoundError:
                pass
            return str(Path.home() / "Pictures")

        elif system == "Windows":
            return str(Path.home() / "Pictures")  
        elif system == "Android":
            return "/storage/emulated/0/Pictures"

        else:  
            return str(Path.home() / "Pictures")

class StlBuilder:
    def __init__(self, qr_id, base_height=2, pillar_height=4, pixel_size=1.0, threshold=128, invert=False):
        self.qr_id = qr_id
        self.base_height = base_height
        self.pillar_height = pillar_height
        self.pixel_size = pixel_size
        self.threshold = threshold
        self.invert = invert

    def _get_bw_matrix(self):
        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")

        if os.path.exists(qr_path):
            img_path = qr_path
        elif os.path.exists(pinned_path):
            img_path = pinned_path
        else:
            raise FileNotFoundError(f"QR code image for ID {self.qr_id} not found.")

        # Convertir a blanco y negro puro (binarización), sin importar el color original
        img = PIL.Image.open(img_path).convert("L")
        arr = np.array(img)
        bw = arr < self.threshold  # True = módulo negro (elevado)
        if self.invert:
            bw = ~bw
        return bw

    def _write_facet(self, f, normal, v0, v1, v2):
        f.write(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")
        f.write("    outer loop\n")
        f.write(f"      vertex {v0[0]:.6f} {v0[1]:.6f} {v0[2]:.6f}\n")
        f.write(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}\n")
        f.write(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}\n")
        f.write("    endloop\n")
        f.write("  endfacet\n")

    def _write_quad(self, f, p0, p1, p2, p3):
        v1v = np.subtract(p1, p0)
        v2v = np.subtract(p2, p0)
        normal = np.cross(v1v, v2v)
        norm_len = np.linalg.norm(normal)
        if norm_len != 0:
            normal = normal / norm_len
        self._write_facet(f, normal, p0, p1, p2)
        self._write_facet(f, normal, p0, p2, p3)

    def generate_stl(self, output_path):
        bw = self._get_bw_matrix()
        h, w = bw.shape
        s = self.pixel_size
        base_h = self.base_height
        top_h = self.base_height + self.pillar_height

        with open(output_path, "w") as f:
            f.write("solid qr_code\n")

            # Base plana completa (a altura base_h)
            self._write_quad(
                f,
                (0, 0, base_h), (w * s, 0, base_h),
                (w * s, h * s, base_h), (0, h * s, base_h),
            )
            # Fondo completo (altura 0)
            self._write_quad(
                f,
                (0, 0, 0), (0, h * s, 0),
                (w * s, h * s, 0), (w * s, 0, 0),
            )
            # Paredes exteriores de la placa base
            outer = [
                ((0, 0), (w * s, 0)),
                ((w * s, 0), (w * s, h * s)),
                ((w * s, h * s), (0, h * s)),
                ((0, h * s), (0, 0)),
            ]
            for (ax, ay), (bx, by) in outer:
                p0 = (ax, ay, 0)
                p1 = (bx, by, 0)
                p2 = (bx, by, base_h)
                p3 = (ax, ay, base_h)
                self._write_quad(f, p0, p1, p2, p3)

            # Un cubo (pilar) por cada módulo negro
            for y in range(h):
                for x in range(w):
                    if not bw[y, x]:
                        continue
                    x0, x1 = x * s, (x + 1) * s
                    y0, y1 = y * s, (y + 1) * s

                    self._write_quad(
                        f,
                        (x0, y0, top_h), (x1, y0, top_h),
                        (x1, y1, top_h), (x0, y1, top_h),
                    )
                    self._write_quad(f, (x0, y0, base_h), (x1, y0, base_h), (x1, y0, top_h), (x0, y0, top_h))
                    self._write_quad(f, (x1, y0, base_h), (x1, y1, base_h), (x1, y1, top_h), (x1, y0, top_h))
                    self._write_quad(f, (x1, y1, base_h), (x0, y1, base_h), (x0, y1, top_h), (x1, y1, top_h))
                    self._write_quad(f, (x0, y1, base_h), (x0, y0, base_h), (x0, y0, top_h), (x0, y1, top_h))

            f.write("endsolid qr_code\n")

        return output_path

class LogoPicker:
    def __init__(self, page):
        self.page = page
        self.file_picker = ft.FilePicker()
        page.services.append(self.file_picker)
        page.update()

    async def pick(self, allowed_extensions=None):
        files = await self.file_picker.pick_files(allowed_extensions=allowed_extensions)
        return files[0].path if files else None

class QRCodes:
    def __init__(self, page, input,all_view,regular_view,pinned_view):    
        self.all_view = all_view
        self.regular_view = regular_view
        self.pinned_view = pinned_view
        self.page = page
        self.divider_rect = ft.VerticalDivider(color=ft.Colors.BLACK, width=1, thickness=30)
        self.date = ""
        self.url = ""
        self.filetext = ""
        self.id = ""
        self.img = None
        self.qr_id = ""
        self.qr_row = None
        self.qr_txt = ""
        self.initial_input = input
        self.pin_state = False
        self.qr_size= ""
        self.type = None # 0-> URL, 1-> Text, 2-> Contact, 3-> Wifi, 4-> Location, 5-> Event, 6-> Email, 7-> Phone, 8-> SMS
        self.share = ft.Share()
        self.status = ft.Text()
        self.result_raw = ft.Text()
        self.primary_hex = None
        self.bg_hex = None
        self.stl_invert = False

    def get_qr_date(self, qr_id):
        if os.path.exists(os.path.join(QR_DIR, f"{qr_id}.png")):
            self.date = time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(time.ctime(os.path.getctime(os.path.join(QR_DIR, f"{qr_id}.png")))))
        elif os.path.exists(os.path.join(PINNED_DIR, f"{qr_id}.png")):
            self.date = time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(time.ctime(os.path.getctime(os.path.join(PINNED_DIR, f"{qr_id}.png")))))
        return self.date

    def get_qr_size(self, qr_id):
        if os.path.exists(os.path.join(QR_DIR, f"{qr_id}.png")):
            raw_size = os.path.getsize(os.path.join(QR_DIR, f"{qr_id}.png"))
        elif os.path.exists(os.path.join(PINNED_DIR, f"{qr_id}.png")):
            raw_size = os.path.getsize(os.path.join(PINNED_DIR, f"{qr_id}.png"))
        else:
            return None
        if raw_size < (1024 * 1024):
            return f"{round(raw_size / 1024, 2)} KB"
        else:
            return f"{round(raw_size / (1024*1024), 2)} MB"

    def get_qr_url(self, qr_id):
        qr_txt = cv2.QRCodeDetector()
        self.url = qr_txt.detectAndDecode(os.path.abspath(qr_id+".png"))[0]
        return self.url

    def create_qr(self,image):
        self.qr_id = self.id_assigner()
        self.date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.url = self.initial_input
        self.img= image
        self.img.save(os.path.join(QR_DIR, f"{self.qr_id}.png"))  
        self.display_qr(False)
        snack = ft.SnackBar(
            content=ft.Text("¡QR code generated!"),
            bgcolor=ft.Colors.WHITE,
            duration= 4000,
            show_close_icon=True,
        )
        self.page.show_dialog(snack)

    def id_assigner(self):
        initial_time = time.localtime()
        output_time = str(initial_time.tm_year)+str(initial_time.tm_mon)+str(initial_time.tm_mday)+str(initial_time.tm_hour)+str(initial_time.tm_min)+str(initial_time.tm_sec)
        return output_time
    
    def display_qr(self,pinned, prepend=True):
        self.qr_size= self.get_qr_size(self.qr_id)
        self.qr_date = self.get_qr_date(self.qr_id)
        self.main_container = ft.Column(
            controls=[
                ft.ListTile(
                    subtitle=ft.Row(controls=[
                        ft.Container(padding=5,bgcolor=ft.Colors.TERTIARY_CONTAINER,border_radius=5, border=ft.Border.all(width=1, color=ft.Colors.TERTIARY_FIXED_DIM),content=ft.Text(value=str(self.qr_size), size=10)),
                        ft.Text(italic=True,color=ft.Colors.GREY_400,value=self.qr_id+".png", overflow="ELLIPSIS"),
                    ]),
                    on_click=lambda e:self.display_details_bottomsheet(),
                    #on_hover=lambda e: self.on_hover(e),
                    content_padding=2,
                    margin=ft.Margin.only(left=10, right=10, top=-10, bottom=-10),
                ),
                ft.Divider(height=1, color=ft.Colors.SURFACE_CONTAINER),
            ]
        )

        if "WIFI:S:" in self.url:
            self.display_name = self.url.split(":")[2].split(";")[0]
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.WIFI_ROUNDED, color=ft.Colors.PRIMARY,size=30))
        elif "BEGIN:VCALENDAR" in self.url:
            self.display_name = self.url.split("\n")[3].split(":")[1]
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.CALENDAR_TODAY_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        elif "mailto:" in self.url:
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.EMAIL_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.display_name = self.url.split("?")[0].split(":")[1]
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        elif "SMSTO:" in self.url:
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.MESSAGE_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.display_name = self.url.split(":")[1]
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        elif "tel:" in self.url:
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.PHONE_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.display_name = self.url.split(":")[1]
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        elif "geo:" in self.url:
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.PIN_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.display_name = self.url.split(":")[1]
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        elif "http" in self.url:
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.LINK_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.display_name = self.url
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        else:
            self.main_container.controls[0].leading = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER, padding=5,border_radius=10,content=ft.Icon(icon=ft.Icons.TEXT_FIELDS_ROUNDED, color=ft.Colors.PRIMARY,size=30))
            self.display_name = self.url
            self.main_container.controls[0].title = ft.Text(value=str(self.display_name), size=18,font_family="MaterialRounded", overflow="ELLIPSIS")
        
        if prepend:
            if not self.all_view.controls:
                self.all_view.controls.insert(0, ft.Text(value=time.strftime("%Y-%m-%d", time.localtime()), size=12, color=ft.Colors.GREY_400, font_family="MaterialRounded"))
                self.pinned_view.controls.insert(0, ft.Text(value=time.strftime("%Y-%m-%d", time.localtime()), size=12, color=ft.Colors.GREY_400, font_family="MaterialRounded"))
                self.regular_view.controls.insert(0, ft.Text(value=time.strftime("%Y-%m-%d", time.localtime()), size=12, color=ft.Colors.GREY_400, font_family="MaterialRounded"))
                self.all_view.controls.insert(0, self.main_container)
                if pinned:
                    self.main_container.controls[0].trailing = (ft.Icon(icon=ft.Icons.PUSH_PIN_ROUNDED))
                    self.pinned_view.controls.insert(0, self.main_container)
                else:    
                    self.regular_view.controls.insert(0, self.main_container)
            elif self.all_view.controls and self.all_view.controls[0] != time.strftime("%Y-%m-%d", time.localtime()):
                self.all_view.controls.insert(0, ft.Text(value=time.strftime("%Y-%m-%d", time.localtime()), size=12, color=ft.Colors.GREY_400, font_family="MaterialRounded"))
                self.pinned_view.controls.insert(0, ft.Text(value=time.strftime("%Y-%m-%d", time.localtime()), size=12, color=ft.Colors.GREY_400, font_family="MaterialRounded"))
                self.regular_view.controls.insert(0, ft.Text(value=time.strftime("%Y-%m-%d", time.localtime()), size=12, color=ft.Colors.GREY_400, font_family="MaterialRounded"))
                self.all_view.controls.insert(0, self.main_container)
                if pinned:
                    self.main_container.controls[0].trailing = (ft.Icon(icon=ft.Icons.PUSH_PIN_ROUNDED))
                    self.pinned_view.controls.insert(0, self.main_container)
                else:    
                    self.regular_view.controls.insert(0, self.main_container)
            else:
                self.all_view.controls.insert(1, self.main_container)
                if pinned:
                    self.main_container.controls[0].trailing = (ft.Icon(icon=ft.Icons.PUSH_PIN_ROUNDED))
                    self.pinned_view.controls.insert(1, self.main_container)
                else:    
                    self.regular_view.controls.insert(1, self.main_container)
        else:
            self.all_view.controls.append(self.main_container)
            if pinned:
                self.main_container.controls[0].trailing = (ft.Icon(icon=ft.Icons.PUSH_PIN_ROUNDED))
                self.pinned_view.controls.append(self.main_container)
            else:    
                self.regular_view.controls.append(self.main_container)

    def on_hover(self,e):
        if e.data == True:
            self.main_container.bgcolor=ft.Colors.SECONDARY_FIXED_DIM
        else:
            self.main_container.bgcolor=ft.Colors.SECONDARY_CONTAINER

    def delete_qr_action(self, e):
        delete_dialog = ft.AlertDialog(
            title=ft.Text("Are you sure you want to delete this QR code?"),
            alignment=ft.Alignment.CENTER,
            content=ft.Text("This action cannot be undone." + "\n" + "However, you can always generate a new QR code with the same URL."),
            actions=[
                ft.Button(content="Cancel", on_click=lambda e: self.page.pop_dialog()),
                ft.Button(icon=ft.Icons.DELETE,bgcolor=ft.Colors.RED_900,content="Delete", on_click=lambda e: self.delete_qr())],
            open=True)
        self.page.show_dialog(delete_dialog)

    def delete_qr(self):
        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")
        if os.path.exists(qr_path):
            os.remove(qr_path)
            self.all_view.controls.remove(self.main_container)
        elif os.path.exists(pinned_path):
            os.remove(pinned_path)
            self.all_view.controls.remove(self.main_container)
        self.clean_bs_up()
        self.page.pop_dialog()
        self.page.update()
    
    def download_qr_action(self):
        self.filetext=ft.TextField(hint_text="Enter filename here",expand=True,label="Rename QR")
        download_dialog = ft.AlertDialog(
            title=ft.Text("Export Options"),
            on_dismiss=lambda e: self.handle_download_dialog_dismissed(),
            alignment=ft.Alignment.CENTER,
            actions=[
                ft.Row(expand=True,alignment="center",controls=self.filetext),
                ft.Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_folder()),margin=ft.Margin(bottom=5,top=10),height=80,padding=10,bgcolor=ft.Colors.SECONDARY_CONTAINER,content=ft.Row(alignment="center",controls=[ft.Icon(icon=ft.Icons.FOLDER_COPY_ROUNDED),ft.Text(value="Select a folder (.png)")])),
                ft.Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_gallery()),margin=ft.Margin(bottom=5,top=5),height=80,padding=10,bgcolor=ft.Colors.SECONDARY_CONTAINER,content=ft.Row(alignment="center",controls=[ft.Icon(icon=ft.Icons.IMAGE_ROUNDED),ft.Text(value="Add to gallery")])),
                ft.Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_stl()),margin=ft.Margin(top=5),height=80,padding=10,bgcolor=ft.Colors.SECONDARY_CONTAINER,content=ft.Row(alignment="center",controls=[ft.Icon(icon=ft.Icons.FILE_COPY_ROUNDED),ft.Text(value="Export as 3D model (.STL)")])),
            ],
        )
        self.page.show_dialog(download_dialog)

    def handle_download_dialog_dismissed(self):
        self.filetext.value = ""


    async def export_to_gallery(self):
        folder_path = get_pictures_folder()
        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")
        if os.path.exists(qr_path):
            src = qr_path
        elif os.path.exists(pinned_path):
            src = pinned_path
        else:
            self.page.show_dialog(ft.SnackBar(content=ft.Text("QR file not found")))
            return
        try:
            shutil.copy(src, f"{folder_path}/{self.filetext.value}.png")
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"QR exported to {folder_path}")))
        except Exception as ex:
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"Error: {ex}")))

    async def export_to_folder(self):
        if platform.system() == "Android":
            default_dir = "/storage/emulated/0/Pictures"
        else:
            default_dir = str(Path.home())

        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="Select folder to export QR",
            initial_directory=default_dir
        )

        if not folder_path:
            return

        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")
        if os.path.exists(qr_path):
            src = qr_path
        elif os.path.exists(pinned_path):
            src = pinned_path
        else:
            self.page.show_dialog(ft.SnackBar(content=ft.Text("QR file not found")))
            return
        try:
            shutil.copy(src, f"{folder_path}/{self.filetext.value}.png")
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"QR exported to {folder_path}")))
        except Exception as ex:
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"Error: {ex}")))

    async def export_to_stl(self):
        if not self.filetext.value:
            self.page.show_dialog(ft.SnackBar(content=ft.Text("Please enter a filename first")))
            return

        invert_dialog = ft.AlertDialog(
            title=ft.Text("Invert 3D model?"),
            alignment=ft.Alignment.CENTER,
            content=ft.Text("By default, the dark squares of the QR are raised, thus the dark area protrudes.\n Invert this so the light modules are raised and the dark areas are indented instead?"),
            actions=[
                ft.TextButton("No, keep as is", on_click=lambda e: self._continue_stl_export(False)),
                ft.TextButton("Yes, invert", on_click=lambda e: self._continue_stl_export(True)),
            ],
            open=True)
        self.page.show_dialog(invert_dialog)

    def _continue_stl_export(self, invert):
        self.stl_invert = invert
        self.page.pop_dialog()
        asyncio.ensure_future(self._pick_folder_and_export_stl())

    async def _pick_folder_and_export_stl(self):
        if platform.system() == "Android":
            default_dir = "/storage/emulated/0/Pictures"
        else:
            default_dir = str(Path.home())

        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="Select folder to export STL",
            initial_directory=default_dir
        )

        if not folder_path:
            return

        filename = self.filetext.value if self.filetext.value.endswith(".stl") else f"{self.filetext.value}.stl"
        destination_path = os.path.join(folder_path, filename)

        try:
            builder = StlBuilder(self.qr_id, invert=self.stl_invert)
            builder.generate_stl(destination_path)
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"STL exported to {folder_path}")))
        except Exception as ex:
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"Error generating STL: {ex}")))

    def set_filetext(self, e):
        self.filetext = str(e.control.value)
        print(self.filetext)

    def download_qr(self):
        if self.filetext == "":
            input_dialog = ft.AlertDialog(
                title=ft.Text("Enter a valid file name"),
                alignment=ft.Alignment.CENTER,
                content=ft.Text("Please enter a valid file name (do not leave blank)."),
                actions=[ft.TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                open=True)
            self.page.show_dialog(input_dialog)
        else:
            self.page.pop_dialog()
            
            filename = self.filetext if self.filetext.endswith(".png") else f"{self.filetext}.png"
            
            downloads_path = ft.FilePicker.get_directory_path()
            destination_path = downloads_path / filename

            qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
            pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")
            if os.path.exists(qr_path):
                source_path = qr_path
            elif os.path.exists(pinned_path):
                source_path = pinned_path
            try:
                shutil.copy2(source_path, str(destination_path))
                if os.path.exists(destination_path+filename):
                    # Show success dialog
                    success_dialog = ft.AlertDialog(
                        title=ft.Text("Download Successful"),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(f"QR code saved to:\n{destination_path}"),
                        actions=[ft.TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                        open=True)
                    self.page.show_dialog(success_dialog)
                else:
                    error_dialog = ft.AlertDialog(
                        title=ft.Text("Error Saving File"),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("Destination QR code wasn't found upon final check."),
                        actions=[ft.TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                        open=True)
                    self.page.show_dialog(error_dialog)
            except Exception as ex: 
                error_dialog = ft.AlertDialog(
                    title=ft.Text("Error Saving File"),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(f"Error: {str(ex)}"),
                    actions=[ft.TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                    open=True)
                self.page.show_dialog(error_dialog)
            self.page.update()

    def pin_triggered(self):
        if os.path.exists(os.path.join(PINNED_DIR, f"{self.qr_id}.png")):
            self.pin_state = True
        self.pin_state = not self.pin_state
        if self.pin_state == True:
            self.pin_qr_action()
        else:
            self.unpin_qr_action()

    def pin_qr_action(self):
        self.pin_button.icon = ft.Icons.PUSH_PIN_ROUNDED
        shutil.move(os.path.join(QR_DIR, f"{self.qr_id}.png"), os.path.join(PINNED_DIR, f"{self.qr_id}.png"))
        self.regular_view.controls.remove(self.main_container)
        self.all_view.controls.remove(self.main_container)
        self.display_qr(True)

    def unpin_qr_action(self):
        self.pin_button.icon = ft.Icons.PUSH_PIN_OUTLINED
        try:
            shutil.move(os.path.join(PINNED_DIR, f"{self.qr_id}.png"), os.path.join(QR_DIR, f"{self.qr_id}.png"))
        except Exception:
            os.makedirs(PINNED_DIR, exist_ok=True)
            shutil.move(os.path.join(PINNED_DIR, f"{self.qr_id}.png"), os.path.join(QR_DIR, f"{self.qr_id}.png"))
        self.pinned_view.controls.remove(self.main_container)
        self.all_view.controls.remove(self.main_container)
        self.display_qr(False)

    def display_details_bottomsheet(self):
        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")

        self.pin_button = ft.IconButton(
            icon=ft.Icons.PUSH_PIN_OUTLINED,
            #alignment=ft.MainAxisAlignment.END,
            on_click=lambda e: self.pin_triggered(),
            style=ft.ButtonStyle(shape=ft.CircleBorder(),
            padding=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            icon_color=ft.Colors.INVERSE_SURFACE,icon_size=20),
        )

        if os.path.exists(qr_path):
            qrpath = qr_path
            qr = ft.Image(src=qr_path, border_radius=10, width=250, height=250)

        elif os.path.exists(pinned_path):
            qrpath = pinned_path
            qr = ft.Image(src=pinned_path, border_radius=10, width=250, height=250)
            self.pin_button.icon = ft.Icons.PUSH_PIN_ROUNDED       

        self.details_bs = ft.BottomSheet(draggable=True,show_drag_handle=True,use_safe_area=True,scrollable=False,fullscreen=True,open=False,on_dismiss=lambda e: self.clean_bs_up(),content=
            ft.Column(horizontal_alignment="center",scroll=ft.ScrollMode.AUTO,controls=[
                ft.Container(bgcolor=ft.Colors.INVERSE_PRIMARY,border_radius=30,content=qr,padding=20,margin=ft.Margin.only(left=20, right=20, bottom=5)),
                ft.Row(
                    alignment="center",
                    margin=ft.Margin.only(left=20, right=20),
                    spacing=3,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.DELETE_ROUNDED,
                            #alignment=ft.MainAxisAlignment.END,
                            on_click=lambda e: self.delete_qr_action(e),
                            style=ft.ButtonStyle(shape=ft.CircleBorder(),
                            padding=10,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                            icon_color=ft.Colors.INVERSE_SURFACE,icon_size=20),
                        ),
                        ft.Container(width=20),
                        ft.Button(
                            elevation=0,
                            icon=ft.Icons.DOWNLOAD,
                            content=ft.Text("Export options",size=16),
                            height=50,
                            color=ft.Colors.SURFACE,
                            bgcolor=ft.Colors.PRIMARY,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=50, top_right=25,bottom_left=50,bottom_right=25)),
                            ),
                            on_click=lambda e: self.download_qr_action(),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.OFFLINE_SHARE,
                            height=50,
                            width=45,
                            alignment=ft.Alignment.CENTER_LEFT,
                            icon_color=ft.Colors.SURFACE,
                            bgcolor=ft.Colors.PRIMARY,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=25, top_right=50,bottom_left=25,bottom_right=50)),
                            ),
                            on_click=lambda e: asyncio.ensure_future(self.do_share_files_from_paths())
                        ),
                        ft.Container(width=20),
                        self.pin_button,
                    ]
                ),
                ft.Divider(color=ft.Colors.GREY_400,thickness=0.2,leading_indent=20,trailing_indent=20,height=50),
                ft.ExpansionTile(
                    title=ft.Row(controls=[ft.Icon(icon=ft.Icons.INFO_ROUNDED),ft.Text(value="QR details", size=16)]),
                    tile_padding=ft.Padding.only(left=20, right=20, top=10, bottom=10),
                    controls_padding=ft.Padding.only(left=20, right=20, bottom=20),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    margin=ft.Margin.only(left=20, right=20),
                    shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                    collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                    controls=ft.Column(controls=[
                        ft.Row(controls=[ft.Icon(icon=ft.Icons.INSERT_LINK_ROUNDED),ft.Column(spacing=-3,controls=[ft.Text(value=("Raw data"), size=16),ft.Text(value=(self.url),size=11,overflow="ELLIPSIS")])]),
                        ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(bottom=5,top=0)),
                        ft.Row(controls=[ft.Icon(icon=ft.Icons.CALENDAR_MONTH_ROUNDED),ft.Column(spacing=-3,controls=[ft.Text(value=("Creation date"), size=16),ft.Text(value=(self.qr_date),size=11,overflow="ELLIPSIS")])]),
                        ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(bottom=5,top=0)),
                        ft.Row(controls=[ft.Icon(icon=ft.Icons.FOLDER_COPY_ROUNDED),ft.Column(spacing=-3,controls=[ft.Text(value=("Internal path"), size=16),ft.Container(content=ft.Text(value=(qrpath),size=11,no_wrap=False))]),]), 
                        ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(bottom=5,top=0)),
                        ft.Row(controls=[ft.Icon(icon=ft.Icons.INSERT_DRIVE_FILE_ROUNDED),ft.Column(spacing=-3,controls=[ft.Text(value=("Filesize"), size=16),ft.Text(value=(self.qr_size),size=11,overflow="ELLIPSIS")]),]),
                    ])
                ),
                ft.ExpansionTile(
                    title=ft.Row(controls=[ft.Icon(icon=ft.Icons.COLOR_LENS_ROUNDED),ft.Text(value="Color scheme", size=16)]),
                    tile_padding=ft.Padding.only(left=20, right=20, top=10, bottom=10),
                    controls_padding=ft.Padding.only(left=20, right=20, bottom=20),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    margin=ft.Margin.only(left=20, right=20),
                    shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                    collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                    controls=ft.Column(controls=[
                        ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(bottom=5,top=0)),
                        ft.Row(controls=[ft.Text(value=("Primary:")),ft.Container(expand=True),ft.Text(value=self.fill_color or "Error")]),
                        ft.Row(controls=[ft.Text(value=("Background:")),ft.Container(expand=True),ft.Text(value=self.back_color or "Error")]),
                    ])
                ),
            ]),
        )
        self.page.overlay.append(self.details_bs)
        self.page.update()
        self.details_bs.open = True
        self.page.update()
            
    def clean_bs_up(self):
        self.details_bs.open = False
        self.page.update()  
     
    async def do_share_files_from_paths(self):
        if self.page.web:
            self.status.value = "File sharing from paths is not supported on the web."
            return

        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")

        if os.path.exists(qr_path):
            file_path = qr_path
        elif os.path.exists(pinned_path):
            file_path = pinned_path
        else:
            self.page.show_dialog(ft.SnackBar(content=ft.Text("QR file not found")))
            return

        try:
            result = await self.share.share_files(
                [ft.ShareFile.from_path(os.path.abspath(file_path))],
                text="Sharing a file from memory",
            )
            self.status.value = f"Share status: {result.status}"
        except Exception as ex:
            self.page.show_dialog(ft.SnackBar(content=ft.Text(f"Share not supported on this platform: {ex}")))

    #async def do_share_uri(self):
    #    result = await self.share.share_uri("https://flet.dev")
    #    self.status.value = f"Share status: {result.status}"
    #    self.result_raw.value = f"Raw: {result.raw}"
        
def main(page: ft.Page):
    page.title = "QuickeR"
    #page.scroll = ScrollMode.ADAPTIVE
    preview_qr = ""
    last_qr_image = {"img": None}
    _debounce_task = {"task": None}
    logo_image_path = {"path": None}
    logo_picker_ref = {"instance": None}

    page.fonts = {
        "MaterialRounded":"GoogleSansFlex.ttf",
        "MaterialRoundedBold":"GoogleSansFlex-Bold.ttf",
        "MaterialRoundedLight":"GoogleSansFlex-Light.ttf"
    }

    def on_buttongroup_change(e: ft.ControlEvent):
        def perform_action(e):
            if e.control in pin_filter_buttongroup.controls:
                if pin_filter_buttongroup.controls[0] == e.control:
                    if regular_view in overview.controls:
                        overview.controls.remove(regular_view)
                    elif pinned_view in overview.controls:
                        overview.controls.remove(pinned_view)
                    overview.controls.append(all_view)
                elif pin_filter_buttongroup.controls[1] == e.control:
                    if regular_view in overview.controls:
                        overview.controls.remove(regular_view)
                    elif all_view in overview.controls:
                        overview.controls.remove(all_view)
                    overview.controls.append(pinned_view)
                elif pin_filter_buttongroup.controls[2] == e.control:
                    if all_view in overview.controls:
                        overview.controls.remove(all_view)
                    elif pinned_view in overview.controls:
                        overview.controls.remove(pinned_view)
                    overview.controls.append(regular_view)       
            #elif e.control in layout_mode_buttongroup.controls:
            #    if pin_filter_buttongroup.controls[0] == e.control:
            #        pass
            #    elif pin_filter_buttongroup.controls[1] == e.control:
            #        pass
            page.update()

        perform_action(e)

        for button in e.control.parent.controls:
            if button.bgcolor != ft.Colors.SURFACE_CONTAINER:
                if e.control.parent.controls[-1] == button:
                    button.style = ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=25, top_right=50,bottom_left=25,bottom_right=50)),
                    )
                elif e.control.parent.controls[0] == button:
                        button.style = ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=50, top_right=25,bottom_left=50,bottom_right=25)),
                        )
                else:
                    button.style = ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                    )
                button.bgcolor = ft.Colors.SURFACE_CONTAINER
                
                    
        e.control.bgcolor = ft.Colors.SECONDARY_CONTAINER
        e.control.style = ft.ButtonStyle(shape=ft.StadiumBorder())
    
        page.update()

    async def open_url(url_to_open,target: ft.UrlTarget):
        url = url_to_open
        await ft.UrlLauncher().launch_url(ft.Url(url=url, target=target))

    def display_preview_qr(url, qr_color_primary, qr_color_secondary, error_correct):
        preview_qr_area.controls.clear()

        if logo_image_path["path"]:
            error_correct = qrcode.constants.ERROR_CORRECT_H

        def build_qr(fill, back):
            q = qrcode.QRCode(error_correction=error_correct, box_size=10, border=4)
            q.add_data(str(url))
            q.make(fit=True)
            img = q.make_image(fill_color=fill, back_color=back).convert("RGBA")
            return q, img

        def is_readable(img):
            arr = np.array(img.convert("RGB"), dtype=np.uint8)
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            if arr.ndim != 3 or arr.shape[2] != 3:
                return False
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
            return bool(data)

        fill_color, back_color = qr_color_primary, qr_color_secondary
        qr_obj, pil_img = build_qr(fill_color, back_color)

        if not is_readable(pil_img) and str(url):
            fill_color, back_color = back_color, fill_color
            qr_obj, pil_img = build_qr(fill_color, back_color)

            if not is_readable(pil_img):
                fill_color, back_color = "black", "white"
                qr_obj, pil_img = build_qr(fill_color, back_color)

        if logo_image_path["path"]:
            pil_img = add_logo_aligned_to_grid(pil_img, logo_image_path["path"], qr_obj, max_module_ratio=0.22)

        pil_img = pil_img.convert("RGB")
        last_qr_image["img"] = pil_img
        archivo_temporal_ram = BytesIO()
        pil_img.save(archivo_temporal_ram, format="PNG")
        base64_puro = base64.b64encode(archivo_temporal_ram.getvalue()).decode("utf-8")
        uri_base64 = f"data:image/png;base64,{base64_puro}"
        preview_qr = ft.Image(src=uri_base64, width=200, height=200, border_radius=10)
        preview_qr_area.controls.append(preview_qr)
        page.update()

    def json_reader():
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "settings.json")
        try:
            with open(json_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data
        except FileNotFoundError:
            print(f"Error: Could not find the JSON file at {json_path}")
            return None

    def theme_loader():
        read_data = json_reader()
        color_string = read_data["Theme_color"]
        page.theme = ft.Theme(color_scheme_seed=getattr(ft.Colors, color_string), font_family="MaterialRounded")
        page.update()

    async def copy_text_to_clipboard(text):
        await ft.Clipboard().set(text)
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Text copied"),
            content=ft.Text("The text has been copied to the clipboard."),
            actions=[ft.TextButton("OK", on_click=lambda e: page.pop_dialog())],
            actions_alignment="end",
        ))

    def theme_changer(ColorId):
        data = json_reader()
        if data != None:
            if ColorId ==1:
                data["Theme_color"] = "BLUE_600"
            elif ColorId ==2:
                data["Theme_color"] = "GREEN_600"
            elif ColorId ==3:
                data["Theme_color"] = "YELLOW_600"
            elif ColorId ==4:
                data["Theme_color"] = "ORANGE_600"
            elif ColorId ==5:
                data["Theme_color"] = "RED_600"
            elif ColorId ==6:
                data["Theme_color"] = "PURPLE_600"
            elif ColorId ==7:
                data["Theme_color"] = "PINK_600"
            elif ColorId ==8:
                data["Theme_color"] = "GREY_600"
            elif ColorId ==9:
                data["Theme_color"] = "GREY_100"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "settings.json")
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        theme_loader()

    def clear_app_data():
        def clear_data_confirmed():
            page.pop_dialog()
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Clearing data..."),
                content=ft.ProgressRing(),
                actions=[],
                open=True,
            ))
            if os.path.exists(QR_DIR):
                shutil.rmtree(QR_DIR)
            if os.path.exists(PINNED_DIR):
                shutil.rmtree(PINNED_DIR)
            os.makedirs(QR_DIR, exist_ok=True)
            os.makedirs(PINNED_DIR, exist_ok=True)
            all_view.controls.clear()
            pinned_view.controls.clear()
            regular_view.controls.clear()
            page.update()
            page.pop_dialog()
            page.show_dialog(ft.SnackBar(content=ft.Text("All data cleared successfully.")))

        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Are you sure you want to clear all data?"),
            content=ft.Text("This will delete all QR codes and reset the app to its default state. This action cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                ft.TextButton("Clear Data", on_click=lambda e: clear_data_confirmed()),
            ],
            actions_alignment="end",
            open=True,
        ))

    def appearance_changer(AppeId):
        data = json_reader()
        if data != None:
            if AppeId ==1:
                data["Appearance"] = "System"
            elif AppeId ==2:
                data["Appearance"] = "Light"
            elif AppeId ==3:
                data["Appearance"] = "Dark"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "settings.json")
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        appearance_loader()

    def appearance_loader():
        read_data = json_reader()
        appearance = read_data["Appearance"]
        if appearance == "System":
            appearance_setting.selected=["1"]
            brightness = page.platform_brightness
            if brightness == ft.Brightness.DARK:
                page.theme_mode = ft.ThemeMode.DARK
            elif brightness == ft.Brightness.LIGHT:
                page.theme_mode= ft.ThemeMode.LIGHT
        elif appearance == "Dark":
            appearance_setting.selected=["3"]
            page.theme_mode = ft.ThemeMode.DARK
        elif appearance == "Light":
            appearance_setting.selected=["2"]
            page.theme_mode = ft.ThemeMode.LIGHT
        page.update()

    def load_qrs():
        files_with_meta = []
        for directory, is_pinned in [(PINNED_DIR, True), (QR_DIR, False)]:
            if os.path.exists(directory):
                for f in os.listdir(directory):
                    if f.endswith(".png"):
                        path = os.path.join(directory, f)
                        files_with_meta.append((path, f[:-4], is_pinned, os.path.getctime(path)))

        files_with_meta.sort(key=lambda x: x[3], reverse=True)

        last_date = None
        for path, qr_id, is_pinned, ctime in files_with_meta:
            date_str = time.strftime("%Y-%m-%d", time.localtime(ctime))
            if date_str != last_date:
                all_view.controls.append(ft.Text(value=date_str, size=16, color=ft.Colors.GREY_400))
                if is_pinned:
                    pinned_view.controls.append(ft.Text(value=date_str, size=16, color=ft.Colors.GREY_400))
                else:
                    regular_view.controls.append(ft.Text(value=date_str, size=16, color=ft.Colors.GREY_400))
                last_date = date_str

            image = cv2.imread(path)
            data = try_decode_with_preprocessing(image)
            if not data:
                continue

            qr = QRCodes(page, data, all_view, regular_view, pinned_view)
            qr.fill_color, qr.back_color = get_qr_colors(path)
            qr.qr_id = qr_id
            qr.date = qr.get_qr_date(qr_id)
            qr.url = data
            if is_pinned:
                qr.display_qr(True, prepend=False)
            else:
                qr.display_qr(False, prepend=False)

    def qr_creator_open():
        async def _open():
            if create_layout not in page.overlay:
                page.overlay.append(create_layout)
                page.update()
                await asyncio.sleep(0.05)
            create_layout.open = True
            page.update()
        page.run_task(_open)

    def input_checker():
        if qr_type_dropdown.value == "WIFI":
            if not wifi_name.value:
                return False
            if wifi_protocol_dropdown.value != "No password" and not wifi_password.value:
                return False
        elif qr_type_dropdown.value == "Email":
            if not email_address.value:
                return False
        elif qr_type_dropdown.value == "Phone":
            if not phone_number.value or not phone_prefix.value:
                return False
        elif qr_type_dropdown.value == "SMS":
            if not sms_number.value or not sms_prefix.value or not sms_message.value:
                return False
        elif qr_type_dropdown.value == "Location":
            if not location_lat.value or not location_lng.value:
                return False
        elif qr_type_dropdown.value == "Event":
            if not event_title.value or not event_location.value or not date_picker.start_value or not date_picker.end_value or not start_time_picker.value or not end_time_picker.value:
                return False
        else:  
            if not qr_url_input_field.value:
                return False
        return True

    def check_qr_contrast(fill, back):
        try:
            f_hex = normalize_hex(fill)
            b_hex = normalize_hex(back)
            ratio = contrast_ratio(f_hex, b_hex)
        except Exception:
            return
        if ratio < 2.0:
            return 1
        elif ratio < 2.5:
            return 2
        else:
            return False
    
    def qr_create_triggered():
        if input_checker():
            contrast_result = check_qr_contrast(qr_color_scheme_primary.color, qr_color_scheme_secondary.color)
            if contrast_result == 1:
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Low contrast"),
                    content=ft.Text("The selected colors have low contrast. This may result in a QR code that is difficult to scan. Do you want to continue?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                        ft.TextButton("Continue", on_click=lambda e: [page.pop_dialog(), create_qr_action()]),
                    ],
                    actions_alignment="end",
                ))
            elif contrast_result == 2:
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Moderate contrast"),
                    content=ft.Text("The selected colors have moderate contrast. This may result in a QR code that is difficult to scan. Do you want to continue?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                        ft.TextButton("Continue", on_click=lambda e: [page.pop_dialog(), create_qr_action()]),
                    ],
                    actions_alignment="end",
                ))
            else:
                create_qr_action()
        else:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Missing required fields"),
                content=ft.Text("Please fill in all required fields for the selected QR type."),
                actions=[ft.TextButton("OK", on_click=lambda e: page.pop_dialog())],
                actions_alignment="end",
            ))

    def create_qr_action():
            create_info = qr_url_input_field.value
            new_qr = QRCodes(page, create_info, all_view, regular_view,pinned_view)
            new_qr.fill_color, new_qr.back_color = qr_color_scheme_primary.color,qr_color_scheme_secondary.color
            if last_qr_image["img"]==None:
                print("image can't be Nonetype!")
            else:
                new_qr.create_qr(last_qr_image["img"])    
            qr_url_input_field.value = ""

    def on_mode_change(e):
        segment_value = (next(iter(e.control.selected)) if e.control.selected else None)
        if segment_value == "1":
            appearance_changer(1)
        elif segment_value == "2":
            appearance_changer(2)
        elif segment_value == "3":
            appearance_changer(3)

    logo_picker = LogoPicker(page)

    async def pick_logo():
        if logo_picker_ref["instance"] is None:
            logo_picker_ref["instance"] = LogoPicker(page)
            page.update()
            await asyncio.sleep(0.2)
        path = await logo_picker_ref["instance"].pick(["png", "jpg", "jpeg"])
        if path:
            logo_image_path["path"] = path
            prop_changed()

    def remove_logo():
        logo_image_path["path"] = None
        prop_changed()

    def get_qr_colors(image_path):
        img = PIL.Image.open(image_path).convert("RGB")
        colors = img.getcolors(maxcolors=1000000)
        colors.sort(key=lambda c: c[0], reverse=True)
        back_color = '#%02x%02x%02x' % colors[0][1]  
        fill_color = '#%02x%02x%02x' % colors[1][1]  
        return fill_color, back_color

    themes_row = ft.Container(padding=5,bgcolor=ft.Colors.SECONDARY_CONTAINER,border=ft.Border.all(width=1,color=ft.Colors.PRIMARY),border_radius=30,content=ft.Row(spacing=-10,scroll=ft.ScrollMode.AUTO,controls=[
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="blue", on_click=lambda e: theme_changer(1), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="green", on_click=lambda e: theme_changer(2), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="yellow", on_click=lambda e: theme_changer(3), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="orange", on_click=lambda e: theme_changer(4), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="red", on_click=lambda e: theme_changer(5), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="purple", on_click=lambda e: theme_changer(6), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="pink", on_click=lambda e: theme_changer(7), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="grey", on_click=lambda e: theme_changer(8), icon_size=50),
        ft.IconButton(icon=ft.Icons.CIRCLE, icon_color="white", on_click=lambda e: theme_changer(9), icon_size=50),
    ]))

    appearance_setting = ft.SegmentedButton(selected=["1"],on_change=lambda e: on_mode_change(e),show_selected_icon=True,segments=[
                ft.Segment(value="1",label=ft.Text("System"),icon=ft.Icon(ft.Icons.MONITOR)),
                ft.Segment(value="2",label=ft.Text("Light"),icon=ft.Icon(ft.Icons.WB_SUNNY_ROUNDED)),
                ft.Segment(value="3",label=ft.Text("Dark"),icon=ft.Icon(ft.Icons.DARK_MODE_ROUNDED)),
            ])

    preview_qr_area= ft.Row(controls=[], alignment=ft.MainAxisAlignment.CENTER,expand=False, tight=True)
    
    def clear_dialog():
        delete_dialog = ft.AlertDialog(
            title=ft.Text("Discard?"),
            alignment=ft.Alignment.CENTER,
            actions=[
                ft.Button(content="No", on_click=lambda e: page.pop_dialog()),
                ft.Button(icon=ft.Icons.DELETE,bgcolor=ft.Colors.RED_900,content="Yes", on_click=lambda e: clean_create_bs_up())],
            open=True)
        page.show_dialog(delete_dialog)
    
    def clean_create_bs_up():
        create_layout.open = False
        qr_url_input_field.value = ""
        page.update()   
    
    qr_type_dropdown = ft.Dropdown(border_radius=50,fill_color=ft.Colors.SURFACE_CONTAINER_LOW,filled=True,on_select=lambda e: type_trigger(e),border_width=0,value="URL/Link",options=[
        ft.DropdownOption(text="URL/Link",leading_icon=ft.Icons.LINK_ROUNDED),
        ft.DropdownOption(text="Text",leading_icon=ft.Icons.TEXT_FIELDS_ROUNDED),
        ft.DropdownOption(text="WIFI",leading_icon=ft.Icons.WIFI_ROUNDED),
        ft.DropdownOption(text="Email",leading_icon=ft.Icons.MAIL_OUTLINE_ROUNDED),
        ft.DropdownOption(text="Phone",leading_icon=ft.Icons.PHONE_ANDROID_ROUNDED),
        ft.DropdownOption(text="Location",leading_icon=ft.Icons.PIN_DROP_ROUNDED),
        ft.DropdownOption(text="SMS",leading_icon=ft.Icons.MESSAGE_ROUNDED),
        ft.DropdownOption(text="Event",leading_icon=ft.Icons.STAR_BORDER_ROUNDED),
    ])

    #URL
    url_protocol_dropdown = ft.Dropdown(border_radius=50,fill_color=ft.Colors.SURFACE_CONTAINER_LOW,filled=True,value="https://",border_width=0,options=[
        ft.DropdownOption(text="https://"),
        ft.DropdownOption(text="http://"),
        ])

    #WIFI
    wifi_name= ft.TextField(
        expand=True,
        border_width=0,
        label="Enter network name",
        on_change=lambda e: prop_changed()
    )
    wifi_protocol_dropdown = ft.Dropdown(border_radius=50,fill_color=ft.Colors.SURFACE_CONTAINER_LOW,filled=True,value="WPA2",border_width=0,on_select=lambda e: wifi_protocol_changed(e),options=[
        ft.DropdownOption(text="WPA2"),
        ft.DropdownOption(text="WPA"),
        ft.DropdownOption(text="WEP"),
        ft.DropdownOption(text="No password"),
    ])
    def wifi_protocol_changed(e):
        selected = e.control.value 
        if selected == "No password":
            wifi_password_setting.visible = False
        else:
            wifi_password_setting.visible = True
        prop_changed()
    wifi_password= ft.TextField(
        expand=True,
        border_width=0,
        label="Enter network password",
        on_change=lambda e: prop_changed()
    )
    wifi_password_setting= ft.Column(visible=True,controls=[
        ft.Divider(color=ft.Colors.GREY),
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[
            ft.Icon(icon=ft.Icons.PASSWORD_ROUNDED),
            ft.Text(value=("WIFI password"), size=20),
        ]),
        ft.Container(border_radius=10,bgcolor=ft.Colors.SURFACE_CONTAINER,content=wifi_password),
    ])
    wifi_area = ft.Column(visible=False,controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[
            ft.Icon(icon=ft.Icons.TEXT_FIELDS_ROUNDED),
            ft.Text(value=("Network name"), size=20),
        ]),
        ft.Container(border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            content=wifi_name
        ),
        ft.Divider(color=ft.Colors.GREY),
        ft.Container(
            content=ft.Row(controls=[
                ft.Icon(icon=ft.Icons.INFO_OUTLINE_ROUNDED,color=ft.    Colors.WHITE),
                ft.Container(expand=True,content=ft.Text(
                    value="If your network has no password, select it here!",
                    size=16,
                    color=ft.Colors.WHITE
                )),
                ],
            ),
            padding=15,
            bgcolor=ft.Colors.INVERSE_PRIMARY,border_radius=30,
            margin=ft.Margin.only(left=0, right=0, top=5, bottom=5,)
        ),
        ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
            ft.Row(controls=[
                ft.Icon(icon=ft.Icons.SHIELD),
                ft.Text(value=("WIFI security protocol"), size=20),
            ]),
            wifi_protocol_dropdown
        ]),
        wifi_password_setting
    ])

    # Email
    email_address = ft.TextField(expand=True,border_width=0,label="Enter address",hint_text="Enter address",on_change=lambda e: prop_changed())
    email_adv_checkbox = ft.Switch(value=False, on_change=lambda e: email_checkbox_changed())
    email_general_content=ft.Column(visible=False,controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[
            ft.Icon(icon=ft.Icons.MAIL_ROUNDED),
            ft.Text(value=("Address"), size=20),
        ]),
        ft.Container(border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            content=email_address
        ),
        ft.Divider(color=ft.Colors.GREY),
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[
            ft.Icon(icon=ft.Icons.TEXT_FIELDS_ROUNDED),
            ft.Text(value=("Advanced options"), size=20),
            email_adv_checkbox
        ]),
    ])
    # -> On checkbox changed
    def email_checkbox_changed():
        if email_adv_checkbox.value:
            email_adv_content.visible = True
        else:
            email_adv_content.visible = False
        prop_changed()

    email_subject = ft.TextField(expand=True, border_width=0, label="Subject", on_change=lambda e: prop_changed())
    email_body = ft.TextField(expand=True, border_width=0, label="Body", multiline=True, on_change=lambda e: prop_changed())
    email_adv_content = ft.Column(visible=False, controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.SUBJECT_ROUNDED), ft.Text(value="Subject", size=20)]),
        ft.Container(border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER, content=email_subject),
        ft.Divider(color=ft.Colors.GREY),
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.TEXT_FIELDS_ROUNDED), ft.Text(value="Body", size=20)]),
        ft.Container(border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER, content=email_body),
    ])

    # Phone
    phone_prefix = ft.TextField(
        border_width=0,
        label="",
        hint_text="",
        width=80,
        max_length=4,
        counter=ft.Container(),
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed()
    )
    phone_number = ft.TextField(
        expand=True,
        border_width=0,
        label="Enter address",
        hint_text="",
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed()
    )   
    phone_general_content=ft.Column(visible=False,controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[
            ft.Icon(icon=ft.Icons.CALL_ROUNDED),
            ft.Text(value=("Phone number"), size=20),
        ]),
        ft.Row(
            expand=True,
            controls=[
            ft.Container(
                border_radius=10,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                content=ft.Row(controls=[
                    ft.Text("+",margin=ft.Margin(left=15),size=15),
                    phone_prefix
                ])
            ),
            ft.Container(
                expand=True,
                border_radius=10,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                content=phone_number
            ),
        ])
    ]) 

    # SMS
    sms_prefix = ft.TextField(
        border_width=0,
        label="",
        hint_text="",
        width=80,
        max_length=4,
        counter=ft.Container(),
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed()
    )
    sms_number = ft.TextField(
        expand=True,
        border_width=0,
        label="Enter phone number",
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed()
    )
    sms_message = ft.TextField(expand=True, border_width=0, label="Enter message", multiline=True, on_change=lambda e: prop_changed())
    sms_general_content = ft.Column(visible=False, controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.SMS_ROUNDED), ft.Text(value="Phone number", size=20)]),
        ft.Row(controls=[
            ft.Container(
                border_radius=10,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                content=ft.Row(controls=[ft.Text("+", margin=ft.Margin(left=15), size=15), sms_prefix])
            ),
            ft.Container(border_radius=10, expand=True, bgcolor=ft.Colors.SURFACE_CONTAINER, content=sms_number),
        ]),
        ft.Divider(thickness=0.2, color=ft.Colors.GREY_400),
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.MESSAGE_ROUNDED), ft.Text(value="Message", size=20)]),
        ft.Container(border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER, content=sms_message),
    ])

    # Location
    location_lat = ft.TextField(expand=True, border_width=0, label="Latitude", keyboard_type=ft.KeyboardType.NUMBER, on_change=lambda e: prop_changed())
    location_lng = ft.TextField(expand=True, border_width=0, label="Longitude", keyboard_type=ft.KeyboardType.NUMBER, on_change=lambda e: prop_changed())

    location_general_content = ft.Column(visible=False, controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.PIN_DROP_ROUNDED), ft.Text(value="Coordinates", size=20)]),
        ft.Row(controls=[
            ft.Container(border_radius=10, expand=True, bgcolor=ft.Colors.SURFACE_CONTAINER, content=location_lat),
            ft.Container(border_radius=10, expand=True, bgcolor=ft.Colors.SURFACE_CONTAINER, content=location_lng),
        ]),
    ])

    # Event (vCalendar/iCal)
    event_title = ft.TextField(expand=True, border_width=0, label="Event title", on_change=lambda e: prop_changed())
    event_location = ft.TextField(expand=True, border_width=0, label="Location", on_change=lambda e: prop_changed())
    date_picker = ft.DateRangePicker(open=False, on_change=lambda e: prop_changed())
    start_time_picker = ft.TimePicker(open=False, on_change=lambda e: prop_changed())
    end_time_picker = ft.TimePicker(open=False, on_change=lambda e: prop_changed())
    page.overlay.append(date_picker)
    page.overlay.append(start_time_picker)
    page.overlay.append(end_time_picker)
    def open_date_picker(e):
        date_picker.open = True
        page.update()
    def open_start_time(e):
        start_time_picker.open = True
        page.update()
    def open_end_time(e):
        end_time_picker.open = True
        page.update()
    date_picker_button = ft.Button(content="Date period",icon=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda e: open_date_picker(e), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor={"": ft.Colors.SURFACE_CONTAINER}), tooltip="Pick date range")
    start_time_picker_button = ft.Button(content="Start time",icon=ft.Icons.ACCESS_TIME_ROUNDED, on_click=lambda e: open_start_time(e), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor={"": ft.Colors.SURFACE_CONTAINER}), tooltip="Pick start time")
    end_time_picker_button = ft.Button(content="End time",icon=ft.Icons.ACCESS_TIME_ROUNDED, on_click=lambda e: open_end_time(e), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor={"": ft.Colors.SURFACE_CONTAINER}), tooltip="Pick end time")
    event_general_content = ft.Column(visible=False, controls=[
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.STAR_BORDER_ROUNDED), ft.Text(value="Event title", size=20)]),
        ft.Container(border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER, content=event_title),
        ft.Divider(thickness=0.2, color=ft.Colors.GREY_400),
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.PIN_DROP_ROUNDED), ft.Text(value="Location", size=20)]),
        ft.Container(border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER, content=event_location),
        ft.Divider(thickness=0.2, color=ft.Colors.GREY_400),
        ft.Row(alignment=ft.MainAxisAlignment.START,controls=[ft.Icon(icon=ft.Icons.ACCESS_TIME_ROUNDED), ft.Text(value="Date and time", size=20)]),
        ft.Container(
            content=ft.Row(controls=[
                ft.Icon(icon=ft.Icons.INFO_OUTLINE_ROUNDED,color=ft.Colors.WHITE),
                ft.Container(expand=True,content=ft.Text(
                    value="Please change all fields below here!",
                    size=16,
                    color=ft.Colors.WHITE
                )),
                ],
            ),
            padding=15,
            bgcolor=ft.Colors.INVERSE_PRIMARY,border_radius=30,
            margin=ft.Margin.only(left=0, right=0, top=5, bottom=5,)
        ),
        ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
            date_picker_button,
            start_time_picker_button,
            end_time_picker_button,
        ]),
    ])
    qr_url_input_field = ft.TextField(expand=True,border_width=0,label="Enter URL or text",on_change=lambda e: prop_changed())
    error_correction_dropdown = ft.Dropdown(border_radius=50,fill_color=ft.Colors.SURFACE_CONTAINER_LOW,filled=True,value="M (15%)",border_width=0,on_select=lambda e: prop_changed(),options=[
        ft.DropdownOption(text="L (7%)"),
        ft.DropdownOption(text="M (15%)"),
        ft.DropdownOption(text="Q (25%)"),
        ft.DropdownOption(text="H (30%)"),
        ])
    qr_color_scheme_primary = MaterialPicker(on_color_change=lambda e:prop_changed(),color="black")
    qr_color_scheme_secondary = MaterialPicker(on_color_change=lambda e:prop_changed(),color="white")
    preview_qr_area= ft.Row(controls=[], alignment=ft.MainAxisAlignment.CENTER,expand=False, tight=True)
    input_row = ft.Column(controls=[
        ft.Row(controls=[
            ft.Icon(icon=ft.Icons.SHORT_TEXT_ROUNDED),
            ft.Text(value=("Content"), size=20)
        ]),
        ft.Row(visible=True,controls=[
            url_protocol_dropdown,
            ft.Container(border_radius=10,expand=True,bgcolor=ft.Colors.SURFACE_CONTAINER,content=qr_url_input_field),
        ]),
    ])
    create_layout= ft.BottomSheet(draggable=False,use_safe_area=True,scrollable=False,fullscreen=True,open=False,on_dismiss=lambda e: clean_create_bs_up(),content=
        ft.Column(horizontal_alignment="center",scroll=ft.ScrollMode.AUTO,controls=[
            ft.Container(bgcolor=ft.Colors.INVERSE_PRIMARY,border_radius=30,expand=False,content=preview_qr_area,padding=20,margin=ft.Margin.only(top=20)),
            ft.Row(
                alignment="center",
                spacing=3,
                controls=[
                    ft.Button(
                        elevation=0,
                        icon=ft.Icons.CHECK,
                        content=ft.Text("Save QR",size=16),
                        height=50,
                        color=ft.Colors.SURFACE,
                        bgcolor=ft.Colors.PRIMARY,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=50, top_right=25,bottom_left=50,bottom_right=25)),
                        ),
                        on_click=lambda e: qr_create_triggered(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        height=50,
                        width=45,
                        alignment=ft.Alignment.CENTER_LEFT,
                        icon_color=ft.Colors.INVERSE_SURFACE,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=25, top_right=50,bottom_left=25,bottom_right=50)),
                        ),
                        on_click=lambda e: clear_dialog(),
                    ),
                ]
            ),
            ft.Divider(color=ft.Colors.GREY_400,thickness=0.1,leading_indent=20,trailing_indent=20,height=50),
            ft.ExpansionTile(
                title=ft.Row(controls=[ft.Icon(icon=ft.Icons.EDIT_ATTRIBUTES_ROUNDED),ft.Text(value="Main content", size=16)]),
                tile_padding=ft.Padding.only(left=20, right=20, top=10, bottom=10),
                controls_padding=ft.Padding.only(left=20, right=20, bottom=20),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                margin=ft.Margin.only(left=20, right=20),
                shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                expanded = True,
                controls=ft.Column(controls=[
                    ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(left=0, right=0, top=0, bottom=5)),
                    ft.Row(tight=True,col={"xs": 12, "lg": 3}, controls=[
                        ft.Icon(icon=ft.Icons.ARROW_DROP_DOWN_CIRCLE_OUTLINED),
                        ft.Text(value=("QR Type"), size=20),
                    ]),
                    ft.Container(col={"xs": 12, "lg": 2},content=qr_type_dropdown),
                    ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(left=0, right=0, top=0, bottom=5)),
                    wifi_area,
                    input_row,
                    email_general_content,
                    email_adv_content,
                    phone_general_content,
                    sms_general_content,
                    location_general_content,
                    event_general_content,
                    ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(left=0, right=0, top=0, bottom=5)),
                    ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
                        ft.Row(controls=[
                            ft.Icon(icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED),
                            ft.Text(value=("Error correction level"), size=20),
                        ]),
                        error_correction_dropdown
                    ]), 
                ])
            
            ),
            ft.ExpansionTile(
                title=ft.Row(controls=[ft.Icon(icon=ft.Icons.COLOR_LENS_ROUNDED),ft.Text(value="Customization", size=16)]),
                tile_padding=ft.Padding.only(left=20, right=20, top=10, bottom=10),
                controls_padding=ft.Padding.only(left=20, right=20, bottom=20),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                margin=ft.Margin.only(left=20, right=20),
                shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                controls=ft.Column(
                    controls=[
                        ft.Container(height=0.2, bgcolor=ft.Colors.GREY_400,margin=ft.Margin.only(left=0, right=0, top=0, bottom=5)),
                        ft.Row(controls=[ft.Icon(icon=ft.Icons.ADD_PHOTO_ALTERNATE_ROUNDED),ft.Text(value=("Logo/Branding"), size=20)]),
                        ft.Container(
                            content=ft.Row(controls=[
                                ft.Icon(icon=ft.Icons.ERROR_OUTLINE_ROUNDED,color=ft.Colors.WHITE),
                                ft.Container(expand=True,content=ft.Text(
                                    value="As logos take up a big chunk of the QR's area, scanability may be greatly reduced. Thus, error correction is overrided to level H, though no guarantees it will work first try.",
                                    size=16,
                                    color=ft.Colors.WHITE
                                )),
                                ],
                            ),
                            padding=15,
                            bgcolor=ft.Colors.RED_500,border_radius=30,
                            margin=ft.Margin.only(left=0, right=0, top=5, bottom=5,)
                        ),
                        ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
                            ft.Button(content="Pick image from folder",icon=ft.Icons.FOLDER_COPY_ROUNDED, on_click=lambda e: asyncio.ensure_future(pick_logo())),
                            ft.Button(content="Remove logo",icon=ft.Icons.DELETE_ROUNDED, on_click=lambda e: remove_logo()),
                        ]),
                        ft.Divider(thickness=0.2, color=ft.Colors.GREY_400),
                        ft.Row(controls=[ft.Icon(icon=ft.Icons.COLOR_LENS_ROUNDED),ft.Text(value=("Color scheme"), size=20)]),
                        ft.ExpansionTile(title="Primary color:",controls=qr_color_scheme_primary,bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20)),
                        ft.ExpansionTile(title="Background color:",controls=qr_color_scheme_secondary,bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20)),
                    ])
                ),
            ft.Container(height=50)
        ]),
    )
    
    def prop_changed():
        if _debounce_task["task"] is not None:
            _debounce_task["task"].cancel()
        _debounce_task["task"] = page.run_task(_debounced_update)

    async def _debounced_update():

        color_raw_1 = qr_color_scheme_primary.color  
        if color_raw_1 and color_raw_1.startswith("#") and len(color_raw_1) == 9:
            color_rgb_1 = "#" + color_raw_1[3:] 
        else:
            color_rgb_1 = color_raw_1

        color_raw_2 = qr_color_scheme_secondary.color  
        if color_raw_2 and color_raw_2.startswith("#") and len(color_raw_2) == 9:
            color_rgb_2 = "#" + color_raw_2[3:] 
        else:
            color_rgb_2 = color_raw_2

        error_correction = ERROR_CORRECTION_MAP.get(error_correction_dropdown.value, qrcode.constants.ERROR_CORRECT_M)

        if qr_type_dropdown.value == "WIFI":
            if wifi_protocol_dropdown.value != "No password":
                qr_url_input_field.value = f"WIFI:S:{wifi_name.value};T:{wifi_protocol_dropdown.value};P:{wifi_password.value};;"
            else:
                qr_url_input_field.value = f"WIFI:S:{wifi_name.value};T:nopass;;"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)
        elif qr_type_dropdown.value == "URL/Link":
                if url_protocol_dropdown.value == "https://":
                    create_val = "https://"+qr_url_input_field.value
                else:
                    create_val = "http://"+qr_url_input_field.value
                display_preview_qr(create_val, color_rgb_1, color_rgb_2, error_correction)
        elif qr_type_dropdown.value == "Email":
            if email_adv_checkbox.value:
                params = []
                if email_subject.value:
                    params.append(f"subject={urllib.parse.quote(email_subject.value)}")
                if email_body.value:
                    params.append(f"body={urllib.parse.quote(email_body.value)}")
                query = "&".join(params)
                qr_url_input_field.value = f"mailto:{email_address.value}" + (f"?{query}" if query else "")
            else:
                qr_url_input_field.value = f"mailto:{email_address.value}"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)

        elif qr_type_dropdown.value == "Phone":
            qr_url_input_field.value = f"tel:+{phone_prefix.value}{phone_number.value}"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)

        elif qr_type_dropdown.value == "SMS":
            qr_url_input_field.value = f"SMSTO:{sms_number.value}:{sms_message.value}"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)

        elif qr_type_dropdown.value == "Location":
            qr_url_input_field.value = f"geo:{location_lat.value},{location_lng.value}"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)

        elif qr_type_dropdown.value == "Event":
            if date_picker.start_value and date_picker.end_value and start_time_picker.value and end_time_picker.value:
                start_date = normalize_picker_date(date_picker.start_value)
                end_date = normalize_picker_date(date_picker.end_value)
                dtstart_str = f"{start_date.strftime('%Y%m%d')}T{start_time_picker.value.strftime('%H%M%S')}"
                dtend_str = f"{end_date.strftime('%Y%m%d')}T{end_time_picker.value.strftime('%H%M%S')}"
                qr_url_input_field.value = (
                    f"BEGIN:VCALENDAR\r\n"
                    f"VERSION:2.0\r\n"
                    f"BEGIN:VEVENT\r\n"
                    f"SUMMARY:{event_title.value}\r\n"
                    f"LOCATION:{event_location.value}\r\n"
                    f"DTSTART:{dtstart_str}\r\n"
                    f"DTEND:{dtend_str}\r\n"
                    f"END:VEVENT\r\n"
                    f"END:VCALENDAR"
                )
                display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)
            else:
                qr_url_input_field.value = (
                    f"BEGIN:VCALENDAR\r\n"
                    f"VERSION:2.0\r\n"
                    f"BEGIN:VEVENT\r\n"
                    f"SUMMARY:{event_title.value}\r\n"
                    f"LOCATION:{event_location.value}\r\n"
                    f"END:VEVENT\r\n"
                    f"END:VCALENDAR"
                )
                display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)
        else:
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)
            
    def color_correction():
        color_raw_1 = qr_color_scheme_primary.color  
        if color_raw_1 and color_raw_1.startswith("#") and len(color_raw_1) == 9:
            color_rgb_1 = "#" + color_raw_1[3:] 
        else:
            color_rgb_1 = color_raw_1

        color_raw_2 = qr_color_scheme_secondary.color  
        if color_raw_2 and color_raw_2.startswith("#") and len(color_raw_2) == 9:
            color_rgb_2 = "#" + color_raw_2[3:] 
        else:
            color_rgb_2 = color_raw_2
            return color_rgb_1, color_rgb_2

    def type_trigger(e):
        selected = e.control.value 
        qr_url_input_field.value=""
        #Hide everything
        for area in [
            wifi_area, input_row, url_protocol_dropdown, email_general_content, email_adv_content,
            phone_general_content, sms_general_content, location_general_content,
            event_general_content, date_picker_button]:            
            area.visible = False
        #Empty everything
        for field in [
            wifi_name, wifi_password, email_address, email_subject, email_body,
            phone_prefix, phone_number, sms_prefix, sms_number, sms_message,
            location_lat, location_lng, event_title, event_location, start_time_picker, end_time_picker]:
        
            field.value = ""    
        if selected == "WIFI":
            wifi_area.visible=True
        elif selected == "URL/Link":
            input_row.visible=True 
            url_protocol_dropdown.visible = True
            qr_url_input_field.hint_text = "Enter URL here"
            qr_url_input_field.label = "Enter URL"
        elif selected == "Text":
            input_row.visible=True 
            qr_url_input_field.hint_text = "Enter text here"
            qr_url_input_field.label = "Enter text"
        elif selected == "Email":
            email_general_content.visible=True 
        elif selected == "Phone":
            phone_general_content.visible=True 
        elif selected == "SMS":
            sms_general_content.visible=True
        elif selected == "Location":
            location_general_content.visible=True
        elif selected == "Event":
            event_general_content.visible=True
            date_picker_button.visible = True
        prop_changed()
        page.update()

    all_view=ft.Column(scroll=ft.ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    regular_view=ft.Column(scroll=ft.ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    pinned_view =ft.Column(scroll=ft.ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])

    #layout_mode_buttongroup= ft.Row(
    #    spacing=3,
    #    controls=[
    #        ft.Button(
    #            elevation=0,
    #            icon=ft.Icons.CLEAR_ALL_ROUNDED,
    #            content=ft.Text("Rows",font_family="MaterialRoundedLight",size=14),
    #            height=40,
    #            color=ft.Colors.INVERSE_SURFACE,
    #            bgcolor=ft.Colors.SECONDARY_CONTAINER,
    #            style=ft.ButtonStyle(
    #                shape=ft.StadiumBorder(),
    #            ),
    #            on_click=lambda e: on_buttongroup_change(e)
    #        ),
    #        ft.Button(
    #            elevation=0,
    #            icon=ft.Icons.GRID_VIEW_ROUNDED,
    #            content=ft.Text("Grid",font_family="MaterialRoundedLight",size=14),
    #            height=40,
    #            color=ft.Colors.INVERSE_SURFACE,
    #            bgcolor=ft.Colors.SURFACE_CONTAINER,
    #            style=ft.ButtonStyle(
    #                shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=25, top_right=50,bottom_left=25,bottom_right=50)),
    #            ),
    #            on_click=lambda e: on_buttongroup_change(e)
    #        ),
    #    ]
    #)

    pin_filter_buttongroup= ft.Row(
        spacing=3,
        controls=[
            ft.Button(
                elevation=0,
                icon=ft.Icons.CLEAR_ALL_ROUNDED,
                content=ft.Text("All",font_family="MaterialRoundedLight",size=14),
                height=40,
                color=ft.Colors.INVERSE_SURFACE,
                bgcolor=ft.Colors.SECONDARY_CONTAINER,
                style=ft.ButtonStyle(
                    shape=ft.StadiumBorder(),
                ),
                on_click=lambda e: on_buttongroup_change(e)
            ),
            ft.Button(
                elevation=0,
                icon=ft.Icons.PUSH_PIN_ROUNDED,
                content=ft.Text("Pinned",font_family="MaterialRoundedLight",size=14),
                height=40,
                color=ft.Colors.INVERSE_SURFACE,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=lambda e: on_buttongroup_change(e)
            ),
            ft.Button(
                elevation=0,
                icon=ft.Icons.PUSH_PIN_OUTLINED,
                content=ft.Text("Unpinned",font_family="MaterialRoundedLight",size=14),
                height=40,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                color=ft.Colors.INVERSE_SURFACE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius = ft.BorderRadius.only(top_left=25, top_right=50,bottom_left=25,bottom_right=50)),
                ),
                on_click=lambda e: on_buttongroup_change(e)
            ),
        ]
    )

    order_toggle_button = ft.IconButton(
        icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,
        #on_click=lambda e: swap_views(),
        style=ft.ButtonStyle(shape=ft.CircleBorder(),
        padding=10,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        icon_color=ft.Colors.INVERSE_SURFACE,icon_size=20),
    )
    
    overview = ft.Column(expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[
        #Container(content=Image(os.path.join(ASSET_DIR,"QuickeR_horizontal_logo.png")),height=150,padding=0, bgcolor=get_container_color_by_mode(), border_radius=30),
        ft.Row(
            height=60,
            spacing=5,
            margin=ft.Margin.only(left=5, right=5, top=0, bottom=15),
            controls=[
                ft.Text(value="QuickeR",
                    size=30,font_family="MaterialRoundedBold",
                    align=ft.Alignment.CENTER,
                    color=ft.Colors.INVERSE_SURFACE,
                    style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                ),
                ft.Container(border_radius=10,
                    bgcolor=ft.Colors.TERTIARY_CONTAINER,
                    content=ft.Text(
                        value="App", 
                        size=13,
                        font_family="MaterialRoundedBold", 
                        color=ft.Colors.INVERSE_SURFACE, 
                        style=ft.TextStyle(weight=ft.FontWeight.BOLD)
                    ),
                    margin=ft.Margin.only(left=5),border=ft.Border.all(width=3,color=ft.Colors.TERTIARY),padding=7),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.COFFEE_ROUNDED,
                    #alignment=ft.MainAxisAlignment.END,
                    #on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK")),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12),
                    padding=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    icon_color=ft.Colors.YELLOW_500,icon_size=20)
                ),
                ft.IconButton(
                    icon=ft.Image(
                        os.path.join(ASSET_DIR + "/github-white-icon.webp"),
                        color=ft.Colors.INVERSE_SURFACE,width=20,height=20
                    ),
                    #alignment=ft.MainAxisAlignment.END,
                    on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK")),
                    style=ft.ButtonStyle(shape=ft.CircleBorder(),
                    padding=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    icon_color=ft.Colors.WHITE,icon_size=20)
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    #alignment=ft.MainAxisAlignment.END,
                    on_click=lambda e: swap_views(),
                    style=ft.ButtonStyle(shape=ft.CircleBorder(),
                    padding=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    icon_color=ft.Colors.INVERSE_SURFACE,icon_size=20),
                ),
            ]
        ),
        ft.Row(
            margin=ft.Margin.only(left=10, right=0, top=0, bottom=0),
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                order_toggle_button,
                ft.Container(height=30,width=2, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
                #layout_mode_buttongroup,
                #ft.Container(height=30,width=2, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
                pin_filter_buttongroup,
            ]
        ),
        
        #Divider(color="grey",thickness=0.1),
        all_view,    
    ])

    #Settings page
    
    def swap_views():
        if overview in view.controls:
            view.controls.clear()
            view.controls.append(settings_view)
        else:
            view.controls.clear()
            view.controls.append(overview)

    settings_view = ft.Column(
        expand=True,
        alignment=ft.Alignment.CENTER,
        #horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Row(
                height=60,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        #alignment=ft.MainAxisAlignment.END,
                        on_click=lambda e: swap_views(),
                        style=ft.ButtonStyle(shape=ft.CircleBorder(),
                        padding=10,
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        icon_color=ft.Colors.INVERSE_SURFACE,icon_size=20),
                        margin=ft.Margin.only(left=10, right=0, top=0, bottom=0),
                    ),
                ]
            ),
            ft.Container(
                padding=20,
                bgcolor=ft.Colors.SECONDARY_CONTAINER,
                #alignment="center",
                #width=600 or None,
                border_radius=30,
                margin=ft.Margin.only(left=20, right=20, bottom=5),
                content=ft.Column(controls=[
                    ft.Row(alignment="center",controls=[
                        ft.Text(value="QuickeR", size=40,font_family="MaterialRoundedBold", align=ft.Alignment.CENTER, color=ft.Colors.INVERSE_SURFACE, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                        ft.Container(border_radius=10,bgcolor=ft.Colors.TERTIARY_CONTAINER,content=ft.Text(value="App", size=15,font_family="MaterialRoundedBold", color=ft.Colors.INVERSE_SURFACE, style=ft.TextStyle(weight=ft.FontWeight.BOLD)),margin=ft.Margin.only(left=5),border=ft.Border.all(width=3,color=ft.Colors.TERTIARY),padding=10)
                    ]),
                    ft.Text(value="Quick | Simple | Private | Open Source", size=15, align=ft.Alignment.CENTER, color=ft.Colors.GREY_400, style=ft.TextStyle(weight=ft.FontWeight.W_200))
                ]),
            ),
            ft.ExpansionTile(
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                margin=ft.Margin.only(left=20, right=20, bottom=5),
                shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                collapsed_shape=ft.RoundedRectangleBorder(side=ft.BorderSide(width=0), radius=20),
                title=ft.Text(value="Support QuickeR", size=15, color=ft.Colors.INVERSE_SURFACE,style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                controls=[ft.Column(controls=[
                    ft.Container(
                        margin=ft.Margin.only(left=10,right=10),
                        border_radius=20,
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        padding=20,
                        content=ft.Column(
                            controls=[
                                ft.Row(controls=[
                                    ft.Icon(icon=ft.Icons.PAYMENT_ROUNDED,color=ft.Colors.INVERSE_SURFACE),
                                    ft.Text(value="Donate", size=25, color=ft.Colors.INVERSE_SURFACE,style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                                    ft.Container(content=ft.Text(value="ONE TIME", size=10, color=ft.Colors.INVERSE_SURFACE,style=ft.TextStyle(weight=ft.FontWeight.BOLD)),margin=ft.Margin.only(left=5),bgcolor=ft.Colors.TERTIARY_CONTAINER,border=ft.Border.all(width=3, color=ft.Colors.TERTIARY), border_radius=10, padding=5),
                                ]),
                                ft.Text(value="If you want to support the project, you can do so by donating via Buy Me a Coffee or GitHub Sponsors.", size=15, color=ft.Colors.INVERSE_SURFACE),
                                ft.Row(alignment=ft.MainAxisAlignment.CENTER,controls=ft.Row(wrap=True,controls=[
                                    ft.Button(
                                        margin=ft.Margin.only(top=10),
                                        content=ft.Text(value="Buy Me a Coffee"),
                                        icon=ft.Icons.COFFEE_ROUNDED, 
                                        #on_click=lambda e: asyncio.ensure_future(open_url("https://www.buymeacoffee.com/ChoiceZero","BLANK")),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=12),
                                            padding=10,
                                            bgcolor=ft.Colors.PRIMARY,
                                            color=ft.Colors.SURFACE,
                                            overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                                        ),
                                    ),
                                    ft.Button(
                                        margin=ft.Margin.only(top=10),
                                        content=ft.Text(value="GitHub Sponsors"),
                                        icon=ft.CupertinoIcons.HEART_FILL, 
                                        #on_click=lambda e: asyncio.ensure_future(open_url("https://www.buymeacoffee.com/ChoiceZero","BLANK")),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=12),
                                            padding=10,
                                            bgcolor=ft.Colors.PRIMARY,
                                            color=ft.Colors.SURFACE,
                                            overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                                        ),
                                    )
                                ]))
                            ]
                        )
                    ),
                    ft.Container(
                        border_radius=20,
                        margin=ft.Margin.only(left=10,right=10),
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        padding=20,
                        content=ft.Column(
                            controls=[
                                ft.Row(controls=[
                                    ft.Icon(icon=ft.Icons.CODE_ROUNDED,color=ft.Colors.INVERSE_SURFACE),
                                    ft.Text(value="Contribute", size=25, color=ft.Colors.INVERSE_SURFACE,style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                                ]),
                                ft.Text(value="Contribute code or report bugs in order to improve the project as a community effort.", size=15, color=ft.Colors.INVERSE_SURFACE),
                                ft.Row(alignment=ft.MainAxisAlignment.CENTER,controls=[
                                    ft.Button(
                                        align=ft.Alignment.CENTER,
                                        margin=ft.Margin.only(top=10),
                                        content=ft.Text(value="QuickeR-Web"),
                                        icon=ft.Image(
                                            os.path.join(ASSET_DIR + "/github-white-icon.webp"),
                                            color=ft.Colors.SURFACE,width=20,height=20
                                        ), 
                                        on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK")),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=12),
                                            padding=10,
                                            bgcolor=ft.Colors.PRIMARY,
                                            color=ft.Colors.SURFACE,
                                            overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                                        ),
                                    ),
                                    ft.Button(
                                        content=ft.Text(value="Report a bug"),
                                        icon=ft.Icons.BUG_REPORT_ROUNDED,
                                        margin=ft.Margin.only(top=10),
                                        on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR/issues","BLANK")),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=12),
                                            padding=10,
                                            bgcolor=ft.Colors.PRIMARY,
                                            color=ft.Colors.SURFACE,
                                            overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                                        ),
                                    )
                                ])   
                            ]
                        )
                    ),
                    ft.Container(
                        border_radius=20,
                        margin=ft.Margin.only(left=10,right=10,bottom=10),
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        padding=20,
                        content=ft.Column(
                            controls=[
                                ft.Row(controls=[
                                    ft.Icon(icon=ft.Icons.SHARE_ROUNDED,color=ft.Colors.INVERSE_SURFACE),
                                    ft.Text(value="Share the app", size=25, color=ft.Colors.INVERSE_SURFACE,style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                                ]),
                                ft.Text(value="Help spread the word about the app and recommend it to others. The more users, the more interest in the project!", size=15, color=ft.Colors.INVERSE_SURFACE),
                                ft.Button(
                                    align=ft.Alignment.CENTER,
                                    content=ft.Text(value="Copy link to clipboard"),
                                    icon=ft.Icons.COPY_ALL_ROUNDED,
                                    margin=ft.Margin.only(top=10),
                                    on_click=lambda e: asyncio.ensure_future(copy_text_to_clipboard("https://choicezero.github.io/QuickeR-Web/")),
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                        padding=10,
                                        bgcolor=ft.Colors.PRIMARY,
                                        color=ft.Colors.SURFACE,
                                        overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                                    ),
                                )
                            ]
                        )
                    ),
                ])]
            ),
            ft.Row(alignment="center",controls=ft.Text(value="Customization", size=18, color=ft.Colors.PRIMARY)),
            ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=30,
                margin=ft.Margin.only(left=20, right=20, top=5, bottom=5),
                padding=20,
                content=ft.Column(controls=[
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.WB_SUNNY_ROUNDED, size=40, color=ft.Colors.PRIMARY),
                        ft.Column(spacing=-3, controls=[
                            ft.Text(value=("Appearance"), size=20, color=ft.Colors.PRIMARY),
                            ft.Text(value=("Select the theme of the app."), size=13)
                        ])
                    ]),
                    appearance_setting,
                    ft.Divider(color=ft.Colors.SURFACE,thickness=3),
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.COLOR_LENS_ROUNDED, size=40, color=ft.Colors.PRIMARY),
                        ft.Column(spacing=-3, controls=[
                            ft.Text(value=("Color theme"), size=20, color=ft.Colors.PRIMARY),
                            ft.Text(value=("Select the color mode of the app."), size=13)
                        ])
                    ]),
                    themes_row,
                ])),
                
            ft.Row(alignment="center",controls=ft.Text(value="About", size=18, color=ft.Colors.PRIMARY)),
            ft.Container(
                width=page.width,
                border_radius=20,
                padding=20,
                margin=ft.Margin.only(left=20, right=20, bottom=5),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                content=ft.Column(controls=[
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.NUMBERS_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(value=("Version"), size=15, color=ft.Colors.GREY_400),
                        ft.Container(expand=True),
                        ft.Text(value=APP_VERSION, size=15, color=ft.Colors.PRIMARY)
                    ]),
                    ft.Divider(color=ft.Colors.SURFACE_CONTAINER_LOW,thickness=2),
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.LIBRARY_BOOKS_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(value=("License"), size=15, color=ft.Colors.GREY_400),
                        ft.Container(expand=True),
                        ft.Text(value="MIT License", size=15, color=ft.Colors.PRIMARY)
                    ]), 
                    ft.Divider(color=ft.Colors.SURFACE_CONTAINER_LOW,thickness=2),
                    ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
                        ft.Row(controls=[
                            ft.Icon(icon=ft.Icons.PERSON_2_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                            ft.Text(value=("Developed by"), size=15, color=ft.Colors.GREY_400),
                        ]),
                        ft.Text(value="Unax Martinez Llorente (aka ChoiceZero).", size=15, color=ft.Colors.INVERSE_SURFACE)
                    ]),
                ])
            ),
            ft.Text(value="Links", size=17, color=ft.Colors.INVERSE_SURFACE, margin=ft.Margin.only(left=20, right=20, top=15)),
            ft.Container(
                width=page.width,
                border_radius=20,
                padding=20,
                margin=ft.Margin.only(left=20, right=20, bottom=5),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                content=ft.Column(controls=[
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.INSERT_LINK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(value=("Repository"), size=15, color=ft.Colors.GREY_400),
                        ft.Container(expand=True),
                        ft.Button(
                            content=ft.Text(value="QuickeR"),
                            icon=ft.Image(
                                os.path.join(ASSET_DIR + "/github-white-icon.webp"),
                                color=ft.Colors.SURFACE,width=20,height=20
                            ),
                            on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK")),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                padding=10,
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.SURFACE,
                                overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                            ),
                        )
                    ]),
                    ft.Divider(color=ft.Colors.SURFACE_CONTAINER_LOW, thickness=2),
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.INSERT_LINK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(value=("Bugs"), size=15, color=ft.Colors.GREY_400),
                        ft.Container(expand=True),
                        ft.Button(
                            content=ft.Text(value="Report a bug"),
                            icon=ft.Icons.BUG_REPORT_ROUNDED,
                            on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK")),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                padding=10,
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.SURFACE,
                                overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                            ),
                        )
                    ]),
                    ft.Divider(color=ft.Colors.SURFACE_CONTAINER_LOW, thickness=2),
                    ft.Row(controls=[
                        ft.Icon(icon=ft.Icons.INSERT_LINK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(value=("Release notes"), size=15, color=ft.Colors.GREY_400),
                        ft.Container(expand=True),
                        ft.Button(
                            content=ft.Text(value="Release notes"),
                            icon=ft.Icons.NEW_RELEASES_ROUNDED,
                            on_click=lambda e: asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR/releases","BLANK")),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                padding=10,
                                bgcolor=ft.Colors.PRIMARY,
                                color=ft.Colors.SURFACE,
                                overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                            ),
                        )
                    ]),
                ])
            ),
            ft.Text(value="Privacy", size=17, color=ft.Colors.INVERSE_SURFACE, margin=ft.Margin.only(left=20, right=20, top=15)),
            ft.Container(
                width=page.width,
                border_radius=20,
                padding=20,
                margin=ft.Margin.only(left=20, right=20, bottom=5),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                content=ft.Column(controls=[
                    ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
                        ft.Row(controls=[
                            ft.Icon(icon=ft.Icons.DISABLED_VISIBLE_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                            ft.Text(value=("Private"), size=15, color=ft.Colors.GREY_400),
                        ]),
                        ft.Text(value="No telemetry or analytics are used.", size=15, color=ft.Colors.INVERSE_SURFACE)  
                    ]),
                    ft.Divider(color=ft.Colors.SURFACE_CONTAINER_LOW,thickness=2),
                    ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
                        ft.Row(controls=[
                            ft.Icon(icon=ft.Icons.EDIT_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                            ft.Text(value=("Open source"), size=15, color=ft.Colors.GREY_400),
                        ]),
                        ft.Text(value="Fully open source and auditable.", size=15, color=ft.Colors.INVERSE_SURFACE)  
                    ]),
                    ft.Divider(color=ft.Colors.SURFACE_CONTAINER_LOW,thickness=2),
                    ft.Row(wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN,controls=[
                        ft.Row(controls=[
                            ft.Icon(icon=ft.Icons.VERIFIED_USER_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                            ft.Text(value=("Personal"), size=15, color=ft.Colors.GREY_400),
                        ]),
                        ft.Text(value="No private data is collected or stored.", size=15, color=ft.Colors.INVERSE_SURFACE)
                    ]),
                ])
            ),
            ft.Row(alignment="center",controls=[ft.Text(value="Danger zone", size=17, color=ft.Colors.RED_400, margin=ft.Margin.only(left=20, right=20, top=15))]),
            ft.Container(
                padding=20,
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
                border_radius=30,
                width=600,
                alignment=ft.Alignment.CENTER,
                align=ft.Alignment.CENTER,
                margin=ft.Margin.only(left=20, right=20, top=15, bottom=5),
                border=ft.Border.all(width=2,color=ft.Colors.RED_400),
                content=ft.Column(
                    controls=[
                        ft.Button(
                            content=ft.Text(value="Delete all data",color=ft.Colors.SURFACE,size=16),
                            icon_color=ft.Colors.SURFACE,
                            icon=ft.Icons.DELETE_ROUNDED,
                            on_click=lambda e: clear_app_data(),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                padding=20,
                                icon_size=20,
                                bgcolor=ft.Colors.RED_100,
                                color=ft.Colors.SURFACE,
                                overlay_color=ft.Colors.ON_PRIMARY_CONTAINER
                            ),
                        ),
                    ]
                )
            ),
            ft.Row(alignment=ft.MainAxisAlignment.CENTER,controls=[ft.Text(value="Made with ❤️ in Spain.", size=15, color=ft.Colors.GREY_400)]),
            ft.Container(height=50),    
             
        ]
    )

    create_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD_ROUNDED,
        on_click=lambda e: qr_creator_open(),
    )

    page.floating_action_button = create_button

    view = ft.Column(width=100,controls=[overview],horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    safearea= ft.SafeArea(content=view,expand=True)
    page.overlay.append(create_layout)

    root_row = ft.Row(controls=[safearea], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    page.add(root_row)

    load_qrs()
    theme_loader()
    appearance_loader()
    display_preview_qr("","black","white",ERROR_CORRECTION_MAP["M (15%)"])

ft.run(main)