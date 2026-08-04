from importlib.resources import files
import os
import qrcode
import cv2 
import time 
import flet as ft
from flet import Tooltip,SnackBar,ExpansionTile,Dropdown,DropdownOption,SegmentedButton,Segment,ThemeMode,Theme,Page,RoundedRectangleBorder,ButtonStyle,Divider,Stack,BottomSheet,Border,Margin,Icon,Icons, IconButton, NavigationBarDestination, Checkbox, VerticalDivider, Container, Image, TextField, Text, Row, Column, Colors, ScrollMode, AlertDialog, FilePicker, TextButton, Alignment, Button, IconButton
from flet_color_pickers import MaterialPicker
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
import numpy as np
from itertools import groupby

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
QR_DIR = os.path.join(BASE_DIR, "qr_codes")
PINNED_DIR = os.path.join(BASE_DIR, "pinned_qr_codes")

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(PINNED_DIR, exist_ok=True)

ERROR_CORRECTION_MAP = {
    "L (7%)": qrcode.constants.ERROR_CORRECT_L,
    "M (15%)": qrcode.constants.ERROR_CORRECT_M,
    "Q (25%)": qrcode.constants.ERROR_CORRECT_Q,
    "H (30%)": qrcode.constants.ERROR_CORRECT_H,
}

os.path.join(ASSET_DIR,"github-white-icon.webp")

def get_github_icon_by_mode():
    with open(os.path.join(BASE_DIR, "settings.json"), "r", encoding="utf-8") as file:
        data = json.load(file)

    if data["Appearance"] == "System":
        brightness = platform.system()
        if brightness == "Dark":
            return "white"
        else:
            return "black"
    elif data["Appearance"] == "Dark":
        return "white"
    elif data["Appearance"] == "Light":
        return "black"

def get_container_color_by_mode():
    with open(os.path.join(BASE_DIR, "settings.json"), "r", encoding="utf-8") as file:
        data = json.load(file)

    if data["Appearance"] == "System":
        brightness = platform.system()
        if brightness == "Dark":
            return Colors.GREY_800
        else:
            return Colors.GREY_300
    elif data["Appearance"] == "Dark":
        return Colors.GREY_800
    elif data["Appearance"] == "Light":
        return Colors.GREY_300
    
def get_option_color_by_mode():
    with open(os.path.join(BASE_DIR, "settings.json"), "r", encoding="utf-8") as file:
        data = json.load(file)

    if data["Appearance"] == "System":
        brightness = platform.system()
        if brightness == "Dark":
            return Colors.GREY_700
        else:
            return Colors.GREY_400
    elif data["Appearance"] == "Dark":
        return Colors.GREY_700
    elif data["Appearance"] == "Light":
        return Colors.GREY_400
    
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

def add_logo_aligned_to_grid(pil_img, logo_path, qr_obj, max_module_ratio=0.25):
    box_size = qr_obj.box_size
    border = qr_obj.border
    modules_count = len(qr_obj.get_matrix())  # número de módulos por lado (sin contar borde)

    # cuántos módulos puede cubrir el logo como máximo, sin pasarse del ratio permitido
    max_logo_modules = int(modules_count * max_module_ratio)
    # forzar número impar para que quede perfectamente centrado en un módulo central
    if max_logo_modules % 2 == 0:
        max_logo_modules -= 1
    max_logo_modules = max(max_logo_modules, 1)

    logo_size_px = max_logo_modules * box_size

    logo = PIL.Image.open(logo_path).convert("RGBA")
    logo = logo.resize((logo_size_px, logo_size_px))

    qr_w, qr_h = pil_img.size

    # posición alineada a la cuadrícula: calculamos en unidades de módulo, no en píxeles sueltos
    total_modules_with_border = modules_count + border * 2
    center_module = total_modules_with_border // 2
    start_module = center_module - max_logo_modules // 2

    pos_x = start_module * box_size
    pos_y = start_module * box_size

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

class LogoPicker:
    def __init__(self, page):
        self.page = page
        self.file_picker = FilePicker()
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
        self.divider_rect = VerticalDivider(color=Colors.BLACK, width=1, thickness=30)
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
        if self.initial_input == "":
            input_dialog = AlertDialog(
                title=Text("Enter a valid URL"),
                alignment=Alignment.CENTER,
                content=Text("Please enter a valid URL (do not leave blank)."),
                actions=[TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                open=True)
            self.page.show_dialog(input_dialog)
        else:
            self.qr_id = self.id_assigner()
            self.date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self.url = self.initial_input
            self.img= image
            self.img.save(os.path.join(QR_DIR, f"{self.qr_id}.png"))  
            self.display_qr(False)

    def id_assigner(self):
        initial_time = time.localtime()
        output_time = str(initial_time.tm_year)+str(initial_time.tm_mon)+str(initial_time.tm_mday)+str(initial_time.tm_hour)+str(initial_time.tm_min)+str(initial_time.tm_sec)
        return output_time
    
    def display_qr(self,pinned, prepend=True):
        if pinned:
            qr = Image(src=os.path.join(PINNED_DIR, f"{self.qr_id}.png"), border_radius=10, width=50, height=50)
        else:
            qr = Image(src=os.path.join(QR_DIR, f"{self.qr_id}.png"), border_radius=10, width=50, height=50)
        self.qr_size= self.get_qr_size(self.qr_id)
        self.qr_date = self.get_qr_date(self.qr_id)
        self.qr_row = Row(controls=[
            qr,
            Column(spacing=1,alignment=Alignment.TOP_CENTER,controls=[
                Text(value=str(self.url), size=18,font_family="Header"),
                #Text(color=Colors.GREY_400,value="Date: "+str(self.date)),
                Row(controls=[
                    Container(padding=5,bgcolor=Colors.TERTIARY_CONTAINER,border_radius=5, border=Border.all(width=1, color=Colors.TERTIARY_FIXED_DIM),content=Text(value=str(self.qr_size), size=10)),
                    Text(italic=True,color=Colors.GREY_400,value=self.qr_id+".png"),
                ]),      
        ])])
        
        self.main_container = Container(on_click=lambda e:self.display_details_bottomsheet(),on_hover=lambda e: self.on_hover(e),content=self.qr_row,padding=10, border_radius=20,bgcolor=Colors.SECONDARY_CONTAINER)
        
        if prepend:
            self.all_view.controls.insert(0, self.main_container)
            if pinned:
                self.qr_row.controls.append(Container(expand=True))
                self.qr_row.controls.append(Icon(icon=Icons.PUSH_PIN_ROUNDED))
                self.pinned_view.controls.insert(0, self.main_container)
            else:    
                self.regular_view.controls.insert(0, self.main_container)
        else:
            self.all_view.controls.append(self.main_container)
            if pinned:
                self.qr_row.controls.append(Container(expand=True))
                self.qr_row.controls.append(Icon(icon=Icons.PUSH_PIN_ROUNDED))
                self.pinned_view.controls.append(self.main_container)
            else:    
                self.regular_view.controls.append(self.main_container)

    def display_grid_qr(self,pinned, prepend=True):
        if pinned:
            qr = Image(src=os.path.join(PINNED_DIR, f"{self.qr_id}.png"), border_radius=10, width=50, height=50)
        else:
            qr = Image(src=os.path.join(QR_DIR, f"{self.qr_id}.png"), border_radius=10, width=50, height=50)
        self.qr_size= self.get_qr_size(self.qr_id)
        self.qr_date = self.get_qr_date(self.qr_id)
        self.qr_row = Row(controls=[
            qr,
            Column(spacing=1,alignment=Alignment.TOP_CENTER,controls=[
                Text(value=str(self.url), size=18,font_family="Header"),
                #Text(color=Colors.GREY_400,value="Date: "+str(self.date)),
                Row(controls=[
                    Container(padding=5,bgcolor=Colors.TERTIARY_CONTAINER,border_radius=5, border=Border.all(width=1, color=Colors.TERTIARY_FIXED_DIM),content=Text(value=str(self.qr_size), size=10)),
                    Text(italic=True,color=Colors.GREY_400,value=self.qr_id+".png"),
                ]),      
        ])])
        
        self.main_container = Container(on_click=lambda e:self.display_details_bottomsheet(),on_hover=lambda e: self.on_hover(e),content=self.qr_row,padding=10, border_radius=20,bgcolor=Colors.SECONDARY_CONTAINER)
        
        if prepend:
            self.all_view.controls.insert(0, self.main_container)
            if pinned:
                self.pinned_view.controls.insert(0, self.main_container)
            else:    
                self.regular_view.controls.insert(0, self.main_container)
        else:
            self.all_view.controls.append(self.main_container)
            if pinned:
                self.pinned_view.controls.append(self.main_container)
            else:    
                self.regular_view.controls.append(self.main_container)
      

    def on_hover(self,e):
        if e.data == True:
            self.main_container.bgcolor=Colors.SECONDARY_FIXED_DIM
        else:
            self.main_container.bgcolor=Colors.SECONDARY_CONTAINER

    def delete_qr_action(self, e):
        delete_dialog = AlertDialog(
            title=Text("Are you sure you want to delete this QR code?"),
            alignment=Alignment.CENTER,
            content=Text("This action cannot be undone." + "\n" + "However, you can always generate a new QR code with the same URL."),
            actions=[
                Button(content="Cancel", on_click=lambda e: self.page.pop_dialog()),
                Button(icon=Icons.DELETE,bgcolor=Colors.RED_900,content="Delete", on_click=lambda e: self.delete_qr())],
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
        self.filetext=TextField(hint_text="Enter filename here",expand=True,label="Rename QR")
        download_dialog = AlertDialog(
            title=Text("Export Options"),
            on_dismiss=lambda e: self.handle_download_dialog_dismissed(),
            alignment=Alignment.CENTER,
            actions=[
                Row(expand=True,alignment="center",controls=self.filetext),
                Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_folder()),margin=Margin(bottom=5,top=10),height=80,padding=10,bgcolor=Colors.SECONDARY_CONTAINER,content=Row(alignment="center",controls=[Icon(icon=Icons.FOLDER_COPY_ROUNDED),Text(value="Select a folder (.png)")])),
                Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_gallery()),margin=Margin(bottom=5,top=5),height=80,padding=10,bgcolor=Colors.SECONDARY_CONTAINER,content=Row(alignment="center",controls=[Icon(icon=Icons.IMAGE_ROUNDED),Text(value="Add to gallery")])),
                Container(border_radius=20,margin=Margin(top=5),height=80,padding=10,bgcolor=Colors.SECONDARY_CONTAINER,content=Row(alignment="center",controls=[Icon(icon=Icons.FILE_COPY_ROUNDED),Text(value="Export as 3D model (.STL)")])),
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
            self.page.show_dialog(SnackBar(content=Text("QR file not found")))
            return
        try:
            shutil.copy(src, f"{folder_path}/{self.filetext.value}.png")
            self.page.show_dialog(SnackBar(content=Text(f"QR exported to {folder_path}")))
        except Exception as ex:
            self.page.show_dialog(SnackBar(content=Text(f"Error: {ex}")))

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
            self.page.show_dialog(SnackBar(content=Text("QR file not found")))
            return
        try:
            shutil.copy(src, f"{folder_path}/{self.filetext.value}.png")
            self.page.show_dialog(SnackBar(content=Text(f"QR exported to {folder_path}")))
        except Exception as ex:
            self.page.show_dialog(SnackBar(content=Text(f"Error: {ex}")))

    def set_filetext(self, e):
        self.filetext = str(e.control.value)
        print(self.filetext)

    def download_qr(self):
        if self.filetext == "":
            input_dialog = AlertDialog(
                title=Text("Enter a valid file name"),
                alignment=Alignment.CENTER,
                content=Text("Please enter a valid file name (do not leave blank)."),
                actions=[TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                open=True)
            self.page.show_dialog(input_dialog)
        else:
            self.page.pop_dialog()
            
            filename = self.filetext if self.filetext.endswith(".png") else f"{self.filetext}.png"
            
            downloads_path = FilePicker.get_directory_path()
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
                    success_dialog = AlertDialog(
                        title=Text("Download Successful"),
                        alignment=Alignment.CENTER,
                        content=Text(f"QR code saved to:\n{destination_path}"),
                        actions=[TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                        open=True)
                    self.page.show_dialog(success_dialog)
                else:
                    error_dialog = AlertDialog(
                        title=Text("Error Saving File"),
                        alignment=Alignment.CENTER,
                        content=Text("Destination QR code wasn't found upon final check."),
                        actions=[TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                        open=True)
                    self.page.show_dialog(error_dialog)
            except Exception as ex: 
                error_dialog = AlertDialog(
                    title=Text("Error Saving File"),
                    alignment=Alignment.CENTER,
                    content=Text(f"Error: {str(ex)}"),
                    actions=[TextButton("Got it!", on_click=lambda e: self.page.pop_dialog())],
                    open=True)
                self.page.show_dialog(error_dialog)
            self.page.update()

    def pin_triggered(self):
        #print("triggered")
        if os.path.exists(os.path.join(PINNED_DIR, f"{self.qr_id}.png")):
            self.pin_state = True
        self.pin_state = not self.pin_state
        if self.pin_state == True:
            self.pin_qr_action()
        else:
            self.unpin_qr_action()

    def pin_qr_action(self):
        self.pin_button.bgcolor = Colors.PINK_500
        self.pin_button.icon = Icons.PUSH_PIN
        shutil.move(os.path.join(QR_DIR, f"{self.qr_id}.png"), os.path.join(PINNED_DIR, f"{self.qr_id}.png"))
        self.regular_view.controls.remove(self.main_container)
        self.all_view.controls.remove(self.main_container)
        self.display_qr(True)

    def unpin_qr_action(self):
        self.pin_button.bgcolor = Colors.PURPLE_500
        self.pin_button.icon = Icons.PUSH_PIN_OUTLINED
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
        if os.path.exists(qr_path):
            qrpath = qr_path
            qr = Image(src=qr_path, border_radius=10, width=250, height=250)
            self.pin_button = IconButton(icon=Icons.PUSH_PIN_OUTLINED, on_click=self.pin_triggered, expand=True,
                style=ButtonStyle(shape=RoundedRectangleBorder(radius=12), bgcolor={"": Colors.PURPLE_500}))
        elif os.path.exists(pinned_path):
            qrpath = pinned_path
            qr = Image(src=pinned_path, border_radius=10, width=250, height=250)
            self.pin_button = IconButton(icon=Icons.PUSH_PIN, on_click=self.pin_triggered, expand=True,
                style=ButtonStyle(shape=RoundedRectangleBorder(radius=12), bgcolor={"": Colors.PINK_500}))        
        
        self.details_bs = BottomSheet(draggable=True,show_drag_handle=True,use_safe_area=True,scrollable=False,fullscreen=True,open=False,on_dismiss=lambda e: self.clean_bs_up(),content=
            Column(horizontal_alignment="center",scroll=ScrollMode.AUTO,controls=[
                Container(bgcolor=Colors.INVERSE_PRIMARY,border_radius=30,content=qr,padding=20,margin=Margin.only(left=20, right=20, bottom=5)),
                Container(bgcolor=Colors.SECONDARY_CONTAINER,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                    Row(alignment="center",controls=[
                        IconButton(
                            icon=Icons.DOWNLOAD,
                            expand=True,
                            on_click=lambda e: self.download_qr_action(),
                            style=ButtonStyle(
                                shape=RoundedRectangleBorder(radius=12),
                                bgcolor={"": Colors.BLUE_500}, 
                            )
                        ),
                        IconButton(
                            icon=Icons.SHARE,
                            expand=True,
                            on_click=lambda e: asyncio.ensure_future(self.do_share_files_from_paths()), 
                            style=ButtonStyle(
                                shape=RoundedRectangleBorder(radius=12),
                                bgcolor={"": Colors.GREEN_500}, 
                            )
                        ),
                        self.pin_button,
                        IconButton(icon=Icons.DELETE,expand=True,on_click=lambda e: self.delete_qr_action(e), style=ButtonStyle(shape=RoundedRectangleBorder(radius=12),bgcolor={"": Colors.RED_500},)),
                    ])
                ),
                Text(value="General", size=18,color=Colors.PRIMARY),
                Container(bgcolor=get_container_color_by_mode(),border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                    Column(controls=[
                        Row(controls=[Icon(icon=Icons.INSERT_LINK_ROUNDED),Column(spacing=-3,controls=[Text(value=("Url/text"), size=16),Text(value=(self.url),size=11)])]),
                        Divider(color="grey"),
                        Row(controls=[Icon(icon=Icons.CALENDAR_MONTH_ROUNDED),Column(spacing=-3,controls=[Text(value=("Creation date"), size=16),Text(value=(self.qr_date),size=11)])]),
                        Divider(color="grey"),
                        Row(controls=[Icon(icon=Icons.FOLDER_COPY_ROUNDED),Column(spacing=-3,controls=[Text(value=("Internal path"), size=16),Text(value=(qrpath),size=11)])]), 
                        Divider(color="grey"),
                        Row(controls=[Icon(icon=Icons.INSERT_DRIVE_FILE_ROUNDED),Column(spacing=-3,controls=[Text(value=("Filesize"), size=16),Text(value=(self.qr_size),size=11)]),]),
                    ])
                ),
                Text(value="Customization", size=18,color=Colors.PRIMARY),
                Container(bgcolor=get_container_color_by_mode(),border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                    Column(controls=[
                        Row(controls=[Icon(icon=Icons.COLOR_LENS_ROUNDED),Column(spacing=-3,controls=Text(value=("Colors"), size=16))]),
                        Row(controls=[Text(value=("Primary: ")),Container(expand=True),Text(value=self.fill_color or "Error")]),
                        Divider(color="grey"),
                        Row(controls=[Text(value=("Background: ")),Container(expand=True),Text(value=self.back_color or "Error")]),
                    ])
                ),
                Container(height=50)
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
            self.page.show_dialog(SnackBar(content=Text("QR file not found")))
            return

        try:
            result = await self.share.share_files(
                [ft.ShareFile.from_path(os.path.abspath(file_path))],
                text="Sharing a file from memory",
            )
            self.status.value = f"Share status: {result.status}"
        except Exception as ex:
            self.page.show_dialog(SnackBar(content=Text(f"Share not supported on this platform: {ex}")))

    #async def do_share_uri(self):
    #    result = await self.share.share_uri("https://flet.dev")
    #    self.status.value = f"Share status: {result.status}"
    #    self.result_raw.value = f"Raw: {result.raw}"
        
def main(page: Page):
    page.title = "QuickeR"
    #page.scroll = ScrollMode.ADAPTIVE
    preview_qr = ""
    last_qr_image = {"img": None}
    _debounce_task = {"task": None}
    logo_image_path = {"path": None}
    logo_picker_ref = {"instance": None}

    page.fonts = {
        "AndroidDefault": "/GoogleSansFlex(1).ttf",
        "Header":"/GoogleSansFlex(2).ttf"
    }

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
        page.theme = Theme(color_scheme_seed=getattr(Colors, color_string), font_family="Header")
        page.update()

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
                page.theme_mode = ThemeMode.DARK
            elif brightness == ft.Brightness.LIGHT:
                page.theme_mode= ThemeMode.LIGHT
        elif appearance == "Dark":
            appearance_setting.selected=["3"]
            page.theme_mode = ThemeMode.DARK
        elif appearance == "Light":
            appearance_setting.selected=["2"]
            page.theme_mode = ThemeMode.LIGHT
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
                all_view.controls.append(Text(value=date_str, size=16, color=Colors.GREY_400))
                if is_pinned:
                    pinned_view.controls.append(Text(value=date_str, size=16, color=Colors.GREY_400))
                else:
                    regular_view.controls.append(Text(value=date_str, size=16, color=Colors.GREY_400))
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
    
    def qr_create_triggered():
        #if contrast_ratio(color_rgb_1, color_rgb_2) < 4.5: 
        #    AlertDialog(
        #        title=Text("Contrast too low"),
        #        alignment=Alignment.CENTER,
        #        content=Text("The contrast between the two colors is too low. The qr may be unreadable."),
        #        actions=[TextButton("Cancel", on_click=lambda e: page.pop_dialog()),TextButton("Create", on_click=lambda e: create_qr_action())],
        #        open=True)
        #else:
        #    create_qr_action()
        create_qr_action()

    def create_qr_action():
            create_info = qr_url_input_field.value
            new_qr = QRCodes(page, create_info, all_view, regular_view,pinned_view)
            new_qr.fill_color, new_qr.back_color = qr_color_scheme_primary.color,qr_color_scheme_secondary.color
            if last_qr_image["img"]==None:
                print("image can't be Nonetype!")
            else:
                new_qr.create_qr(last_qr_image["img"])    
            qr_url_input_field.value = ""
            clean_create_bs_up()
            snack = SnackBar(
                content=Text("¡QR code generated!"),
                bgcolor=Colors.WHITE,
                duration= 4000,
                show_close_icon=True,
            )
            page.show_dialog(snack)

    def on_mode_change(e):
        segment_value = (next(iter(e.control.selected)) if e.control.selected else None)
        if segment_value == "1":
            appearance_changer(1)
        elif segment_value == "2":
            appearance_changer(2)
        elif segment_value == "3":
            appearance_changer(3)

    def on_filter_change(e):
        segment_value = (next(iter(e.control.selected)) if e.control.selected else None)
        if segment_value == "1":
            if regular_view in overview.controls:
                overview.controls.remove(regular_view)
            elif pinned_view in overview.controls:
                overview.controls.remove(pinned_view)
            overview.controls.append(all_view)
        elif segment_value == "2":
            if all_view in overview.controls:
                overview.controls.remove(all_view)
            elif pinned_view in overview.controls:
                overview.controls.remove(pinned_view)
            overview.controls.append(regular_view)
        elif segment_value == "3":
            if regular_view in overview.controls:
                overview.controls.remove(regular_view)
            elif all_view in overview.controls:
                overview.controls.remove(all_view)
            overview.controls.append(pinned_view)
        page.update()

    def on_tab_change(e):
        if e.control.selected_index == 0:
            view.controls.clear()
            view.controls.append(overview)
        elif e.control.selected_index == 1:
            view.controls.clear()
            view.controls.append(settings_view)

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

    themes_row = Container(padding=5,bgcolor=Colors.SECONDARY_CONTAINER,border=Border.all(width=1,color=Colors.PRIMARY),border_radius=30,content=Row(spacing=-10,scroll=ScrollMode.AUTO,controls=[
        IconButton(icon=Icons.CIRCLE, icon_color="blue", on_click=lambda e: theme_changer(1), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="green", on_click=lambda e: theme_changer(2), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="yellow", on_click=lambda e: theme_changer(3), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="orange", on_click=lambda e: theme_changer(4), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="red", on_click=lambda e: theme_changer(5), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="purple", on_click=lambda e: theme_changer(6), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="pink", on_click=lambda e: theme_changer(7), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="grey", on_click=lambda e: theme_changer(8), icon_size=50),
        IconButton(icon=Icons.CIRCLE, icon_color="white", on_click=lambda e: theme_changer(9), icon_size=50),
    ]))

    appearance_setting = SegmentedButton(selected=["1"],on_change=lambda e: on_mode_change(e),show_selected_icon=True,segments=[
                Segment(value="1",label=Text("System"),icon=Icon(Icons.MONITOR)),
                Segment(value="2",label=Text("Light"),icon=Icon(Icons.WB_SUNNY_ROUNDED)),
                Segment(value="3",label=Text("Dark"),icon=Icon(Icons.DARK_MODE_ROUNDED)),
            ])

    preview_qr_area= Row(controls=[], alignment=ft.MainAxisAlignment.CENTER,expand=False, tight=True)
    
    def clear_dialog():
        delete_dialog = AlertDialog(
            title=Text("Discard?"),
            alignment=Alignment.CENTER,
            actions=[
                Button(content="No", on_click=lambda e: page.pop_dialog()),
                Button(icon=Icons.DELETE,bgcolor=Colors.RED_900,content="Yes", on_click=lambda e: clean_create_bs_up())],
            open=True)
        page.show_dialog(delete_dialog)
    
    def clean_create_bs_up():
        create_layout.open = False
        qr_url_input_field.value = ""
        page.update()   
    
    qr_type_dropdown = Dropdown(on_select=lambda e: type_trigger(e),border_width=0,value="URL/Link",options=[
        DropdownOption(text="URL/Link",leading_icon=Icons.LINK_ROUNDED),
        DropdownOption(text="Text",leading_icon=Icons.TEXT_FIELDS_ROUNDED),
        DropdownOption(text="WIFI",leading_icon=Icons.WIFI_ROUNDED),
        DropdownOption(text="Email",leading_icon=Icons.MAIL_OUTLINE_ROUNDED),
        DropdownOption(text="Phone",leading_icon=Icons.PHONE_ANDROID_ROUNDED),
        DropdownOption(text="Location",leading_icon=Icons.PIN_DROP_ROUNDED),
        DropdownOption(text="SMS",leading_icon=Icons.MESSAGE_ROUNDED),
        DropdownOption(text="Event",leading_icon=Icons.STAR_BORDER_ROUNDED),
    ])
    
    url_protocol_dropdown = Dropdown(value="https://",border_width=0,options=[
        DropdownOption(text="https://"),
        DropdownOption(text="http://"),
        ])

    wifi_name= TextField(
        expand=True,
        border_width=0,
        label="Enter network name",
        on_change=lambda e: prop_changed()
    )

    wifi_protocol_dropdown = Dropdown(value="WPA2",border_width=0,on_select=lambda e: wifi_protocol_changed(e),options=[
        DropdownOption(text="WPA2"),
        DropdownOption(text="WPA"),
        DropdownOption(text="WEP"),
        DropdownOption(text="No password"),
    ])

    def wifi_protocol_changed(e):
        selected = e.control.value 
        if selected == "No password":
            wifi_password_setting.visible = False
        else:
            wifi_password_setting.visible = True
        prop_changed()

    wifi_password= TextField(
        expand=True,
        border_width=0,
        label="Enter network password",
        on_change=lambda e: prop_changed()
    )

    wifi_password_setting= Column(visible=True,controls=[
        Divider(color="grey"),
        Row(controls=[
            Icon(icon=Icons.PASSWORD_ROUNDED),
            Text(value=("WIFI password"), size=20),
            Container(expand=True),
        ]),
        Container(border_radius=10,bgcolor=get_option_color_by_mode(),content=wifi_password),
    ])

    wifi_area = Column(visible=False,controls=[
        Row(controls=[
            Icon(icon=Icons.TEXT_FIELDS_ROUNDED),
            Text(value=("Network name"), size=20),
            Container(expand=True)
        ]),
        Container(border_radius=10,
            bgcolor=get_option_color_by_mode(),
            content=wifi_name
        ),
        Divider(color="grey"),
        Container(
            content=Row(controls=[
                Icon(icon=Icons.INFO_OUTLINE_ROUNDED,color=Colors.WHITE),
                Container(expand=True,content=Text(
                    value="If your network has no password, select it here!",
                    size=16,
                    color=Colors.WHITE
                )),
                ],
            ),
            padding=15,
            bgcolor=Colors.INVERSE_PRIMARY,border_radius=30,
            margin=Margin.only(left=0, right=0, top=5, bottom=5,)
        ),
        Row(controls=[
            Icon(icon=Icons.SHIELD),
            Text(value=("WIFI security protocol"), size=20),
            Container(expand=True),
            Container(border_radius=50,bgcolor=get_option_color_by_mode(),content=wifi_protocol_dropdown)
        ]),
        wifi_password_setting
    ])

    #EMAIL QR TYPE------------------------------------------------------------------------------
    #General elements

    email_address = TextField(expand=True,border_width=0,label="Enter address",hint_text="Enter address",on_change=lambda e: prop_changed())
    email_adv_checkbox = ft.Switch(value=False, on_change=lambda e: email_checkbox_changed())

    email_general_content=Column(visible=False,controls=[
        Row(controls=[
            Icon(icon=Icons.MAIL_ROUNDED),
            Text(value=("Address"), size=20),
            Container(expand=True)
        ]),
        Container(border_radius=10,
            bgcolor=get_option_color_by_mode(),
            content=email_address
        ),
        Divider(color="grey"),
        Row(controls=[
            Icon(icon=Icons.TEXT_FIELDS_ROUNDED),
            Text(value=("Advanced options"), size=20),
            Container(expand=True),
            Container(border_radius=50,bgcolor=get_option_color_by_mode(),content=email_adv_checkbox)
        ]),
    ])

    #On checkbox changed
    def email_checkbox_changed():
        if email_adv_checkbox.value:
            email_adv_content.visible = True
        else:
            email_adv_content.visible = False
        prop_changed()

    email_subject = TextField(expand=True, border_width=0, label="Subject", on_change=lambda e: prop_changed())
    email_body = TextField(expand=True, border_width=0, label="Body", multiline=True, on_change=lambda e: prop_changed())

    email_adv_content = Column(visible=False, controls=[
        Row(controls=[Icon(icon=Icons.SUBJECT_ROUNDED), Text(value="Subject", size=20), Container(expand=True)]),
        Container(border_radius=10, bgcolor=get_option_color_by_mode(), content=email_subject),
        Divider(color="grey"),
        Row(controls=[Icon(icon=Icons.TEXT_FIELDS_ROUNDED), Text(value="Body", size=20), Container(expand=True)]),
        Container(border_radius=10, bgcolor=get_option_color_by_mode(), content=email_body),
    ])

    #PHONE QR TYPE------------------------------------------------------------------------------
    #General elements

    phone_number = TextField(
        expand=True,
        border_width=0,
        label="Enter address",
        hint_text="",
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed())
    
    phone_prefix = TextField(
        border_width=0,
        label="",
        hint_text="",
        width=80,
        max_length=4,
        counter=Container(),
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed())

    phone_general_content=Column(visible=False,controls=[
        Row(controls=[
            Icon(icon=Icons.CALL_ROUNDED),
            Text(value=("Phone number"), size=20),
            Container(expand=True)
        ]),
        Row(
            expand=True,
            controls=[
            Container(
                border_radius=10,
                bgcolor=get_option_color_by_mode(),
                content=Row(controls=[
                    Text("+",margin=Margin(left=15),size=15),
                    phone_prefix
                ])
            ),
            Container(
                expand=True,
                border_radius=10,
                bgcolor=get_option_color_by_mode(),
                content=phone_number
            ),
        ])
    ]) 

    # SMS
    sms_prefix = TextField(
        border_width=0,
        label="",
        hint_text="",
        width=80,
        max_length=4,
        counter=Container(),
        keyboard_type=ft.KeyboardType.NUMBER,
        on_change=lambda e: prop_changed()
    )

    sms_number = TextField(expand=True, border_width=0, label="Enter phone number", keyboard_type=ft.KeyboardType.NUMBER, on_change=lambda e: prop_changed())
    sms_message = TextField(expand=True, border_width=0, label="Enter message", multiline=True, on_change=lambda e: prop_changed())

    sms_general_content = Column(visible=False, controls=[
        Row(controls=[Icon(icon=Icons.SMS_ROUNDED), Text(value="Phone number", size=20), Container(expand=True)]),
        Row(controls=[
            Container(
                border_radius=10,
                bgcolor=get_option_color_by_mode(),
                content=Row(controls=[Text("+", margin=Margin(left=15), size=15), sms_prefix])
            ),
            Container(border_radius=10, expand=True, bgcolor=get_option_color_by_mode(), content=sms_number),
        ]),
        Divider(color="grey"),
        Row(controls=[Icon(icon=Icons.MESSAGE_ROUNDED), Text(value="Message", size=20), Container(expand=True)]),
        Container(border_radius=10, bgcolor=get_option_color_by_mode(), content=sms_message),
    ])

    # Location
    location_lat = TextField(expand=True, border_width=0, label="Latitude", keyboard_type=ft.KeyboardType.NUMBER, on_change=lambda e: prop_changed())
    location_lng = TextField(expand=True, border_width=0, label="Longitude", keyboard_type=ft.KeyboardType.NUMBER, on_change=lambda e: prop_changed())

    location_general_content = Column(visible=False, controls=[
        Row(controls=[Icon(icon=Icons.PIN_DROP_ROUNDED), Text(value="Coordinates", size=20), Container(expand=True)]),
        Row(controls=[
            Container(border_radius=10, expand=True, bgcolor=get_option_color_by_mode(), content=location_lat),
            Container(border_radius=10, expand=True, bgcolor=get_option_color_by_mode(), content=location_lng),
        ]),
    ])

    # Event (vCalendar/iCal básico)
    event_title = TextField(expand=True, border_width=0, label="Event title", on_change=lambda e: prop_changed())
    event_location = TextField(expand=True, border_width=0, label="Location", on_change=lambda e: prop_changed())
    event_start = TextField(expand=True, border_width=0, label="Start (YYYYMMDDTHHMMSS)", hint_text="20260101T120000", on_change=lambda e: prop_changed())
    event_end = TextField(expand=True, border_width=0, label="End (YYYYMMDDTHHMMSS)", hint_text="20260101T130000", on_change=lambda e: prop_changed())

    event_general_content = Column(visible=False, controls=[
        Row(controls=[Icon(icon=Icons.STAR_BORDER_ROUNDED), Text(value="Event title", size=20), Container(expand=True)]),
        Container(border_radius=10, bgcolor=get_option_color_by_mode(), content=event_title),
        Divider(color="grey"),
        Row(controls=[Icon(icon=Icons.PIN_DROP_ROUNDED), Text(value="Location", size=20), Container(expand=True)]),
        Container(border_radius=10, bgcolor=get_option_color_by_mode(), content=event_location),
        Divider(color="grey"),
        Row(controls=[
            Container(border_radius=10, expand=True, bgcolor=get_option_color_by_mode(), content=event_start),
            Container(border_radius=10, expand=True, bgcolor=get_option_color_by_mode(), content=event_end),
        ]),
    ])
    
    qr_url_input_field = TextField(expand=True,border_width=0,label="Enter URL or text",on_change=lambda e: prop_changed())
    error_correction_dropdown = Dropdown(value="M (15%)",border_width=0,on_select=lambda e: prop_changed(),options=[
        DropdownOption(text="L (7%)"),
        DropdownOption(text="M (15%)"),
        DropdownOption(text="Q (25%)"),
        DropdownOption(text="H (30%)"),
        ])
    qr_color_scheme_primary = MaterialPicker(on_color_change=lambda e:prop_changed(),color="black")
    qr_color_scheme_secondary = MaterialPicker(on_color_change=lambda e:prop_changed(),color="white")

    input_row = Column(controls=[Row(controls=[Icon(icon=Icons.SHORT_TEXT_ROUNDED),Text(value=("Content"), size=20)]),Row(visible=True,controls=[Container(border_radius=50,bgcolor=get_option_color_by_mode(),content=url_protocol_dropdown),Container(border_radius=10,expand=True,bgcolor=get_option_color_by_mode(),content=qr_url_input_field)]),
    ])
    create_layout= BottomSheet(draggable=False,use_safe_area=True,scrollable=False,fullscreen=True,open=False,on_dismiss=lambda e: clean_create_bs_up(),content=
        Column(horizontal_alignment="center",scroll=ScrollMode.AUTO,controls=[
            Container(bgcolor=Colors.INVERSE_PRIMARY,border_radius=30,expand=False,content=preview_qr_area,padding=20,),
            Container(bgcolor=Colors.SECONDARY_CONTAINER,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                Row(alignment="center",controls=[
                    IconButton(
                        icon=Icons.CLOSE,
                        expand=True, 
                        on_click=lambda e: clear_dialog(),    
                        style=ButtonStyle(
                            shape=RoundedRectangleBorder(radius=12),
                            bgcolor={"": Colors.RED_500}, 
                        )
                    ),
                    IconButton(
                        icon=Icons.CHECK,
                        expand=True,
                        on_click=lambda e: qr_create_triggered(), 
                        style=ButtonStyle(
                            shape=RoundedRectangleBorder(radius=12),
                            bgcolor={"": Colors.INVERSE_PRIMARY}, 
                        )
                    ),
                ])
            ),
            Container(bgcolor=get_container_color_by_mode(),border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                Column(controls=[
                    Row(controls=[Icon(icon=Icons.ARROW_DROP_DOWN_CIRCLE_OUTLINED),Text(value=("QR Type"), size=20),Container(expand=True),Container(border_radius=50,bgcolor=get_option_color_by_mode(),content=qr_type_dropdown)]),
                    Divider(color="grey"),
                    wifi_area,
                    input_row,
                    email_general_content,
                    email_adv_content,
                    phone_general_content,
                    sms_general_content,
                    location_general_content,
                    event_general_content,
                    Divider(color="grey"),
                    Row(controls=[Icon(icon=Icons.CHECK_CIRCLE_OUTLINE_ROUNDED),Text(value=("Error correction level"), size=20),Container(expand=True),Container(border_radius=50,bgcolor=get_option_color_by_mode(),content=error_correction_dropdown)]), 
                ])
            ),
            Text(value="Customization", size=18,color=Colors.PRIMARY),
            Container(bgcolor=get_container_color_by_mode(),border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                Column(controls=[
                    Row(controls=[Icon(icon=Icons.ADD_PHOTO_ALTERNATE_ROUNDED),Text(value=("Logo/Branding"), size=20)]),
                    Container(
                        content=Row(controls=[
                            Icon(icon=Icons.ERROR_OUTLINE_ROUNDED,color=Colors.WHITE),
                            Container(expand=True,content=Text(
                                value="As logos take up a big chunk of the QR's area, scanability may be greatly reduced. Thus, it is highly reccomended that H level error correction is used.",
                                size=16,
                                color=Colors.WHITE
                            )),
                            ],
                        ),
                        padding=15,
                        bgcolor=Colors.RED_500,border_radius=30,
                        margin=Margin.only(left=0, right=0, top=5, bottom=5,)
                    ),
                    Row(controls=[
                    Button(content="Pick image from folder",icon=Icons.FOLDER_COPY_ROUNDED, on_click=lambda e: asyncio.ensure_future(pick_logo())),
                    Container(expand=True),
                    Button(content="Remove logo",icon=Icons.DELETE_ROUNDED, on_click=lambda e: remove_logo()),
                    ]),
                    Divider(color="grey"),
                    Text(value=("Color scheme"), size=20, color=Colors.PRIMARY),
                    ExpansionTile(title="Primary color:",controls=qr_color_scheme_primary),
                    ExpansionTile(title="Background color:",controls=qr_color_scheme_secondary),
                ])
            ),
            Container(height=50)
        ]),
    )
    
    def prop_changed():
        if _debounce_task["task"] is not None:
            _debounce_task["task"].cancel()
        _debounce_task["task"] = page.run_task(_debounced_update)

    async def _debounced_update():
        await asyncio.sleep(0.3)
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
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2,error_correction)
        elif qr_type_dropdown.value == "URL/Link":
                if url_protocol_dropdown.value == "https://":
                    create_val = "https://"+qr_url_input_field.value
                else:
                    create_val = "http://"+qr_url_input_field.value
                display_preview_qr(create_val, color_rgb_1, color_rgb_2,error_correction)
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
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2,error_correction)

        elif qr_type_dropdown.value == "SMS":
            qr_url_input_field.value = f"SMSTO:{sms_number.value}:{sms_message.value}"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)

        elif qr_type_dropdown.value == "Location":
            qr_url_input_field.value = f"geo:{location_lat.value},{location_lng.value}"
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)

        elif qr_type_dropdown.value == "Event":
            qr_url_input_field.value = (
                f"BEGIN:VEVENT\n"
                f"SUMMARY:{event_title.value}\n"
                f"LOCATION:{event_location.value}\n"
                f"DTSTART:{event_start.value}\n"
                f"DTEND:{event_end.value}\n"
                f"END:VEVENT"
            )
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2, error_correction)
        else:
            display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2,error_correction)
            
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
            event_general_content,]:
            
            area.visible = False

        #Empty everything
        for field in [
            wifi_name, wifi_password, email_address, email_subject, email_body,
            phone_prefix, phone_number, sms_prefix, sms_number, sms_message,
            location_lat, location_lng, event_title, event_location, event_start, event_end,]:
            
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

        prop_changed()
        page.update()

    all_view=Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    regular_view=Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    pinned_view =Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    
    overview = Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[
        #Container(content=Image(os.path.join(ASSET_DIR,"QuickeR_horizontal_logo.png")),height=150,padding=0, bgcolor=get_container_color_by_mode(), border_radius=30),
        Row(controls=[
            IconButton(icon=Icons.INFO_OUTLINE_ROUNDED, tooltip=Tooltip(message="Tap the + icon to create a QR, and tap the rows to see details!")),
            Text(value="All QR codes",size=30,margin=Margin(left=-10),)
        ]),
        Divider(color="grey"),
        Container(padding=20,bgcolor=get_container_color_by_mode(),border_radius=20,content=    
            SegmentedButton(selected=["1"],on_change=lambda e: on_filter_change(e),show_selected_icon=True,segments=[
                Segment(value="1",label=Text("All"),icon=Icon(Icons.CLEAR_ALL)),
                Segment(value="2",label=Text("Unpinned"),icon=Icon(Icons.PUSH_PIN_OUTLINED)),
                Segment(value="3",label=Text("Pinned"),icon=Icon(Icons.PUSH_PIN_ROUNDED)),
            ]),
        ),
        
        all_view,    
    ])

    #Settings page
    support_me = Container(bgcolor=Colors.SECONDARY_CONTAINER,border_radius=30,padding=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),content=Column(controls=[
        Text(value="Support me!", weight=5, size=30),
        Container(
            content=Text(
                value="If you like this app, consider supporting me by donating, sharing the app, contributing code or give it a star in github.",
            ),
        ),
        Row(wrap=True,controls=[Button(icon=Icons.STAR,content="Star on github",on_click=lambda e:asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK")),height=80),Button(icon=Icons.COFFEE,content="Buy me a coffee")],)
        ]))
    bug_report = Container(bgcolor=Colors.PRIMARY_CONTAINER,border_radius=30,padding=30,content=Column(wrap=True,controls=[
        Text(value="Bugs", weight=5, size=30),
        Text(value="Found any bugs, issues or errors? Report them on the github 'Issues' tab."+"\n"+"Please check if the same bug has been already reportedif you can! "),
        Row(controls=[Button(icon=Icons.BUG_REPORT,content="Github Issues")],)
        ]))
    
    settings_view = Column(
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        scroll=ScrollMode.AUTO,
        controls=[
            Container(content=Text(value="QuickeR",size=40), margin=Margin(bottom=15,top=15)),
            Text(value="Settings and info",size=20, margin=Margin(bottom=-10)),
            Text(value="Check the project's about section!",size=10),
            Row(alignment="center",controls=Text(value="Customization", size=18, color=Colors.PRIMARY)),
            Container(
                bgcolor=get_container_color_by_mode(),
                border_radius=30,
                margin=Margin.only(left=20, right=20, top=5, bottom=5),
                padding=20,
                content=Column(controls=[
                    Row(controls=[
                        Icon(icon=Icons.WB_SUNNY_ROUNDED, size=40, color=Colors.PRIMARY),
                        Column(spacing=-3, controls=[
                            Text(value=("Appearance"), size=20, color=Colors.PRIMARY),
                            Text(value=("Select the color mode of the app."), size=13)
                        ])
                    ]),
                    appearance_setting,
                    Divider(color="grey"),
                    Row(controls=[
                        Icon(icon=Icons.COLOR_LENS_ROUNDED, size=40, color=Colors.PRIMARY),
                        Column(spacing=-3, controls=[
                            Text(value=("Color theme"), size=20, color=Colors.PRIMARY),
                            Text(value=("Select the color mode of the app."), size=13)
                        ])
                    ]),
                    themes_row,
                ])),
                
            Row(alignment="center",controls=Text(value="About", size=18, color=Colors.PRIMARY)),
            support_me,
            Container(bgcolor=get_container_color_by_mode(),border_radius=30,padding=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),content=Column(controls=[
                Text(value="Developed by Unax Martinez Llorente (aka ChoiceZero)"),
                Text(value="Made in Spain"),
                Text(value="Version number: Beta 0.0.3"),
            ])),
            
        ]
    )
    
    nav_bar = ft.NavigationBar(on_change=lambda e: on_tab_change(e),
    destinations=[
        NavigationBarDestination(icon=Icons.CLEAR_ALL, label="All QR Codes"),
        NavigationBarDestination(icon=Icons.SETTINGS, label="Settings"),],)
    nav_rail = ft.NavigationRail(
        selected_index=0,
        on_change=lambda e: on_tab_change(e),
        bgcolor=Colors.SURFACE_CONTAINER,
        height=100,
        destinations=[
            ft.NavigationRailDestination(icon=Icons.CLEAR_ALL, label="All QR Codes"),
            ft.NavigationRailDestination(icon=Icons.SETTINGS, label="Settings"),
        ],
    )
    
    add_button = ft.FloatingActionButton(icon=Icons.ADD, on_click=qr_creator_open)
    
    nav_rail_wrapper = Container(content=Column(controls=[
        Container(content=add_button, padding=19,width=nav_rail.width,margin=Margin(bottom=-40)),
        Divider(color=Colors.SECONDARY,thickness=1),
        nav_rail,
        Container(expand=True),
        Container(content=IconButton(icon=Image(os.path.join(ASSET_DIR,"github-white-icon.webp"),color=get_github_icon_by_mode(),width=40,height=40),on_click=lambda e:asyncio.ensure_future(open_url("https://github.com/ChoiceZero/QuickeR","BLANK"))),padding=19)
    ]),
    bgcolor=Colors.SURFACE_CONTAINER,expand=False, height=page.height, border_radius=20)

    async def open_url(url_to_open,target: ft.UrlTarget):
        url = url_to_open
        await ft.UrlLauncher().launch_url(ft.Url(url=url, target=target))

    view = Column(width=100,controls=[overview],horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    safearea= ft.SafeArea(content=view,expand=True)
    page.overlay.append(create_layout)

    root_row = Row(controls=[safearea], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    page.add(root_row)

    def on_resize(e):
        #if page.width >= 1200:
        #    page.navigation_bar = None
        #    page.floating_action_button = None
        #    page.navigation_rail = None
        #    root_row.append()
        if page.width >= 700:
            page.navigation_bar = None
            page.floating_action_button = None
            page.navigation_rail = nav_rail_wrapper
            if nav_rail_wrapper not in root_row.controls:
                root_row.controls.insert(0, nav_rail_wrapper)
        else:
            page.navigation_rail = None
            page.floating_action_button = add_button
            page.navigation_bar = nav_bar
            if nav_rail_wrapper in root_row.controls:
                root_row.controls.remove(nav_rail_wrapper)
        page.update()

    page.on_resize = on_resize
    
    on_resize(None)

    load_qrs()
    theme_loader()
    appearance_loader()
    display_preview_qr("","black","white",ERROR_CORRECTION_MAP["M (15%)"])

ft.run(main)