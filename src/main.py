import os
import qrcode
import cv2 
import time 
import flet as ft
from flet import SnackBar,ExpansionTile,Dropdown,DropdownOption,SegmentedButton,Segment,ThemeMode,Theme,Page,RoundedRectangleBorder,ButtonStyle,Divider,Stack,BottomSheet,Border,Margin,Icon,Icons, IconButton, NavigationBarDestination, Checkbox, VerticalDivider, Container, Image, TextField, Text, Row, Column, Colors, ScrollMode, AlertDialog, FilePicker, TextButton, Alignment, Button, IconButton
from flet_color_pickers import MaterialPicker,ColorPicker
from pathlib import Path
import platform
import shutil
import json
import base64
from io import BytesIO  
import asyncio
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QR_DIR = os.path.join(BASE_DIR, "qr_codes")
print(f"QR_DIR: {QR_DIR}")
PINNED_DIR = os.path.join(BASE_DIR, "pinned_qr_codes")

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(PINNED_DIR, exist_ok=True)

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

        else:  # macOS or unknown
            return str(Path.home() / "Pictures")

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
            self.display_qr()

    def id_assigner(self):
        initial_time = time.localtime()
        output_time = str(initial_time.tm_year)+str(initial_time.tm_mon)+str(initial_time.tm_mday)+str(initial_time.tm_hour)+str(initial_time.tm_min)+str(initial_time.tm_sec)
        return output_time
    
    def display_qr(self):
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
        
        self.main_container = Container(on_click=lambda e:self.display_details_bottomsheet(),content=self.qr_row,padding=10, border_radius=20,bgcolor=Colors.SECONDARY_CONTAINER)
        
        self.all_view.controls.append(self.main_container)
        self.regular_view.controls.append(self.main_container)
  
        #if self.date[0:10] == time.strftime("%Y-%m-%d",time.localtime()):
        #    self.home_view.controls.append(self.main_container)
        #self.page.update()
    
    def display_pinned_qr(self):
        qr = Image(src=os.path.join(PINNED_DIR, f"{self.qr_id}.png"), border_radius=10, width=50, height=50)
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
            ]),
            Container(expand=True),
            Icon(icon=Icons.PUSH_PIN_ROUNDED)
        ])
        
        self.main_container = Container(on_click=lambda e:self.display_details_bottomsheet(),content=self.qr_row,padding=10, border_radius=20,bgcolor=Colors.SECONDARY_CONTAINER)
        
        self.all_view.controls.append(self.main_container)
        self.pinned_view.controls.append(self.main_container)
  
        #if self.date[0:10] == time.strftime("%Y-%m-%d",time.localtime()):
        #    self.home_view.controls.append(self.main_container)
        #self.page.update()

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
            alignment=Alignment.CENTER,
            actions=[
                Row(expand=True,alignment="center",controls=self.filetext),
                Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_folder()),margin=Margin(bottom=5,top=10),height=80,padding=10,bgcolor=Colors.SECONDARY_CONTAINER,content=Row(alignment="center",controls=[Icon(icon=Icons.FOLDER_COPY_ROUNDED),Text(value="Select a folder (.png)")])),
                Container(border_radius=20,on_click=lambda e: asyncio.ensure_future(self.export_to_gallery()),margin=Margin(bottom=5,top=5),height=80,padding=10,bgcolor=Colors.SECONDARY_CONTAINER,content=Row(alignment="center",controls=[Icon(icon=Icons.IMAGE_ROUNDED),Text(value="Add to gallery")])),
                Container(border_radius=20,margin=Margin(top=5),height=80,padding=10,bgcolor=Colors.SECONDARY_CONTAINER,content=Row(alignment="center",controls=[Icon(icon=Icons.FILE_COPY_ROUNDED),Text(value="Export as 3D model (.STL)")])),
            ],
        )
        self.page.show_dialog(download_dialog)

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
        self.filetext.value = ""

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
        self.filetext.value = ""

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
        self.pin_button.bgcolor = Colors.PINK_900
        self.pin_button.icon = Icons.PUSH_PIN
        shutil.move(os.path.join(QR_DIR, f"{self.qr_id}.png"), os.path.join(PINNED_DIR, f"{self.qr_id}.png"))
        self.regular_view.controls.remove(self.main_container)
        self.all_view.controls.remove(self.main_container)
        self.display_pinned_qr()

    def unpin_qr_action(self):
        self.pin_button.bgcolor = Colors.PURPLE_900
        self.pin_button.icon = Icons.PUSH_PIN_OUTLINED
        try:
            shutil.move(os.path.join(PINNED_DIR, f"{self.qr_id}.png"), os.path.join(QR_DIR, f"{self.qr_id}.png"))
        except Exception:
            os.makedirs(PINNED_DIR, exist_ok=True)
            shutil.move(os.path.join(PINNED_DIR, f"{self.qr_id}.png"), os.path.join(QR_DIR, f"{self.qr_id}.png"))
        self.pinned_view.controls.remove(self.main_container)
        self.all_view.controls.remove(self.main_container)
        self.display_qr()

    def display_details_bottomsheet(self):
        qr_path = os.path.join(QR_DIR, f"{self.qr_id}.png")
        pinned_path = os.path.join(PINNED_DIR, f"{self.qr_id}.png")
        if os.path.exists(qr_path):
            qrpath = qr_path
            qr = Image(src=qr_path, border_radius=10, width=250, height=250)
            self.pin_button = IconButton(icon=Icons.PUSH_PIN_OUTLINED, on_click=self.pin_triggered, expand=True,
                style=ButtonStyle(shape=RoundedRectangleBorder(radius=12), bgcolor={"": Colors.PURPLE_900}))
        elif os.path.exists(pinned_path):
            qrpath = pinned_path
            qr = Image(src=pinned_path, border_radius=10, width=250, height=250)
            self.pin_button = IconButton(icon=Icons.PUSH_PIN, on_click=self.pin_triggered, expand=True,
                style=ButtonStyle(shape=RoundedRectangleBorder(radius=12), bgcolor={"": Colors.PINK_900}))
        elif os.path.exists(os.path.join(PINNED_DIR, f"{self.qr_id}.png")):
            qrpath=os.path.join(PINNED_DIR, f"{self.qr_id}.png")
            qr = Image(src=os.path.join(PINNED_DIR, f"{self.qr_id}.png"),border_radius=10,width=250,height=250)
            self.pin_button = IconButton(
                icon=Icons.PUSH_PIN,
                on_click=self.pin_triggered,
                expand=True, 
                style=ButtonStyle(
                    shape=RoundedRectangleBorder(radius=12),
                    bgcolor={"": Colors.PINK_900}, 
                ))         
        
        self.details_bs = BottomSheet(draggable=True,show_drag_handle=True,use_safe_area=True,scrollable=False,fullscreen=True,open=False,on_dismiss=lambda e: self.clean_bs_up(),content=
            Stack(controls=[
                Column(horizontal_alignment="center",scroll=ScrollMode.AUTO,controls=[
                    Container(bgcolor=Colors.PRIMARY,border_radius=30,content=qr,padding=20,margin=Margin.only(left=20, right=20, bottom=5)),
                    Container(bgcolor=Colors.SECONDARY_CONTAINER,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                        Row(alignment="center",controls=[
                            IconButton(
                                icon=Icons.DOWNLOAD,
                                expand=True,
                                on_click=lambda e: self.download_qr_action(),
                                style=ButtonStyle(
                                    shape=RoundedRectangleBorder(radius=12),
                                    bgcolor={"": Colors.GREEN_900}, 
                                )
                            ),
                            IconButton(
                                icon=Icons.SHARE,
                                expand=True,
                                on_click=lambda e: asyncio.ensure_future(self.do_share_files_from_paths()), 
                                style=ButtonStyle(
                                    shape=RoundedRectangleBorder(radius=12),
                                    bgcolor={"": Colors.GREEN_900}, 
                                )
                            ),
                            IconButton(
                                icon=Icons.EDIT,
                                expand=True, 
                                style=ButtonStyle(
                                    shape=RoundedRectangleBorder(radius=12),
                                    bgcolor={"": Colors.BLUE_900}, 
                                )
                            ),
                            self.pin_button,
                            IconButton(icon=Icons.DELETE,expand=True,on_click=lambda e: self.delete_qr_action(e), style=ButtonStyle(shape=RoundedRectangleBorder(radius=12),bgcolor={"": Colors.RED_900},)),
                        ])
                    ),
                    Text(value="General", size=18,color=Colors.PRIMARY),
                    Container(bgcolor=Colors.GREY_800,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                        Column(controls=[
                            Row(controls=[Icon(icon=Icons.INSERT_LINK_ROUNDED),Column(spacing=-3,controls=[Text(value=("Url/text"), size=16),Text(value=(self.url),size=11)])]),
                            Divider(),
                            Row(controls=[Icon(icon=Icons.CALENDAR_MONTH_ROUNDED),Column(spacing=-3,controls=[Text(value=("Creation date"), size=16),Text(value=(self.qr_date),size=11)])]),
                            Divider(),
                            Row(controls=[Icon(icon=Icons.FOLDER_COPY_ROUNDED),Column(spacing=-3,controls=[Text(value=("Internal path"), size=16),Text(value=(qrpath),size=11)])]), 
                            Divider(),
                            Row(controls=[Icon(icon=Icons.INSERT_DRIVE_FILE_ROUNDED),Column(spacing=-3,controls=[Text(value=("Filesize"), size=16),Text(value=(self.qr_size),size=11)]),]),
                        ])
                    ),
                    Text(value="Customization", size=18,color=Colors.PRIMARY),
                    Container(bgcolor=Colors.GREY_800,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                        Column(controls=[
                            Row(controls=[Text(value=("Custom branding?: "))]),
                            Divider(),
                            Text(value=("Custom branding image path: ")),
                            Divider(),
                            Text(value=("Colors: ")),
                        ])
                    ),
                    Container(height=50)
                ]),
            ])
        )
        self.page.overlay.append(self.details_bs)
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
    page.scroll = ScrollMode.ADAPTIVE
    preview_qr = ""
    last_qr_image = {"img": None}
    _debounce_task = {"task": None}

    date_list=[]

    # "#769CDF",

    page.fonts = {
        "AndroidDefault": "/GoogleSansFlex(1).ttf",
        "Header":"/GoogleSansFlex(2).ttf"
    }

    def display_preview_qr(url, qr_color_primary,qr_color_secondary):
        preview_qr_area.controls.clear()
        prev_qr = qrcode.QRCode()
        prev_qr.add_data(str(url))
        pil_img = prev_qr.make_image(fill_color=qr_color_primary, back_color=qr_color_secondary)
        pil_img = pil_img.convert("RGB")
        last_qr_image["img"] = pil_img
        archivo_temporal_ram = BytesIO()
        pil_img.save(archivo_temporal_ram, format="PNG")
        base64_puro = base64.b64encode(archivo_temporal_ram.getvalue()).decode(
            "utf-8"
        )
        uri_base64 = f"data:image/png;base64,{base64_puro}"
        preview_qr = ft.Image(src=uri_base64, width=200, height=200)
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
            brightness = page.platform_brightness
            if brightness == ft.Brightness.DARK:
                page.theme_mode = ThemeMode.DARK
            elif brightness == ft.Brightness.LIGHT:
                page.theme_mode= ThemeMode.LIGHT
        elif appearance == "Dark":
            page.theme_mode = ThemeMode.DARK
        elif appearance == "Light":
            page.theme_mode = ThemeMode.LIGHT
        page.update()

    async def get_permission_status():
        if platform.system() == "Android":
            try:
                import flet_permission_handler as fph            
                global ph 
                ph = fph.PermissionHandler()
                page.overlay.append(ph)
                page.update()
                status = await ph.get_status(fph.Permission.STORAGE)
                if status == fph.PermissionStatus.DENIED:
                    show_permissions_dialog()
                    await ph.request(fph.Permission.STORAGE)
            except ImportError:
                print("flet_permission_handler not found. Skipping permission check.")
    
    def show_permissions_dialog():
        error_dialog = AlertDialog(
            title=Text("Permissions needed"),
            alignment=Alignment.CENTER,
            content=Text("Some permissions are required to use this app. Please, grant them."),
            actions=[TextButton("Close App", on_click=lambda e: ft.app().close()),TextButton("Open Settings", on_click=lambda e: open_settings),],
            open=True)
        page.show_dialog(error_dialog)

    async def open_settings():
        try:
            import flet_permission_handler as fph
            global ph
            # Attempt to reopen settings context if needed
            if 'ph' not in globals() or ph is None:
                ph = fph.PermissionHandler()
                page.overlay.append(ph)
                page.update()
            await ph.open_app_settings()
            page.pop_dialog()
            get_permission_status()
            await ph.open_app_settings()
            page.pop_dialog()
        except ImportError:
             print("flet_permission_handler not available to open settings.")
    
    def load_qrs():
        if os.path.exists(PINNED_DIR):
            for file in os.listdir(PINNED_DIR):
                if file.endswith(".png"):
                    qr_id = file[:-4]
                    image = cv2.imread(os.path.join(PINNED_DIR, file))
                    detector = cv2.QRCodeDetector()
                    data, bbox, straight_qrcode = detector.detectAndDecode(image)
                    qr = QRCodes(page, data, all_view, regular_view, pinned_view)
                    qr.qr_id = qr_id
                    qr.date = qr.get_qr_date(qr_id)
                    qr.url = data
                    qr.display_pinned_qr()

        if os.path.exists(QR_DIR):
            for file in os.listdir(QR_DIR):
                if file.endswith(".png"):
                    qr_id = file[:-4]
                    image = cv2.imread(os.path.join(QR_DIR, file))
                    detector = cv2.QRCodeDetector()
                    data, bbox, straight_qrcode = detector.detectAndDecode(image)
                    qr = QRCodes(page, data, all_view, regular_view, pinned_view)
                    qr.qr_id = qr_id
                    qr.date = qr.get_qr_date(qr_id)
                    qr.url = data
                    qr.display_qr()

    def qr_creator_open():
        create_layout.open = True
        page.update() 
    
    def qr_create_triggered(color_rgb_1, color_rgb_2):
        if contrast_ratio(color_rgb_1, color_rgb_2) < 4.5: 
            AlertDialog(
                title=Text("Contrast too low"),
                alignment=Alignment.CENTER,
                content=Text("The contrast between the two colors is too low. The qr may be unreadable."),
                actions=[TextButton("Cancel", on_click=lambda e: page.pop_dialog()),TextButton("Create", on_click=lambda e: create_qr_action())],
                open=True)
        else:
            create_qr_action()

    def create_qr_action():
            if qr_type_dropdown.value == "URL/Link":
                if url_protocol_dropdown.value == "https://":
                    create_info = "https://"+qr_url_input_field.value
                else:
                    create_info = "http://"+qr_url_input_field.value
            else:
                create_info = qr_url_input_field.value
            new_qr = QRCodes(page, create_info, all_view, regular_view,pinned_view)
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

    def on_tab_change(e):
        if e.control.selected_index == 0:
            view.controls.clear()
            view.controls.append(overview)
        elif e.control.selected_index == 1:
            view.controls.clear()
            view.controls.append(settings_view)
    
    branding_checkbox = Checkbox(label="Use a custom logo?")

    save_folder = TextField(hint_text="Enter path", width=400)
    
    #Settings page
    support_me = Container(bgcolor=Colors.SECONDARY_CONTAINER,border_radius=30,padding=30,content=Column(wrap=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[
        Text(value="Support me!", weight=5, size=30),
        Text(value="If you like this app, consider supporting me by donating, sharing the app, contributing code or give it a star in github.",overflow=ft.TextOverflow.ELLIPSIS),
        Row(wrap=True,controls=[Button(icon=Icons.STAR,content="Star on github"),Button(icon=Icons.COFFEE,content="Buy me a coffee")],)
        ]))
    bug_report = Container(bgcolor=Colors.PRIMARY_CONTAINER,border_radius=30,padding=30,content=Column(wrap=True,controls=[
        Text(value="Bugs", weight=5, size=30),
        Text(value="Found any bugs, issues or errors? Report them on the github 'Issues' tab."+"\n"+"Please check if the same bug has been already reportedif you can! "),
        Row(controls=[Button(icon=Icons.BUG_REPORT,content="Github Issues")],)
        ]))
    settings_container = Container(bgcolor=Colors.TERTIARY_CONTAINER,border_radius=30,padding=30,content=Column(wrap=True,controls=[
        Text(value="Settings", weight=5, size=30),
        Text(value="Save folder", weight=5, size=20),
        Text(value="The path where the images are saved to whenever the respctive button is pressed."),
        Row(controls=[save_folder,Text(value="or"),Button(icon=Icons.FOLDER,content="Select folder")],)
        ]))
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

    appearance_setting = Column(controls=[
        Row(controls=[
            SegmentedButton(selected=["1"],on_change=lambda e: on_mode_change(e),show_selected_icon=True,segments=[
                Segment(value="1",label=Text("System"),icon=Icon(Icons.MONITOR)),
                Segment(value="2",label=Text("Light"),icon=Icon(Icons.WB_SUNNY_ROUNDED)),
                Segment(value="3",label=Text("Dark"),icon=Icon(Icons.DARK_MODE_ROUNDED)),
            ]),
        ]),
    ])

    preview_qr_area= Row(controls=[], alignment=ft.MainAxisAlignment.CENTER,expand=False)
    
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
    
    qr_type_dropdown = Dropdown(on_select=lambda e: type_trigger(e),value="URL/Link",options=[
        DropdownOption(text="WIFI",leading_icon=Icons.WIFI_ROUNDED),
        DropdownOption(text="URL/Link",leading_icon=Icons.LINK_ROUNDED),
        DropdownOption(text="Text",leading_icon=Icons.TEXT_FIELDS_ROUNDED),
        ])
    
    url_protocol_dropdown = Dropdown(value="https://",options=[
        DropdownOption(text="https://"),
        DropdownOption(text="http://"),
        ])
    
    qr_url_input_field = TextField(label="Enter URL or text",on_change=lambda e: prop_changed())

    qr_color_scheme_primary = MaterialPicker(on_color_change=lambda e:prop_changed(),color="black")
    qr_color_scheme_secondary = MaterialPicker(on_color_change=lambda e:prop_changed(),color="white")

    create_layout= BottomSheet(draggable=False,use_safe_area=True,scrollable=False,fullscreen=True,open=False,on_dismiss=lambda e: clean_create_bs_up(),content=
            Stack(controls=[
                Column(horizontal_alignment="center",scroll=ScrollMode.AUTO,controls=[
                    Container(bgcolor=Colors.PRIMARY,border_radius=30,expand=False,content=preview_qr_area,padding=20,margin=Margin.only(left=20, right=20, top=20, bottom=5)),
                    Container(bgcolor=Colors.SECONDARY_CONTAINER,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                        Row(alignment="center",controls=[
                            IconButton(
                                icon=Icons.CLOSE,
                                expand=True, 
                                on_click=lambda e: clear_dialog(),    
                                style=ButtonStyle(
                                    shape=RoundedRectangleBorder(radius=12),
                                    bgcolor={"": Colors.RED_900}, 
                                )
                            ),
                            IconButton(
                                icon=Icons.CHECK,
                                expand=True,
                                on_click=lambda e: qr_create_triggered(), 
                                style=ButtonStyle(
                                    shape=RoundedRectangleBorder(radius=12),
                                    bgcolor={"": Colors.PRIMARY_CONTAINER}, 
                                )
                            ),
                        ])
                    ),
                    
                    Container(bgcolor=Colors.GREY_800,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                        Column(controls=[
                            qr_type_dropdown,
                            Row(controls=[url_protocol_dropdown,qr_url_input_field]),
                            

                            #branding_checkbox,       
                        ])
                    ),
                    Text(value="Customization", size=18,color=Colors.PRIMARY),
                    Container(bgcolor=Colors.GREY_800,border_radius=30,margin=Margin.only(left=20, right=20, top=5, bottom=5),padding=20,content=
                        Column(controls=[
                            Row(controls=[Text(value=("Custom branding?: "))]),
                            Divider(),
                            Text(value=("Custom branding image path: ")),
                            Divider(),
                            Text(value=("Colors: ")),
                        ])
                    ),

                    #selected_color,
                    ExpansionTile(title="Select a color:",controls=qr_color_scheme_primary),
                    ExpansionTile(title="Select a color:",controls=qr_color_scheme_secondary),
                    Container(height=50)
                ]),
                #Container(border_radius=20,content=Row(controls=[IconButton(icon=Icons.CLOSE,bgcolor=Colors.ON_SECONDARY, on_click=lambda e: clean_create_bs_up())])),
            ])
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
        display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2)
        display_preview_qr(qr_url_input_field.value, color_rgb_1, color_rgb_2)

    def type_trigger(e):
        selected = e.control.value 
        url_protocol_dropdown.visible = False
        if selected == "WIFI":
            #print("selected WIFI")
            qr_url_input_field.hint_text = "Enter WIFI here"
            qr_url_input_field.label = "Enter WIFI"
        elif selected == "URL/Link":
            #print("selected URL")
            url_protocol_dropdown.visible = True
            qr_url_input_field.hint_text = "Enter URL here"
            qr_url_input_field.label = "Enter URL"
        elif selected == "Text":
            qr_url_input_field.hint_text = "Enter text here"
            qr_url_input_field.label = "Enter text"
        page.update()

    home_view = Column(controls=[], scroll=ScrollMode.AUTO, expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    create_view = Column(controls=[create_layout])

    all_view=Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    regular_view=Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    pinned_view =Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[])
    
    overview = Column(scroll=ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,controls=[
        Row(controls=[Column(controls=[
            Container(content=Text(value="QuickeR",size=40), margin=Margin(bottom=15,top=15)),
            Text(value="All QR codes",size=20, margin=Margin(bottom=-10)),
            Text(value="Tap the + icon to create a QR, and tap the row to see its details!",size=10),
            SegmentedButton(selected=["1"],on_change=lambda e: on_filter_change(e),margin=Margin.only(left=0, right=0, top=0, bottom=20),show_selected_icon=True,segments=[
                Segment(value="1",label=Text("All"),icon=Icon(Icons.CLEAR_ALL)),
                Segment(value="2",label=Text("Unpinned"),icon=Icon(Icons.PUSH_PIN_OUTLINED)),
                Segment(value="3",label=Text("Pinned"),icon=Icon(Icons.PUSH_PIN_ROUNDED)),
                ])]),
            ]),
            all_view,
        ])
    
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
                bgcolor=Colors.GREY_800,
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
                    Divider(),
                    Row(controls=[
                        Icon(icon=Icons.COLOR_LENS_ROUNDED, size=40, color=Colors.PRIMARY),
                        Column(spacing=-3, controls=[
                            Text(value=("Color theme"), size=20, color=Colors.PRIMARY),
                            Text(value=("Select the color mode of the app."), size=13)
                        ])
                    ]),
                    themes_row,
                ])),
                
            Row(alignment="center",controls=Text(value="General", size=18, color=Colors.PRIMARY)),
            Container(
                bgcolor=Colors.GREY_800,
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
                    Divider(),
                    Row(controls=[
                        Icon(icon=Icons.COLOR_LENS_ROUNDED, size=40, color=Colors.PRIMARY),
                        Column(spacing=-3, controls=[
                            Text(value=("Color theme"), size=20, color=Colors.PRIMARY),
                            Text(value=("Select the color mode of the app."), size=13)
                        ])
                    ]),
                    themes_row,
                    Divider(),
                    Row(controls=[
                        Icon(icon=Icons.FOLDER_COPY_ROUNDED),
                        Column(spacing=-3, controls=[Text(value=("Internal path"), size=16), Text(value=("qrpath"), size=11)])
                    ]),
                    Divider(),
                    Row(controls=[
                        Icon(icon=Icons.INSERT_DRIVE_FILE_ROUNDED),
                        Column(spacing=-3, controls=[Text(value=("Filesize"), size=16), Text(value=("self.qr_size"), size=11)])
                    ]),
                ])),
            
        ]
    )
    
    page.navigation_bar = ft.NavigationBar(on_change=lambda e: on_tab_change(e),
    destinations=[
        NavigationBarDestination(icon=Icons.CLEAR_ALL, label="All QR Codes"),
        NavigationBarDestination(icon=Icons.SETTINGS, label="Settings"),],)

    view = Column(expand=True,controls=[overview],horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    safearea= ft.SafeArea(content=view,expand=True)
    page.floating_action_button = ft.FloatingActionButton(icon=Icons.ADD, on_click=qr_creator_open)
    page.overlay.append(create_layout)
    
    page.add(safearea)
    load_qrs()
    page.run_task(get_permission_status)
    theme_loader()
    appearance_loader()
    display_preview_qr("","black","white")

ft.run(main)